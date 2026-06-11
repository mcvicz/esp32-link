"""QApplication setup and dark theme configuration for the esp32-link UI."""

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def build_application(argv: list[str]) -> QApplication:
    """Create and configure the QApplication with the project-wide dark theme."""
    _configure_pyqtgraph()
    app = QApplication(argv)
    app.setApplicationName("esp32-link")
    app.setOrganizationName("esp32-link")
    app.setStyle("Fusion")
    app.setPalette(_dark_palette())
    return app


def _configure_pyqtgraph() -> None:
    pg.setConfigOption("background", (33, 33, 33))
    pg.setConfigOption("foreground", (220, 220, 220))
    pg.setConfigOption("antialias", True)


def _dark_palette() -> QPalette:
    palette = QPalette()

    bg = QColor(33, 33, 33)
    bg_alt = QColor(45, 45, 45)
    text = QColor(220, 220, 220)
    text_disabled = QColor(127, 127, 127)
    accent = QColor(38, 139, 210)

    palette.setColor(QPalette.ColorRole.Window, bg)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, bg_alt)
    palette.setColor(QPalette.ColorRole.AlternateBase, bg)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, bg_alt)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.ToolTipBase, bg_alt)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, text_disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, text_disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, text_disabled)

    return palette
