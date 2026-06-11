#include <Arduino.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>

#include <functional>

namespace cfg {
constexpr char SSID[] = "ESP32-Console";
constexpr char PASSWORD[] = "esp32pass";
constexpr uint16_t WS_PORT = 81;
constexpr char WS_PATH[] = "/ws";
constexpr uint32_t TELEMETRY_INTERVAL_MS = 500;
constexpr uint8_t LED_PIN = 2;
}  // namespace cfg

struct Telemetry {
    uint32_t ts;
    float temp_c;
    uint32_t free_heap;
    int rssi;

    static Telemetry sample() {
        Telemetry t;
        t.ts = millis();

        // Arduino-ESP32 2.0.14+ returns Celsius on classic ESP32; we no longer
        // apply the historical Fahrenheit-to-Celsius conversion that older 2.x
        // releases needed. (Verified against framework-arduinoespressif32 2.0.17.)
        t.temp_c = temperatureRead();

        t.free_heap = ESP.getFreeHeap();

        wifi_sta_list_t sta_list;
        if (esp_wifi_ap_get_sta_list(&sta_list) == ESP_OK && sta_list.num > 0) {
            t.rssi = sta_list.sta[0].rssi;
        } else {
            t.rssi = 0;
        }

        return t;
    }
};

namespace Protocol {

String encodeTelemetry(const Telemetry& t) {
    JsonDocument doc;
    doc["type"] = "telemetry";
    doc["ts"] = t.ts;

    char tempBuf[16];
    dtostrf(t.temp_c, 0, 1, tempBuf);
    doc["temp_c"] = serialized(String(tempBuf));

    doc["free_heap"] = t.free_heap;
    doc["rssi"] = t.rssi;

    String out;
    serializeJson(doc, out);
    out += '\n';
    return out;
}

String encodeAck(const char* cmd_id, bool ok, const String& msg) {
    JsonDocument doc;
    doc["type"] = "ack";
    doc["cmd_id"] = cmd_id;
    doc["ok"] = ok;
    doc["msg"] = msg;

    String out;
    serializeJson(doc, out);
    out += '\n';
    return out;
}

}  // namespace Protocol

namespace CommandDispatcher {

static bool ledState = false;

String dispatch(const String& payload) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, payload);
    if (err) {
        String preview = payload.substring(0, 60);
        Serial.printf("[err]  malformed json: %s\n", preview.c_str());
        return String();
    }

    const char* type = doc["type"] | (const char*)nullptr;
    if (!type) {
        Serial.println("[err]  message missing type");
        return String();
    }
    if (strcmp(type, "cmd") != 0) {
        Serial.printf("[err]  unknown type: %s\n", type);
        return String();
    }

    const char* cmd_id = doc["cmd_id"] | (const char*)nullptr;
    if (!cmd_id) {
        Serial.println("[err]  cmd missing cmd_id");
        return String();
    }

    const char* action = doc["action"] | (const char*)nullptr;
    if (!action) {
        return Protocol::encodeAck(cmd_id, false, String("missing action"));
    }

    if (strcmp(action, "toggle_led") == 0) {
        ledState = !ledState;
        digitalWrite(cfg::LED_PIN, ledState ? HIGH : LOW);
        const char* stateStr = ledState ? "on" : "off";
        Serial.printf("[cmd]  toggle_led -> led %s\n", stateStr);
        return Protocol::encodeAck(cmd_id, true, String("led ") + stateStr);
    }

    if (strcmp(action, "ping") == 0) {
        Serial.println("[cmd]  ping -> pong");
        return Protocol::encodeAck(cmd_id, true, String("pong"));
    }

    Serial.printf("[cmd]  unknown action: %s\n", action);
    return Protocol::encodeAck(cmd_id, false, String("unknown action: ") + action);
}

}  // namespace CommandDispatcher

class WsServer {
public:
    using MessageHandler = std::function<String(const String&)>;

    WsServer() : server_(cfg::WS_PORT), ws_(cfg::WS_PATH) {}

    void onMessage(MessageHandler handler) { handler_ = std::move(handler); }

    void begin() {
        ws_.onEvent([this](AsyncWebSocket* /*s*/, AsyncWebSocketClient* client,
                           AwsEventType type, void* arg, uint8_t* data, size_t len) {
            handleEvent(client, type, arg, data, len);
        });
        server_.addHandler(&ws_);
        server_.begin();
    }

    void broadcast(const String& text) {
        if (ws_.count() == 0) return;
        ws_.textAll(text);
    }

    size_t clientCount() const { return ws_.count(); }

private:
    AsyncWebServer server_;
    AsyncWebSocket ws_;
    MessageHandler handler_;

    void handleEvent(AsyncWebSocketClient* client, AwsEventType type, void* arg,
                     uint8_t* data, size_t len) {
        if (type == WS_EVT_CONNECT) {
            Serial.printf("[ws]   client #%u connected from %s\n", client->id(),
                          client->remoteIP().toString().c_str());
        } else if (type == WS_EVT_DISCONNECT) {
            Serial.printf("[ws]   client #%u disconnected\n", client->id());
        } else if (type == WS_EVT_DATA) {
            AwsFrameInfo* info = static_cast<AwsFrameInfo*>(arg);
            if (info->final && info->index == 0 && info->len == len &&
                info->opcode == WS_TEXT) {
                String payload;
                payload.reserve(len);
                for (size_t i = 0; i < len; ++i) payload += static_cast<char>(data[i]);
                if (handler_) {
                    String reply = handler_(payload);
                    if (reply.length() > 0) {
                        client->text(reply);
                    }
                }
            }
        }
    }
};

static WsServer wsServer;
static uint32_t lastTelemetry = 0;

void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("[boot] esp32-link firmware booted");

    pinMode(cfg::LED_PIN, OUTPUT);
    digitalWrite(cfg::LED_PIN, LOW);

    WiFi.mode(WIFI_AP);
    WiFi.softAP(cfg::SSID, cfg::PASSWORD);
    IPAddress ip = WiFi.softAPIP();
    Serial.printf("[wifi] AP started: %s @ %s\n", cfg::SSID, ip.toString().c_str());

    wsServer.onMessage(
        [](const String& payload) { return CommandDispatcher::dispatch(payload); });
    wsServer.begin();
    Serial.printf("[ws]   listening on port %u path %s\n", cfg::WS_PORT, cfg::WS_PATH);
}

void loop() {
    uint32_t now = millis();
    if (now - lastTelemetry >= cfg::TELEMETRY_INTERVAL_MS) {
        lastTelemetry = now;
        if (wsServer.clientCount() > 0) {
            Telemetry t = Telemetry::sample();
            wsServer.broadcast(Protocol::encodeTelemetry(t));
        }
    }
}
