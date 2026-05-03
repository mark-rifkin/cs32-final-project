from __future__ import annotations

"""GUI application entry point."""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(QFont("Arial", 11))

    window = MainWindow()
    window.show()

    # Start the first preload only after the event loop is running.
    QTimer.singleShot(0, window.start)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
