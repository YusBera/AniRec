"""The HTTP boundary must behave like the desktop, not merely respond.

These assert the properties the Qt client's behaviour was tuned against, so
the two clients cannot drift into disagreeing about the same operation:

* one running operation per key, and a second start refused rather than queued;
* cooperative cancellation that reaches a terminal state;
* the terminal event sequence, in order;
* replay, so a client that subscribes after the work finished still learns
  what happened - the one place HTTP genuinely differs from Qt signals;
* errors that carry the redacted presentable_error model and never a
  traceback.
"""

from __future__ import annotations

import json
import threading

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from AniRec.api import OperationRegistry, create_app  # noqa: E402
from AniRec.api.operations import (  # noqa: E402
    OperationAlreadyRunningError,
    OperationState,
)
from AniRec.errors import NetworkError  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    app = create_app(root_override=str(tmp_path))
    with TestClient(app) as test_client:
        yield test_client


# -- read surface ---------------------------------------------------------


def test_health_reports_ok(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_feed_falls_back_to_the_sample_library_without_a_profile(client):
    payload = client.get("/api/discover/feed").json()
    assert payload["source"] == "sample"
    assert payload["recommendations"], "the bundled sample must produce a feed"
    assert payload["profile"] is None


def test_a_sample_feed_is_ephemeral_and_offers_nowhere_to_persist(tmp_path, client):
    # SampleDataService.profile_id is "__sample__", which paths.profile_dir
    # rejects. The desktop resolves this with set_ephemeral(True); the API has
    # to make the same promise or a vote would 500 on a leading underscore.
    payload = client.get("/api/discover/feed").json()
    assert payload["ephemeral"] is True
    assert payload["state_profile_id"] is None
    assert payload["state"]["liked_mal_ids"] == []


def test_the_feed_serializes_the_presentation_model_unchanged(client):
    from AniRec.presentation import recommendation_view_models
    from AniRec.services import SampleDataService

    result = SampleDataService().load()
    expected = recommendation_view_models(result.recommendations)
    payload = client.get("/api/discover/feed").json()

    assert len(payload["recommendations"]) == len(expected)
    first, model = payload["recommendations"][0], expected[0]
    assert first["display_title"] == model.display_title
    assert first["personal_match"] == pytest.approx(model.personal_match)
    assert tuple(first["genres"]) == model.genres
    assert first["aired_text"] == model.aired_text


def test_the_breakdown_still_sums_to_the_score_over_the_wire(client):
    """The product's one invariant, asserted at the boundary that serializes it."""
    for card in client.get("/api/discover/feed").json()["recommendations"]:
        contributions = card["genre_contributions"]
        if not contributions:
            continue
        total = sum(item["value"] for item in contributions)
        assert total == pytest.approx(card["personal_match"], abs=0.05), card["display_title"]


def test_the_catalogue_offers_the_terms_present_in_the_feed(client):
    payload = client.get("/api/discover/feed").json()
    genres = {genre for card in payload["recommendations"] for genre in card["genres"]}
    assert genres <= set(payload["catalogue"]["genres"])


# -- operation model ------------------------------------------------------


def test_starting_without_a_profile_is_a_conflict_not_a_crash(client):
    response = client.post("/api/operations/recommendation", json={})
    assert response.status_code == 409


def test_an_unknown_kind_is_rejected(client):
    response = client.post("/api/operations/nonsense", json={"profile_id": "someone"})
    assert response.status_code == 404


def test_one_operation_per_key(tmp_path):
    """The guard that stops a second press starting a second run."""
    registry = OperationRegistry()
    release = threading.Event()

    def blocking(_token, _report):
        release.wait(5)
        return {"done": True}

    registry.start("sync:someone", "sync", "someone", blocking)
    with pytest.raises(OperationAlreadyRunningError):
        registry.start("sync:someone", "sync", "someone", blocking)
    release.set()
    assert registry.shutdown()


def test_a_finished_key_can_be_started_again(tmp_path):
    """controller.py's BUG1: a stale handle is retired, not used to refuse."""
    registry = OperationRegistry()
    registry.start("sync:someone", "sync", "someone", lambda _t, _r: 1)
    registry.shutdown()
    record = registry.start("sync:someone", "sync", "someone", lambda _t, _r: 2)
    assert record.is_running or record.state is OperationState.SUCCEEDED
    registry.shutdown()


def test_cancellation_is_cooperative_and_reaches_a_terminal_state():
    registry = OperationRegistry()
    started = threading.Event()

    def cancellable(token, _report):
        started.set()
        for _ in range(500):
            token.raise_if_cancelled()
            threading.Event().wait(0.01)
        return "never"

    record = registry.start("sync:someone", "sync", "someone", cancellable)
    assert started.wait(5)
    assert registry.cancel("sync:someone")
    registry.shutdown()
    assert record.state is OperationState.CANCELLED
    assert [event.event for event in record.events][-2:] == ["cancelled", "finished"]


def test_the_terminal_event_sequence_matches_the_qt_worker_contract():
    from AniRec.models import PipelineProgress

    registry = OperationRegistry()

    def work(_token, report):
        report(PipelineProgress(stage_id="fetch_top", message="Fetching", current=1, total=2))
        return {"ok": True}

    record = registry.start("sync:someone", "sync", "someone", work)
    registry.shutdown()
    sequence = [event.event for event in record.events]
    assert sequence[0] == "started"
    assert sequence[-1] == "finished"
    assert "result" in sequence
    assert sequence.index("progress") < sequence.index("result")


def test_a_failure_carries_the_redacted_model_and_no_traceback():
    registry = OperationRegistry()

    def failing(_token, _report):
        raise NetworkError("Could not connect to MyAnimeList.")

    record = registry.start("sync:someone", "sync", "someone", failing)
    registry.shutdown()
    assert record.state is OperationState.FAILED
    payload = next(event.data for event in record.events if event.event == "error")
    assert set(payload) == {"code", "title", "description", "solution", "retryable"}
    assert "Traceback" not in json.dumps(payload)


def test_the_event_stream_replays_for_a_client_that_arrives_late():
    """The one real difference from Qt signals, and the reason for it.

    A Qt client connects its slots before the worker starts. An HTTP client
    cannot: it learns the id from the response that started the work. Without
    replay it would hang on a stream that has already said everything.
    """
    registry = OperationRegistry()
    record = registry.start("sync:someone", "sync", "someone", lambda _t, _r: {"ok": True})
    registry.shutdown()

    # Subscribing only now, well after the operation finished.
    replayed = [item["event"] for item in record.follow()]
    assert replayed[0] == "started"
    assert replayed[-1] == "finished"


def test_events_are_sequenced_so_a_reconnect_can_be_reconciled():
    registry = OperationRegistry()
    record = registry.start("sync:someone", "sync", "someone", lambda _t, _r: None)
    registry.shutdown()
    sequence = [item["seq"] for item in record.follow()]
    assert sequence == sorted(sequence)
    assert sequence == list(range(len(sequence)))


def test_the_sse_route_emits_named_events(client, tmp_path):
    """A GET on a finished operation must still stream its whole history."""
    registry: OperationRegistry = client.app.state.operations
    registry.start("api-test:someone", "api-test", "someone", lambda _t, _r: {"ok": True})
    registry.shutdown()

    with client.stream("GET", "/api/operations/api-test:someone/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert "event: started" in body
    assert "event: finished" in body


def test_cancelling_an_unknown_operation_is_a_404(client):
    assert client.delete("/api/operations/sync:nobody").status_code == 404


# -- feedback -------------------------------------------------------------


def test_feedback_rejects_a_body_that_does_not_match_the_schema(client):
    """422, not 400: these fail Pydantic validation before any handler runs.

    The distinction is deliberate now that the request body is a declared
    model. A body that does not typecheck is 422 (unprocessable); a body that
    typechecks but is semantically refused by the handler stays 400 - see the
    empty-profile_id test below.
    """
    missing_profile = client.post(
        "/api/discover/feedback", json={"mal_id": 1, "action": "hidden"}
    )
    assert missing_profile.status_code == 422

    bad_id = client.post(
        "/api/discover/feedback",
        json={"profile_id": "someone", "mal_id": "nope", "action": "hidden"},
    )
    assert bad_id.status_code == 422

    unknown_action = client.post(
        "/api/discover/feedback",
        json={"profile_id": "someone", "mal_id": 1, "action": "explode"},
    )
    assert unknown_action.status_code == 422


def test_an_empty_profile_id_is_a_handler_level_rejection(client):
    """Schema-valid, semantically refused: 400, and a readable reason."""
    response = client.post(
        "/api/discover/feedback",
        json={"profile_id": "   ", "mal_id": 1, "action": "hidden"},
    )
    assert response.status_code == 400


def test_every_error_uses_one_envelope_shape(client):
    """A client must not need a second error shape for input rejections."""
    for response in (
        client.post("/api/discover/feedback", json={"mal_id": 1, "action": "hidden"}),
        client.post("/api/discover/feedback", json={"profile_id": " ", "mal_id": 1, "action": "hidden"}),
        client.get("/api/operations/sync:nobody"),
        client.post("/api/operations/nonsense", json={"profile_id": "someone"}),
    ):
        assert response.status_code >= 400
        body = response.json()
        assert "error" in body, body
        assert set(body["error"]) == {
            "code",
            "title",
            "description",
            "solution",
            "retryable",
        }


def test_a_vote_round_trips_through_the_real_state_service(client):
    payload = {
        "profile_id": "someone",
        "mal_id": 1535,
        "action": "watch_later",
        "value": True,
    }
    state = client.post("/api/discover/feedback", json=payload).json()["state"]
    assert state["watch_later_mal_ids"] == [1535]

    payload["value"] = False
    state = client.post("/api/discover/feedback", json=payload).json()["state"]
    assert state["watch_later_mal_ids"] == []


def test_sentiment_is_mutually_exclusive_at_the_boundary(client):
    def vote(sentiment):
        return client.post(
            "/api/discover/feedback",
            json={
                "profile_id": "someone",
                "mal_id": 42,
                "action": "sentiment",
                "sentiment": sentiment,
            },
        ).json()["state"]

    assert vote("liked")["liked_mal_ids"] == [42]
    after = vote("disliked")
    assert after["disliked_mal_ids"] == [42]
    assert after["liked_mal_ids"] == []


# -- the boundary must not import Qt --------------------------------------


def _imported_modules(path):
    """Every module a file imports, absolute and relative alike.

    Parsed rather than grepped. The first version of this test searched the
    raw text and failed on its own package docstring, which explains why the
    modules moved - prose about ``AniRec.gui`` is not an import of it.
    """
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(("." * node.level) + (node.module or ""))
    return names


def test_the_api_never_imports_pyside():
    """A web process must not need a widget toolkit installed to start.

    Checked against the source rather than by importing, because PySide6 is
    installed in this environment: an accidental import would succeed here and
    fail on a server that has no display and no Qt.
    """
    from pathlib import Path

    import AniRec.api as api_package

    for path in Path(api_package.__file__).parent.glob("*.py"):
        for name in _imported_modules(path):
            assert not name.startswith("PySide6"), f"{path.name} imports {name}"
            assert "gui" not in name.split("."), f"{path.name} imports {name}"


def test_the_presentation_package_never_imports_the_gui():
    """The rule that keeps the moved modules honest.

    The dependency runs one way: the GUI imports presentation. If it ever ran
    the other way, the modules would be back where they started and a second
    client would pull in Qt to read a dataclass.
    """
    from pathlib import Path

    import AniRec.presentation as presentation

    for path in Path(presentation.__file__).parent.glob("*.py"):
        for name in _imported_modules(path):
            assert not name.startswith("PySide6"), f"{path.name} imports {name}"
            assert "gui" not in name.split("."), f"{path.name} imports {name}"
            assert not name.startswith("..gui"), f"{path.name} imports {name}"
