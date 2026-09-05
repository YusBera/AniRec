"""Sample mode is ephemeral by design, and that design is load-bearing.

The finding these tests formalize: ``SampleDataService.profile_id`` is
``"__sample__"``, and ``paths.profile_dir`` rejects it, because the profile-ID
pattern requires a leading alphanumeric as a path-traversal guard. The
decision recorded here is to keep the guard and keep sample mode ephemeral,
rather than to carve out an exception so demonstration data can be persisted.

These tests exist so a future change in either direction fails loudly:
loosening the validator to admit the sentinel, or quietly teaching some code
path to write for it anyway.
"""

from __future__ import annotations

import pytest

from AniRec.infrastructure.paths import profile_dir
from AniRec.services import RecommendationStateService, SampleDataService


def test_the_sample_id_is_rejected_as_a_storage_location(tmp_path):
    """The security invariant, stated as a test rather than as a comment."""
    with pytest.raises(ValueError):
        profile_dir(SampleDataService().profile_id, tmp_path)


def test_the_guard_that_rejects_it_is_the_traversal_guard(tmp_path):
    """It is rejected for the same reason "../" is, not by a special case."""
    for hostile in ("..", ".", "../escape", "_leading_underscore"):
        with pytest.raises(ValueError):
            profile_dir(hostile, tmp_path)


def test_a_real_profile_id_is_still_accepted(tmp_path):
    """The guard must not be so broad that ordinary usernames fail."""
    assert profile_dir("kuroboshi", tmp_path).name == "kuroboshi"
    assert profile_dir("user.name-2", tmp_path).name == "user.name-2"


def test_sample_mode_is_recognised_by_a_shared_predicate():
    """Both frontends ask the same question the same way."""
    samples = SampleDataService()
    assert samples.is_sample_profile(samples.profile_id)
    assert not samples.is_sample_profile("kuroboshi")
    assert not samples.is_sample_profile(None)


def test_state_cannot_be_persisted_for_the_sample_library(tmp_path):
    """The consequence, asserted where it would actually bite.

    Any code path that forgets sample mode is ephemeral and tries to write a
    vote for it fails here rather than silently creating a directory whose
    name was never meant to be one.
    """
    service = RecommendationStateService(root_override=tmp_path)
    with pytest.raises(ValueError):
        service.set_watch_later(SampleDataService().profile_id, 1535, True)


def test_the_sample_library_still_loads_without_any_storage(tmp_path):
    """Ephemeral does not mean unavailable: the feed itself must still work."""
    result = SampleDataService().load()
    assert result is not None
    assert result.recommendations
