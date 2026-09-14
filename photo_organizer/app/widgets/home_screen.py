"""Home screen — two cards, one per flow."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CardWidget, FluentIcon, IconWidget, PrimaryPushButton, SubtitleLabel, TitleLabel


class _FeatureCard(CardWidget):
    def __init__(self, icon: FluentIcon, title: str, description: str, cta: str, on_click: Callable[[], None]) -> None:
        super().__init__()
        self.setFixedHeight(200)

        icon_widget = IconWidget(icon, self)
        icon_widget.setFixedSize(32, 32)

        title_label = SubtitleLabel(title)
        desc_label = BodyLabel(description)
        desc_label.setWordWrap(True)

        btn = PrimaryPushButton(cta)
        btn.clicked.connect(on_click)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.addWidget(icon_widget)
        layout.addWidget(title_label)
        layout.addWidget(desc_label, 1)
        layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft)


class HomeScreen(QWidget):
    def __init__(
        self,
        on_sort_new: Callable[[], None],
        on_sort_scratch: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("homeScreen")

        heading = TitleLabel("Photo Organizer")
        subheading = BodyLabel("Choose what you'd like to do.")

        sort_new_card = _FeatureCard(
            FluentIcon.SYNC,
            "Sort New Photos",
            "For ongoing use: drop new camera imports into a folder and route them "
            "into your Fuji and Photos libraries by date and camera make.",
            "Get Started",
            on_sort_new,
        )
        sort_scratch_card = _FeatureCard(
            FluentIcon.BROOM,
            "Sort From Scratch",
            "One-time bulk reorganize of an entire existing photo library root — "
            "routes everything into Fuji/YYYY/MM and YYYY/MM in a single pass.",
            "Get Started",
            on_sort_scratch,
        )

        cards_row = QHBoxLayout()
        cards_row.setSpacing(20)
        cards_row.addWidget(sort_new_card, 1)
        cards_row.addWidget(sort_scratch_card, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        layout.addWidget(heading)
        layout.addWidget(subheading)
        layout.addSpacing(12)
        layout.addLayout(cards_row)
        layout.addStretch(1)
