"""UI-independent presentation models, read models and filter vocabulary.

What belongs here is anything that decides *what a surface shows* without
deciding *how it is drawn*: the projection of a domain object into the fields
a card needs, the shapes a payload arrives in, the protocol a surface asks its
data for, and the normalised form of a filter.

These modules used to live in ``AniRec.gui``. None of them ever imported Qt -
``taste_profile`` even documented its caching decision by reference to what "a
React surface would reach for" - but living inside the widget package made
them look like widget code and put a toolkit import between them and any
second client. They are the layer an HTTP API serializes and a React client
consumes, so they sit beside ``services`` rather than inside a frontend.

The rule that keeps this package honest: **nothing here may import from
``AniRec.gui``.** It may import ``models``, ``services``, ``scoring`` and
``infrastructure``; the GUI imports it, not the other way round.
"""

from .compatibility import (
    ComparisonEntry,
    ComparisonScores,
    ComparisonSection,
    CompatibilityProvider,
    CompatibilityReport,
    CompatibilityUnavailable,
    FriendEntry,
    FriendSummary,
    SampleCompatibilityProvider,
    UnavailableCompatibilityProvider,
    UnavailableReason,
    report_from_payload,
    sections_from,
)
from .filters import (
    KIND_LABELS,
    MAXIMUM_GROUP_PROFILES,
    ActiveFilter,
    FilterKind,
    ProfileStatus,
    episode_filter,
    score_filter,
)
from .metadata_index import MetadataCatalog, MetadataSuggestion
from .recommendation_view_model import (
    RecommendationViewModel,
    recommendation_view_models,
)
from .bundle_view_model import BundleViewModel, build_bundles
from .taste_profile import (
    LocalTasteProfileProvider,
    SampleTasteProfileProvider,
    TasteProfile,
    TasteProfileProvider,
    TasteProfileUnavailable,
    UnavailableTasteProfileProvider,
)

__all__ = [
    "ActiveFilter",
    "BundleViewModel",
    "ComparisonEntry",
    "ComparisonScores",
    "ComparisonSection",
    "CompatibilityProvider",
    "CompatibilityReport",
    "CompatibilityUnavailable",
    "FilterKind",
    "FriendEntry",
    "FriendSummary",
    "KIND_LABELS",
    "LocalTasteProfileProvider",
    "MAXIMUM_GROUP_PROFILES",
    "MetadataCatalog",
    "MetadataSuggestion",
    "ProfileStatus",
    "RecommendationViewModel",
    "SampleCompatibilityProvider",
    "SampleTasteProfileProvider",
    "TasteProfile",
    "TasteProfileProvider",
    "TasteProfileUnavailable",
    "UnavailableCompatibilityProvider",
    "UnavailableReason",
    "UnavailableTasteProfileProvider",
    "build_bundles",
    "episode_filter",
    "recommendation_view_models",
    "report_from_payload",
    "score_filter",
    "sections_from",
]
