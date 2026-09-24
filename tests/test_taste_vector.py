from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from AniRec.api.app import create_app
from AniRec.models.domain import NOT_AVAILABLE, GenreStat
from AniRec.presentation.taste_vector import taste_vector


def stat(genre: str, importance: float, completed: int = 3) -> GenreStat:
    return GenreStat(genre=genre, importance_score=importance, completed_count=completed)


def test_liked_are_the_four_most_positive_terms_in_ranking_order():
    vector = taste_vector(
        [stat("Drama", 20), stat("Action", 50), stat("Comedy", 5),
         stat("Romance", 30), stat("Mystery", 10), stat("Sports", 1)],
        studio_names=[],
    )
    assert [term.term for term in vector.liked] == ["Action", "Romance", "Drama", "Mystery"]


def test_avoided_are_the_two_most_negative_terms_most_negative_first():
    vector = taste_vector(
        [stat("Horror", -40), stat("Drama", 20), stat("Ecchi", -10), stat("Mecha", -25)],
        studio_names=[],
    )
    assert [term.term for term in vector.avoided] == ["Horror", "Mecha"]
    # Zero is neither liked nor avoided.
    assert taste_vector([stat("Slice of Life", 0)], studio_names=[]).liked == ()


def test_a_studio_in_the_ranking_is_typed_as_a_studio_not_a_genre():
    vector = taste_vector(
        [stat("Psychological", 60, completed=11), stat("Madhouse", 40, completed=4)],
        studio_names=["madhouse ", "Kyoto Animation"],
    )
    assert [(term.term, term.kind, term.rated_count) for term in vector.liked] == [
        ("Psychological", "genre", 11),
        ("Madhouse", "studio", 4),
    ]


def test_an_unnamed_term_is_skipped_and_no_ranking_is_an_empty_vector():
    vector = taste_vector([stat(NOT_AVAILABLE, 90), stat("Drama", 10)], studio_names=[])
    assert [term.term for term in vector.liked] == ["Drama"]
    empty = taste_vector([], studio_names=[])
    assert empty.liked == () and empty.avoided == ()


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(root_override=str(tmp_path))) as test_client:
        yield test_client


def test_the_feed_carries_the_taste_vector_the_desktop_header_shows(client):
    from AniRec.services import SampleDataService

    result = SampleDataService().load()
    payload = client.get("/api/discover/feed").json()

    ranked = sorted(result.genre_stats, key=lambda s: -float(s.importance_score or 0))
    expected = [s.genre for s in ranked if float(s.importance_score or 0) > 0][:4]
    liked = payload["taste_vector"]["liked"]
    assert [term["term"] for term in liked] == expected
    assert all(term["kind"] in {"genre", "studio"} for term in liked)
    assert isinstance(payload["taste_vector"]["avoided"], list)
