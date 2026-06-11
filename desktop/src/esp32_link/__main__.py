"""Entry point for the esp32-link desktop application."""

import logging
import os
import sys

from esp32_link.app import build_application
from esp32_link.ui.main_window import MainWindow

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s — %(message)s"


def _configure_logging() -> None:
    level = logging.DEBUG if os.environ.get("ESP32_LINK_DEBUG") == "1" else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, stream=sys.stdout)


def main() -> None:
    _configure_logging()
    app = build_application(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
