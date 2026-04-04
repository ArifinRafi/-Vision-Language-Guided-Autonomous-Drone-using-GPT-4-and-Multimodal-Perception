"""RGB video display widget with decision overlay."""

import numpy as np
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt5.QtGui import QImage, QPixmap, QPainter, QFont, QColor
from PyQt5.QtCore import Qt


class VideoWidget(QWidget):
    """Displays RGB video feed with avoidance decision overlay."""

    def __init__(self, title="RGB Video", parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(2, 2, 2, 2)

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignCenter)
        self._title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #ccc;")
        self._layout.addWidget(self._title_label)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMinimumSize(480, 360)
        self._image_label.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333;")
        self._layout.addWidget(self._image_label)

        self._overlay_text = ""
        self._overlay_color = QColor(0, 255, 0)
        self._distance_text = ""

    def update_frame(self, rgb_frame):
        """Update display with new RGB frame (numpy H,W,3 uint8)."""
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        # Draw overlay
        if self._overlay_text or self._distance_text:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)

            # Distance text (top-center)
            if self._distance_text:
                font = QFont("Consolas", 14, QFont.Bold)
                painter.setFont(font)
                painter.setPen(QColor(255, 255, 0))
                painter.drawText(
                    pixmap.rect().adjusted(0, 10, 0, 0),
                    Qt.AlignHCenter | Qt.AlignTop,
                    self._distance_text
                )

            # Decision overlay (bottom-center)
            if self._overlay_text:
                font = QFont("Consolas", 16, QFont.Bold)
                painter.setFont(font)

                # Background rectangle
                fm = painter.fontMetrics()
                text_rect = fm.boundingRect(self._overlay_text)
                bg_rect = text_rect.adjusted(-10, -5, 10, 5)
                bg_rect.moveCenter(pixmap.rect().center())
                bg_rect.moveBottom(pixmap.height() - 20)

                painter.fillRect(bg_rect, QColor(0, 0, 0, 160))
                painter.setPen(self._overlay_color)
                painter.drawText(bg_rect, Qt.AlignCenter, self._overlay_text)

            painter.end()

        scaled = pixmap.scaled(
            self._image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._image_label.setPixmap(scaled)

    def set_overlay(self, text, color=None):
        """Set the decision overlay text."""
        self._overlay_text = text
        if color:
            self._overlay_color = color

    def set_distance_text(self, text):
        """Set the distance display text."""
        self._distance_text = text

    def clear_overlay(self):
        self._overlay_text = ""
        self._distance_text = ""
