"""Nothing in the interface may open an accidental top-level window.

Addresses: BUG1 (blank windows flashing open and shut on almost any click).

In Qt a widget with no parent *is* a window. Two ordinary-looking mistakes
open one by accident:

1. Making a widget visible before a layout has adopted it. The card's
   secondary title label was created parentless and then given
   ``setVisible(True)``, so every title whose English name differs from its
   romaji one opened a window while the card was being built.

2. Detaching a *visible* widget with ``setParent(None)``. Qt hides it
   implicitly, but an implicit hide leaves ``WA_WState_ExplicitShowHide``
   clear, which tells Qt the widget was never deliberately hidden, so it is
   free to show it again once it is a window. It then appears as a blank
   frame with a title bar and vanishes when ``deleteLater`` runs. Liking or
   saving anything refilters the feed and removes cards, which is why this
   fired on nearly every interaction.

The second only reproduces under a real event loop, where the orphan survives
long enough to be re-shown, so timing is not what these tests assert. They
assert the states that make the re-show possible, which is deterministic.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from AniRec.gui import stray_window_guard
from AniRec.gui.recommendation_page import (
    RecommendationExplorerPage,
    RecommendationViewMode,
)
from AniRec.gui_main import create_application
from AniRec.models import Anime, Recommendation
from AniRec.services import RecommendationStateService


EXPLICIT_SHOW_HIDE = Qt.WidgetAttribute.WA_WState_ExplicitShowHide


def _recommendations():
    return tuple(
        Recommendation(
            Anime(
                f"Title {index}",
                mal_id=index,
                english_title=f"English Title {index}",
                genres=("Action", "Drama"),
                mean_score=8.0,
                status="finished_airing",
                episodes=12,
                year=2020,
                cover_url=f"https://cdn.example.test/{index}.jpg",
            ),
            match_score=90 - index,
            rank=index,
        )
        for index in range(1, 6)
    )


def _shown_page(system_temp_dir, view_mode, application):
    page = RecommendationExplorerPage(
        state_service=RecommendationStateService(root_override=system_temp_dir)
    )
    page.set_profile("profile-a")
    page.set_view_mode(view_mode)
    page.set_recommendations(_recommendations())
    page.show()
    for _ in range(3):
        application.processEvents()
    return page


def _assert_safely_detached(widget, label: str) -> None:
    assert widget.parent() is None, f"{label} was expected to be detached"
    assert widget.isHidden(), f"{label} is still visible after removal"
    assert widget.testAttribute(EXPLICIT_SHOW_HIDE), (
        f"{label} was hidden only implicitly by setParent(None). Qt treats "
        "that as 'never deliberately hidden' and may show it again, which "
        "opens a blank top-level window. Hide it before detaching."
    )


def test_a_removed_card_is_explicitly_hidden_before_it_is_detached(system_temp_dir):
    application = create_application([])
    page = _shown_page(system_temp_dir, RecommendationViewMode.CARDS, application)
    victim = page._cards_by_key[next(iter(page._cards_by_key))]

    page._toggle_hidden(page.visible_models[0])

    _assert_safely_detached(victim, "The removed card")
    page.close()


def test_a_removed_list_row_is_explicitly_hidden_before_it_is_detached(system_temp_dir):
    application = create_application([])
    page = _shown_page(system_temp_dir, RecommendationViewMode.LIST, application)
    victim = page._rows_by_key[next(iter(page._rows_by_key))]

    page._toggle_hidden(page.visible_models[0])

    _assert_safely_detached(victim, "The removed list row")
    page.close()


def test_card_labels_are_parented_the_moment_they_are_created(system_temp_dir):
    """A parentless label given setVisible(True) becomes a window.

    Checked on the helper itself, not on a finished card: by the time a card
    is built its layout has adopted every label, so inspecting one afterwards
    would pass whether or not the label was parented at creation, which is
    the only moment that matters.
    """
    application = create_application([])
    page = _shown_page(system_temp_dir, RecommendationViewMode.CARDS, application)
    card = page._cards_by_key[next(iter(page._cards_by_key))]

    label = card._label("sample", "testLabel")

    assert label.parent() is card, (
        "_label returned a label with no parent. Anything that makes it "
        "visible before a layout adopts it opens a top-level window."
    )
    assert not label.isWindow()
    page.close()


def test_no_stray_windows_appear_while_a_feed_is_filtered(system_temp_dir):
    """Backstop: watches for the symptom itself rather than the state."""
    application = create_application([])
    guard = stray_window_guard.install(application, log=False)
    page = _shown_page(system_temp_dir, RecommendationViewMode.CARDS, application)
    guard.allow(page)
    guard.sightings.clear()

    page._toggle_hidden(page.visible_models[0])
    page._toggle_watch_later(page.visible_models[0])
    for _ in range(3):
        application.processEvents()

    assert guard.sightings == [], "\n".join(str(s) for s in guard.sightings)
    page.close()


def test_rows_and_cards_are_parented_the_moment_they_are_created(system_temp_dir):
    """A feed widget must never exist, even briefly, without a parent.

    A QWidget with no parent is a top-level window by definition, so building
    a row cold and reparenting it afterwards makes Qt map a real frame for
    every one of them: switching to the list view flashes dozens of empty
    "AniRec" windows before the list appears. This is BUG1 in a place the
    original fix did not reach, and it came back once while the rebuild cost
    was being profiled - unparenting looks like an optimisation and is not
    even that. It measured slower.

    Checked on the builders, because the parent at construction is the only
    moment that matters; a finished row has been adopted by its layout either
    way.
    """
    application = create_application([])
    page = _shown_page(system_temp_dir, RecommendationViewMode.LIST, application)
    model = page.visible_models[0]

    row = page._build_row("probe-row", model)
    assert row.parent() is page.list_container, (
        "_build_row returned a row with no parent. Qt maps that as a "
        "top-level window before the layout adopts it."
    )
    assert not row.isWindow()

    card = page._build_card("probe-card", model)
    assert card.parent() is page.card_container
    assert not card.isWindow()
    page.close()


def test_no_stray_windows_appear_while_switching_between_views(system_temp_dir):
    """The symptom itself: rebuilding a view must open nothing.

    The list is the one that regressed, because it is the only view that
    builds a widget per model on every switch. Sixty rows produced sixty
    stray windows.
    """
    application = create_application([])
    guard = stray_window_guard.install(application, log=False)
    page = _shown_page(system_temp_dir, RecommendationViewMode.CARDS, application)
    guard.allow(page)
    guard.sightings.clear()

    for mode in (
        RecommendationViewMode.LIST,
        RecommendationViewMode.TABLE,
        RecommendationViewMode.CARDS,
        RecommendationViewMode.LIST,
    ):
        page.set_view_mode(mode)
        for _ in range(3):
            application.processEvents()

    assert guard.sightings == [], "\n".join(str(s) for s in guard.sightings)
    page.close()


def test_a_fingerprint_module_parents_its_label_before_showing_it(system_temp_dir):
    """The one constructor the original BUG1 sweep did not reach.

    ``setVisible(True)`` on a label the layout has not adopted yet is
    setVisible on a widget with no parent, and a parentless QWidget is a
    top-level window - so opening Profile flashed one empty frame per
    fingerprint reading. Checked on the module rather than on the finished
    page, because the order inside the constructor is the only thing that
    decides it.
    """
    from AniRec.gui.profile_page import FingerprintModule
    from AniRec.gui.taste_profile import FingerprintReading

    application = create_application([])
    guard = stray_window_guard.install(application, log=False)
    guard.sightings.clear()

    module = FingerprintModule(
        FingerprintReading(
            "community-sync", "COMMUNITY SYNC", "72%", label="MOSTLY ALIGNED",
            position=0.72,
        )
    )
    guard.allow(module)
    for _ in range(3):
        application.processEvents()

    assert guard.sightings == [], "\n".join(str(s) for s in guard.sightings)
    for label in module.findChildren(QLabel):
        assert label.parent() is not None
        assert not label.isWindow()


def test_the_guard_ignores_windows_that_are_meant_to_be_windows():
    """A guard that cries wolf is worse than none.

    Watching isWindow() alone flagged every tooltip in the running app, which
    buries a real sighting in noise. Qt gives each top-level widget a window
    *type*; a tooltip and a combo box popup are top-level by design. Only a
    plain Window is the symptom being hunted.
    """
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QLabel, QToolTip

    application = create_application([])
    guard = stray_window_guard.install(application, log=False)
    host = QLabel("host")
    guard.allow(host)
    host.resize(200, 60)
    host.show()
    for _ in range(3):
        application.processEvents()
    guard.sightings.clear()

    QToolTip.showText(QPoint(50, 50), "a tooltip", host)
    for _ in range(4):
        application.processEvents()

    assert guard.sightings == [], "a tooltip is not a stray window"

    orphan = QLabel("orphan", host)
    orphan.show()
    for _ in range(2):
        application.processEvents()
    guard.sightings.clear()
    orphan.setParent(None)
    orphan.setVisible(True)
    for _ in range(3):
        application.processEvents()

    assert len(guard.sightings) == 1, "the guard stopped catching real strays"
    assert guard.sightings[0].window_type == "Window"
    host.close()
