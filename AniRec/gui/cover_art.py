"""Fitting cover artwork into a rounded frame.

Addresses: BUG7 (portraits had hard square corners inside rounded cards).

A stylesheet ``border-radius`` styles a widget's own background and border. It
does not clip the pixmap a QLabel draws, so artwork set on a rounded label
still renders as a rectangle and cuts across the corners. The rounding has to
be applied to the image itself, which is what this does.

Every surface that shows a cover goes through here so the card, the list row
and the detail dialog cannot drift apart.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap


def rounded_cover(source: QPixmap, width: int, height: int, radius: int) -> QPixmap:
    """Return ``source`` filling width x height, cropped centrally and rounded.

    KeepAspectRatioByExpanding then centring is a centre crop: the frame is
    always filled and the image is never distorted, which matters because
    cover art is not all the same aspect ratio.
    """
    canvas = QPixmap(width, height)
    canvas.fill(Qt.GlobalColor.transparent)
    if source.isNull() or width <= 0 or height <= 0:
        return canvas

    fitted = source.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.setClipPath(clip)
    painter.drawPixmap(
        (width - fitted.width()) // 2,
        (height - fitted.height()) // 2,
        fitted,
    )
    painter.end()
    return canvas
