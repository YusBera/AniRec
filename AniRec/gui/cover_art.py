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
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap


# How far the backdrop is scaled down before being scaled back up. The result
# is a cheap, wide blur: no convolution, one bilinear pass each way, and it
# runs on every cover in the grid without being noticeable.
BACKDROP_DIVISOR = 14

# How much of the ground is laid over the backdrop. Enough that the blurred
# copy reads as a lit recess behind the artwork rather than as a second,
# competing picture.
BACKDROP_DIM = 0.62

# The colour the backdrop is dimmed toward. Not a token import: this module is
# used by the card, the row and the dialog, and a painted pixmap cannot ask
# the stylesheet what the recess is currently set to.
BACKDROP_GROUND = QColor("#040806")


def _backdrop(source: QPixmap, width: int, height: int) -> QPixmap:
    """A blurred, dimmed copy of the artwork, filling the whole frame."""
    small = source.scaled(
        max(1, width // BACKDROP_DIVISOR),
        max(1, height // BACKDROP_DIVISOR),
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    blurred = small.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    canvas = QPixmap(width, height)
    canvas.fill(BACKDROP_GROUND)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.drawPixmap(
        (width - blurred.width()) // 2,
        (height - blurred.height()) // 2,
        blurred,
    )
    dim = QColor(BACKDROP_GROUND)
    dim.setAlphaF(BACKDROP_DIM)
    painter.fillRect(0, 0, width, height, dim)
    painter.end()
    return canvas


def rounded_cover(source: QPixmap, width: int, height: int, radius: int) -> QPixmap:
    """Return ``source`` whole, on a backdrop that fills the frame.

    Two requirements that look contradictory and are not. Nothing may be cut
    off - anime key art prints title lockups and faces hard against an edge,
    and a centre crop takes the top of someone's head off. And nothing may be
    empty - a letterboxed cover leaves bands of chrome around the one thing
    the grid exists to show, and gives the match plate no picture to sit on.

    A fit-to-frame crop satisfies the second and breaks the first; a contain
    fit does the reverse. So the frame is filled by a blurred, dimmed copy of
    the same artwork and the artwork itself is drawn over it at its true
    aspect ratio, entire. Every pixel of the frame is painted, and every pixel
    of the cover is visible.
    """
    canvas = QPixmap(width, height)
    canvas.fill(Qt.GlobalColor.transparent)
    if source.isNull() or width <= 0 or height <= 0:
        return canvas

    fitted = source.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.setClipPath(clip)
    # Only worth painting when the artwork does not already cover the frame.
    if fitted.width() < width or fitted.height() < height:
        painter.drawPixmap(0, 0, _backdrop(source, width, height))
    painter.drawPixmap(
        (width - fitted.width()) // 2,
        (height - fitted.height()) // 2,
        fitted,
    )
    painter.end()
    return canvas
