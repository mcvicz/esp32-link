# esp32-link firmware

PlatformIO project targeting the ESP32-WROOM-32 (`esp32dev`).

## Build

```bash
cd firmware
pio run
```

## Flash

Connect the board over USB, then:

```bash
pio run --target upload
```

## Serial monitor

```bash
pio device monitor
```

Baud rate is 115200. On boot the firmware prints `esp32-link firmware booted`.
