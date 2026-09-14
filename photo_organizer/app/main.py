"""Photo Organizer desktop app entry point.

FluentWindow shell with a left nav pane hosting three screens: Home,
Sort New Photos, and Sort From Scratch. Each screen is a self-contained
QWidget (see app/widgets/) that can also be instantiated and driven directly
in tests without the surrounding window chrome.
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition, Theme, setTheme

from photo_organizer.app.resource_path import resource_path
from photo_organizer.app.widgets.home_screen import HomeScreen
from photo_organizer.app.widgets.sort_new_screen import SortNewPhotosScreen
from photo_organizer.app.widgets.sort_scratch_screen import SortFromScratchScreen


class MainWindow(FluentWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Photo Organizer")
        self.resize(1000, 720)
        icon_path = resource_path("resources/icon.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        try:
            self.setMicaEffectEnabled(True)
        except Exception:
            pass  # gracefully degrade on platforms/Windows versions without Mica support

        self.sort_new_screen = SortNewPhotosScreen()
        self.sort_scratch_screen = SortFromScratchScreen()
        self.home_screen = HomeScreen(
            on_sort_new=lambda: self.switchTo(self.sort_new_screen),
            on_sort_scratch=lambda: self.switchTo(self.sort_scratch_screen),
        )

        self.addSubInterface(self.home_screen, FluentIcon.HOME, "Home", NavigationItemPosition.TOP)
        self.addSubInterface(self.sort_new_screen, FluentIcon.SYNC, "Sort New Photos", NavigationItemPosition.TOP)
        self.addSubInterface(self.sort_scratch_screen, FluentIcon.BROOM, "Sort From Scratch", NavigationItemPosition.TOP)

    def switchTo(self, widget) -> None:
        self.stackedWidget.setCurrentWidget(widget, popOut=False)
        self.navigationInterface.setCurrentItem(widget.objectName())


def main() -> None:
    app = QApplication(sys.argv)
    setTheme(Theme.AUTO)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
