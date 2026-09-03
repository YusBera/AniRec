"""What the cover dissolve is allowed to hold on screen."""

from __future__ import annotations

from PySide6.QtGui import QPixmap

from AniRec.gui.cover_art import CoverLabel
from AniRec.gui_main import create_application


def pixmap(width=40, height=60):
    image = QPixmap(width, height)
    image.fill()
    return image


def test_artwork_replacing_a_placeholder_does_not_dissolve():
    """A crossfade holds both images on screen for its whole duration.

    Reordering the two draws cannot change that - any two-layer alpha
    composite is the same blend either way round - so while a dissolve runs,
    the generated plate really is over the artwork it stood in for. Landing a
    screenful at once while scrolling makes that read as placeholders being
    painted on top of the real images.
    """
    create_application([])
    label = CoverLabel()
    label.mark_placeholder()
    label.setPixmap(pixmap())

    label.arm_fade()
    label.setPixmap(pixmap())

    assert label._outgoing is None
    assert label._mix == 0.0


def test_artwork_replacing_artwork_still_dissolves():
    """The case the fade was written for, and the one it keeps.

    The detail view upgrades a small cover to the large one; that is a real
    picture becoming a better picture, and popping between them is the thing
    worth softening.
    """
    create_application([])
    label = CoverLabel()
    label.setPixmap(pixmap())

    label.arm_fade()
    label.setPixmap(pixmap())

    assert label._outgoing is not None
    assert label._mix == 1.0


def test_a_placeholder_arriving_mid_dissolve_cancels_it():
    """The running fade belonged to the pixmap being replaced."""
    create_application([])
    label = CoverLabel()
    label.setPixmap(pixmap())
    label.arm_fade()
    label.setPixmap(pixmap())
    assert label._outgoing is not None

    label.mark_placeholder()
    label.setPixmap(pixmap())

    assert label._outgoing is None
    assert label._mix == 0.0


def test_the_placeholder_mark_is_consumed_by_one_set():
    """Only the pixmap set immediately after the mark is a stand-in.

    Leaving the flag raised would suppress every later dissolve on the label.
    """
    create_application([])
    label = CoverLabel()
    label.mark_placeholder()
    label.setPixmap(pixmap())
    label.setPixmap(pixmap())

    label.arm_fade()
    label.setPixmap(pixmap())

    assert label._outgoing is not None


def test_a_resize_still_never_dissolves():
    """Re-fitting after a scale change sets a pixmap and is not an event."""
    create_application([])
    label = CoverLabel()
    label.setPixmap(pixmap())

    label.setPixmap(pixmap(60, 90))

    assert label._outgoing is None
