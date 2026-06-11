"""pyqtgraph-based real-time chart widget for streaming telemetry samples."""

from collections import deque

import pyqtgraph as pg
from PySide6.QtCore import Slot

from esp32_link.domain.messages import Telemetry

WINDOW_SECONDS: float = 60.0

_TEMP_PEN = pg.mkPen(color=(220, 50, 47), width=2)
_HEAP_PEN = pg.mkPen(color=(38, 139, 210), width=2)
_RSSI_PEN = pg.mkPen(color=(133, 153, 0), width=2)


class ChartWidget(pg.GraphicsLayoutWidget):
    """Three stacked plots showing temperature, free heap, and RSSI."""

    def __init__(self) -> None:
        super().__init__()

        self._t0_ms: int | None = None
        self._ts: deque[float] = deque()
        self._temp: deque[float] = deque()
        self._heap: deque[float] = deque()
        self._rssi: deque[float] = deque()

        self._temp_plot = self.addPlot(row=0, col=0, title="Temperature (°C)")
        self._temp_curve = self._temp_plot.plot(pen=_TEMP_PEN)

        self._heap_plot = self.addPlot(row=1, col=0, title="Free heap (bytes)")
        self._heap_curve = self._heap_plot.plot(pen=_HEAP_PEN)

        self._rssi_plot = self.addPlot(row=2, col=0, title="RSSI (dBm)")
        self._rssi_curve = self._rssi_plot.plot(pen=_RSSI_PEN)

        for plot in (self._temp_plot, self._heap_plot, self._rssi_plot):
            plot.showGrid(x=True, y=True, alpha=0.3)
            plot.setLabel("bottom", "t (s)")

        self._heap_plot.setXLink(self._temp_plot)
        self._rssi_plot.setXLink(self._temp_plot)

    @Slot(Telemetry)
    def append_sample(self, telemetry: Telemetry) -> None:
        """Append a telemetry sample and trim the rolling window."""
        if self._t0_ms is None:
            self._t0_ms = telemetry.ts

        t_s = (telemetry.ts - self._t0_ms) / 1000.0
        self._ts.append(t_s)
        self._temp.append(telemetry.temp_c)
        self._heap.append(float(telemetry.free_heap))
        self._rssi.append(float(telemetry.rssi))

        while self._ts and (t_s - self._ts[0]) > WINDOW_SECONDS:
            self._ts.popleft()
            self._temp.popleft()
            self._heap.popleft()
            self._rssi.popleft()

        ts = list(self._ts)
        self._temp_curve.setData(ts, list(self._temp))
        self._heap_curve.setData(ts, list(self._heap))
        self._rssi_curve.setData(ts, list(self._rssi))

    def clear_samples(self) -> None:
        """Drop all samples and reset the time origin."""
        self._t0_ms = None
        self._ts.clear()
        self._temp.clear()
        self._heap.clear()
        self._rssi.clear()
        self._temp_curve.setData([], [])
        self._heap_curve.setData([], [])
        self._rssi_curve.setData([], [])

    @property
    def sample_count(self) -> int:
        return len(self._ts)
