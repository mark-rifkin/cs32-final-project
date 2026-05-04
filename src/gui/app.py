from __future__ import annotations

"""GUI application entry point."""

import sys

from PySide6.QtCore import QTimer
from pathlib import Path

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(QFont("Arial", 11))

    logo_path = Path(__file__).resolve().parents[2] / "assets" / "ui" / "logo.png"
    app.setWindowIcon(QIcon(str(logo_path)))

    window = MainWindow()
    window.setWindowIcon(QIcon(str(logo_path)))
    window.show()

    # Start intro loading / startup preload after the event loop is running.
    QTimer.singleShot(0, window.start)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
