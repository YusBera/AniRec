"""Ranking engine adapters and conservative fallback routing."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
import hashlib
import json
import logging
import math
from pathlib import Path
from time import perf_counter

import pandas as pd

try:
    from ..title_utils import normalize_title_key
    from .contracts import (
        RANKING_INPUT_SCHEMA_VERSION,
        RankingEngine,
        RankingEngineMetadata,
        RankingRequest,
        RankingResult,
    )
    from .eligibility import EligibilityContext
    from .explanation import (
        MODEL_RANK_COLUMN,
        RANKED_COUNT_COLUMN,
        explain_counterfactual_removal,
        unavailable_explanation,
    )
except ImportError:  # Compatibility with the sibling import path used by tests.
    from title_utils import normalize_title_key
    from scoring.contracts import (
        RANKING_INPUT_SCHEMA_VERSION,
        RankingEngine,
        RankingEngineMetadata,
        RankingRequest,
        RankingResult,
    )
    from scoring.eligibility import EligibilityContext
    from scoring.explanation import (
        MODEL_RANK_COLUMN,
        RANKED_COUNT_COLUMN,
        explain_counterfactual_removal,
        unavailable_explanation,
    )


_LOG = logging.getLogger(__name__)


class RankingEngineUnavailable(RuntimeError):
    """The selected engine cannot perform inference in this environment."""


class IncompatibleRankingEngine(RankingEngineUnavailable):
    """The engine and request use incompatible contracts or feature schemas."""


class HeuristicRankingEngine:
    """Adapter that preserves AniRec's current explainable ranking behavior.

    Returns the ordered candidate pool; the feed is selected afterwards by the
    shared policy in ``scoring.selection``.
    """

    engine_id = "heuristic"
    engine_version = "1"
    feature_schema_version = "heuristic-v1"

    def rank(self, request: RankingRequest) -> RankingResult:
        # Import after scoring has initialized; recommendation_system imports
        # scoring helpers and must also be importable first in a fresh process.
        if __package__ == "scoring":  # Legacy top-level scoring package.
            from recommendation_system import rank_candidate_pool
        else:
            from ..recommendation_system import rank_candidate_pool

        if request.input_schema_version != RANKING_INPUT_SCHEMA_VERSION:
            raise IncompatibleRankingEngine(
                "The heuristic engine does not support ranking input schema "
                f"{request.input_schema_version!r}."
            )

        candidates = pd.DataFrame.from_records(
            request.candidates,
            columns=list(request.candidate_columns) or None,
        )
        profile = pd.DataFrame.from_records(
            request.taste_profile,
            columns=list(request.profile_columns) or None,
        )
        started = perf_counter()
        ranked = rank_candidate_pool(
            candidates,
            profile,
            num_recommendations=request.parameters.recommendation_count,
            top_anime_count=request.parameters.candidate_pool_size,
            genre_adjustments=dict(request.taste_adjustments),
            excluded_mal_ids=set(request.excluded_mal_ids),
            excluded_titles=set(request.excluded_titles),
            minimum_mean_score=request.parameters.minimum_mean_score,
            collaborative_scores=dict(request.collaborative_scores),
        )
        elapsed_ms = (perf_counter() - started) * 1000.0
        return RankingResult(
            ranked_candidates=tuple(ranked.to_dict("records")),
            columns=tuple(str(column) for column in ranked.columns),
            metadata=RankingEngineMetadata(
                engine_id=self.engine_id,
                engine_version=self.engine_version,
                feature_schema_version=self.feature_schema_version,
                explanation_type="exact-additive",
                inference_ms=elapsed_ms,
            ),
        )


class OnnxSequenceRankingEngine:
    """Rank AniRec candidates with a versioned AniRecTrainer SASRec bundle."""

    engine_id = "sasrec-onnx"
    feature_schema_version = "anirec-sasrec-history-v1"
    requires_user_history = True

    _TYPE_COMPLETED = 1
    _TYPE_WATCHING = 2
    _TYPE_WATCHING_NO_PROGRESS = 3
    _TYPE_PLAN_TO_WATCH = 4
    _TYPE_DROPPED = 5
    _TYPE_ON_HOLD = 6
    _TYPE_UNKNOWN = 7
    _STATUS_BY_TYPE = {
        1: "completed", 2: "watching", 3: "watching", 4: "plan_to_watch",
        5: "dropped", 6: "on_hold", 7: None,
    }

    def __init__(self, bundle: str | Path, *, session_factory=None) -> None:
        self._bundle = Path(bundle).expanduser().resolve()
        self._session_factory = session_factory
        self._bundle_loaded = False
        self._loaded = False

    def candidate_catalog(
        self,
        *,
        include_nsfw: bool = False,
        as_of: date | None = None,
    ) -> tuple[dict, ...]:
        """Return the frozen, model-aligned catalogue eligible for serving."""
        self._ensure_bundle_loaded()
        cutoff = as_of or date.today()
        rows = []
        for position, source in enumerate(self._catalog):
            if not bool(self._candidate_mask[position]):
                continue
            start_date = str(source.get("start_date") or "").strip()
            try:
                released = date.fromisoformat(start_date)
            except ValueError:
                continue
            status = str(source.get("airing_status") or "").strip()
            if released > cutoff or status.casefold() == "not yet aired":
                continue
            rating = str(source.get("content_rating") or "").strip()
            if not include_nsfw and rating.startswith(("R+", "Rx")):
                continue
            mal_id = int(self._items[position])
            episodes = self._positive_int(source.get("episodes"))
            english = str(source.get("title_english") or "").strip() or None
            rows.append(
                {
                    "Anime ID": mal_id,
                    "Title": str(source.get("title") or "").strip(),
                    "English Title": english,
                    "Alternative Titles": [english] if english else [],
                    "Genres": list(source.get("genres") or ()),
                    "Mean Score": None,
                    "Picture URL": None,
                    "Large Picture URL": None,
                    "Episodes": episodes,
                    "Anime Status": status,
                    "Start Date": start_date,
                    "End Date": None,
                    "Year": released.year,
                    "Synopsis": None,
                    "MAL URL": f"https://myanimelist.net/anime/{mal_id}",
                    "Studios": list(source.get("studios") or ()),
                    "Source": source.get("source"),
                    "Media Type": source.get("media_type"),
                    "Scoring Users": None,
                    "Content Rating": rating or None,
                    "Catalog Members": source.get("members"),
                    "Catalog Popularity": source.get("popularity"),
                }
            )
        return tuple(rows)

    def eligibility_context(self) -> EligibilityContext:
        """Expose versioned catalogue policy data without exposing model tensors."""
        self._ensure_bundle_loaded()
        return self._eligibility_context

    @property
    def engine_version(self) -> str:
        # The manifest names the checkpoint as soon as the bundle is read; the
        # model session is not needed for that. Reporting "unloaded" until
        # the first ranking made every refresh after a restart look like a
        # model change (D-018).
        if not self._bundle_loaded:
            return "unloaded"
        checkpoint = self._manifest.get("checkpoint", {})
        return str(checkpoint.get("sha256") or "unknown")[:12]

    def rank(self, request: RankingRequest) -> RankingResult:
        if request.input_schema_version != RANKING_INPUT_SCHEMA_VERSION:
            raise IncompatibleRankingEngine(
                "The sequence engine does not support ranking input schema "
                f"{request.input_schema_version!r}."
            )
        self._ensure_loaded()
        if not request.user_history:
            raise IncompatibleRankingEngine(
                "The sequence model requires current MyAnimeList history."
            )

        import numpy as np

        history_ids = self._known_history_ids(request.user_history)
        inputs = self._history_inputs(request.user_history)
        consumed_history_ids = self._consumed_history_ids(request.user_history)
        started = perf_counter()
        try:
            logits = self._session.run(
                ["logits"],
                {
                    "items": inputs[0],
                    "types": inputs[1],
                    "scores": inputs[2],
                },
            )[0]
        except Exception as error:
            raise RankingEngineUnavailable(
                "The sequence model could not run in this environment."
            ) from error
        elapsed_ms = (perf_counter() - started) * 1000.0
        scores = np.asarray(logits, dtype=np.float32)
        if scores.shape != (1, len(self._items)) or not np.isfinite(scores).all():
            raise RankingEngineUnavailable("The sequence model returned invalid scores.")

        eligible = [
            (float(scores[0, position]), mean, mal_id, title, dict(row))
            for position, mean, mal_id, title, row in self._eligible_candidates(
                request, history_ids, consumed_history_ids
            )
        ]
        if not eligible:
            raise RankingEngineUnavailable(
                "No current candidates are covered by the installed sequence model."
            )

        eligible.sort(key=lambda value: (-value[0], -value[1], value[2], value[3]))
        pool_limit = max(
            request.parameters.recommendation_count,
            request.parameters.candidate_pool_size,
        )
        # The ordered pool is returned; the shared selection policy in
        # ``scoring.selection`` picks the feed from it after ranking.
        pool = eligible[:pool_limit]
        ranked_rows = []
        for global_rank, (raw_score, _mean, _mal_id, _title, row) in enumerate(pool):
            row.update(
                {
                    "Recommendation Score": raw_score,
                    "Match Score": 0.0,
                    "Match Score Available": False,
                    "Genre Contributions": [],
                    "Contributing Genres": [],
                    "Recommendation Reason": (
                        "Sequential-model pick based on your MAL activity "
                        f"(candidate rank {global_rank + 1})."
                    ),
                    MODEL_RANK_COLUMN: global_rank + 1,
                    RANKED_COUNT_COLUMN: len(eligible),
                }
            )
            ranked_rows.append(row)
        columns = tuple(dict.fromkeys(
            (*request.candidate_columns, "Recommendation Score", "Match Score",
             "Match Score Available",
             "Genre Contributions", "Contributing Genres", "Recommendation Reason",
             MODEL_RANK_COLUMN, RANKED_COUNT_COLUMN)
        ))
        return RankingResult(
            ranked_candidates=tuple(ranked_rows),
            columns=columns,
            metadata=RankingEngineMetadata(
                engine_id=self.engine_id,
                engine_version=self.engine_version,
                feature_schema_version=self.feature_schema_version,
                explanation_type="sequence-score",
                inference_ms=elapsed_ms,
            ),
            warnings=(
                "MAL list update times approximate viewing order; the model score is not a calibrated match percentage.",
                "Later-released entries with reciprocal MAL prequel/sequel relations require a consumed direct prequel.",
            ),
        )

    def explain(self, request: RankingRequest, rows) -> list[dict]:
        """Explain each served row by removing parts of the reader's history.

        For every genre among the reader's history titles, and for every
        single history title, the model is rerun without those titles and the
        pick's score and rank are measured again among the same eligible
        candidates. Deterministic: no sampling. A failure must not cost the
        reader their feed, so it yields an honest "unavailable".
        """
        try:
            return self._explain(request, rows)
        except Exception:  # noqa: BLE001 - an explanation never breaks a feed
            _LOG.warning("Sequence-model explanation failed.", exc_info=True)
            return [unavailable_explanation("explanation-failed") for _row in rows]

    def _explain(self, request, rows) -> list[dict]:
        import numpy as np

        self._ensure_loaded()
        history_ids = self._known_history_ids(request.user_history)
        consumed_history_ids = self._consumed_history_ids(request.user_history)
        eligible = self._eligible_candidates(request, history_ids, consumed_history_ids)
        events = self._history_events(request.user_history)
        column_by_position = {
            position: column for column, (position, *_rest) in enumerate(eligible)
        }
        targets = [
            column_by_position.get(
                self._position_by_mal_id.get(self._positive_int(row.get("Anime ID")))
            )
            for row in rows
        ]
        if not events or not any(target is not None for target in targets):
            return [unavailable_explanation("explanation-unavailable") for _row in rows]

        history = []
        for item, event_type, rating in events:
            source = self._catalog[item - 1]
            history.append(
                {
                    "mal_id": int(self._items[item - 1]),
                    "title": str(source.get("title") or "").strip(),
                    "genres": list(
                        dict.fromkeys(
                            text
                            for genre in source.get("genres") or ()
                            if (text := str(genre).strip())
                        )
                    ),
                    "user_score": float(rating) if rating > 0 else None,
                    "list_status": self._STATUS_BY_TYPE.get(event_type),
                }
            )
        members: dict[tuple[str, str], list[int]] = {}
        for index, title in enumerate(history):
            for key in [("history-group", genre) for genre in title["genres"]] or [
                ("history-other", "Titles without genres")
            ]:
                members.setdefault(key, []).append(index)
        groups = sorted(members.items(), key=lambda item: (item[0][0], item[0][1].casefold()))

        # One run each, batch size one, exactly as ``rank`` runs the model, so
        # the full-history run reproduces the ranking score bit for bit.
        sequences = [events]
        sequences += [
            [event for index, event in enumerate(events) if index not in set(group)]
            for _key, group in groups
        ]
        sequences += [events[:index] + events[index + 1 :] for index in range(len(events))]
        positions = np.asarray([position for position, *_rest in eligible], dtype=np.int64)
        scores = np.empty((len(sequences), len(eligible)), dtype=np.float32)
        for row_index, sequence in enumerate(sequences):
            items, types, ratings = self._pack([sequence])
            logits = np.asarray(
                self._session.run(
                    ["logits"], {"items": items, "types": types, "scores": ratings}
                )[0],
                dtype=np.float32,
            )
            if logits.shape != (1, len(self._items)) or not np.isfinite(logits).all():
                raise RankingEngineUnavailable("The sequence model returned invalid scores.")
            scores[row_index] = logits[0, positions]

        # Ranks use the engine's own order: score, then community mean, MAL ID
        # and title, the same key ``rank`` sorts by.
        tiebreak = np.empty(len(eligible), dtype=np.int64)
        tiebreak[
            sorted(
                range(len(eligible)),
                key=lambda column: (-eligible[column][1], eligible[column][2], eligible[column][3]),
            )
        ] = np.arange(len(eligible))

        def rank_of(run, column):
            score = scores[run, column]
            ahead = scores[run] > score
            tied = (scores[run] == score) & (tiebreak < tiebreak[column])
            return int(ahead.sum() + tied.sum()) + 1

        group_offset, title_offset = 1, 1 + len(groups)
        effects = []
        for column in targets:
            if column is None:
                effects.append(None)
                continue
            full = float(scores[0, column])
            effects.append(
                {
                    "full_score": full,
                    "full_rank": rank_of(0, column),
                    "groups": [
                        (
                            kind,
                            label,
                            group,
                            full - float(scores[group_offset + index, column]),
                            rank_of(group_offset + index, column),
                        )
                        for index, ((kind, label), group) in enumerate(groups)
                    ],
                    "titles": [
                        (
                            full - float(scores[title_offset + index, column]),
                            rank_of(title_offset + index, column),
                        )
                        for index in range(len(history))
                    ],
                }
            )
        return [
            explain_counterfactual_removal(history, effect, pool_size=len(eligible))
            if effect is not None
            else unavailable_explanation("outside-ranked-candidates")
            for effect in effects
        ]

    def _eligible_candidates(self, request, history_ids, consumed_history_ids):
        """The candidates ``rank`` may order, in input order, first copy only."""
        excluded_titles = {
            key
            for value in request.excluded_titles
            if (key := normalize_title_key(value))
        }
        eligible = []
        seen_candidates = set()
        for row in request.candidates:
            mal_id = self._positive_int(row.get("Anime ID"))
            if mal_id is None or mal_id in history_ids or mal_id in request.excluded_mal_ids:
                continue
            if mal_id in seen_candidates:
                continue
            seen_candidates.add(mal_id)
            position = self._position_by_mal_id.get(mal_id)
            if position is None or not bool(self._candidate_mask[position]):
                continue
            prerequisites = self._prerequisites_by_position.get(position)
            if prerequisites and prerequisites.isdisjoint(consumed_history_ids):
                continue
            if excluded_titles and normalize_title_key(row.get("Title")) in excluded_titles:
                continue
            mean_score = self._finite_float(row.get("Mean Score"))
            if (
                request.parameters.minimum_mean_score is not None
                and (mean_score is None or mean_score < request.parameters.minimum_mean_score)
            ):
                continue
            eligible.append(
                (
                    position,
                    mean_score if mean_score is not None else -math.inf,
                    mal_id,
                    str(row.get("Title") or ""),
                    row,
                )
            )
        return eligible

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._ensure_bundle_loaded()
        try:
            factory = self._session_factory
            if factory is None:
                import onnxruntime as ort

                factory = lambda path: ort.InferenceSession(
                    str(path), providers=["CPUExecutionProvider"]
                )
            self._session = factory(self._bundle / "model.onnx")
            self._loaded = True
        except RankingEngineUnavailable:
            raise
        except Exception as error:
            raise RankingEngineUnavailable(
                "The sequence model could not start in this environment."
            ) from error

    def _ensure_bundle_loaded(self) -> None:
        if self._bundle_loaded:
            return
        try:
            import numpy as np

            manifest_path = self._bundle / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("bundle_version") != 3 or manifest.get("format") != "onnx":
                raise ValueError("unsupported bundle manifest")
            if not manifest.get("parity", {}).get("parity_pass"):
                raise ValueError("bundle parity is not verified")
            for name in (
                "model.onnx",
                "items.npy",
                "candidate_mask.npy",
                "prerequisites.npz",
                "catalog.json",
            ):
                path = self._bundle / name
                expected = manifest.get("files", {}).get(name, {}).get("sha256")
                if not expected or self._sha256(path) != expected:
                    raise ValueError(f"bundle hash mismatch: {name}")
            items = np.load(self._bundle / "items.npy", allow_pickle=False)
            candidate_mask = np.load(
                self._bundle / "candidate_mask.npy", allow_pickle=False
            )
            if items.ndim != 1 or candidate_mask.shape != items.shape:
                raise ValueError("bundle item arrays are incompatible")
            expected_items = int(manifest.get("data", {}).get("n_items", -1))
            if len(items) != expected_items or len(set(map(int, items))) != len(items):
                raise ValueError("bundle item catalogue is invalid")
            catalog = json.loads(
                (self._bundle / "catalog.json").read_text(encoding="utf-8")
            )
            if (
                not isinstance(catalog, list)
                or len(catalog) != len(items)
                or any(
                    not isinstance(row, dict)
                    or self._positive_int(row.get("anime_id")) != int(items[position])
                    or not str(row.get("title") or "").strip()
                    for position, row in enumerate(catalog)
                )
            ):
                raise ValueError("bundle serving catalogue is invalid")
            self._manifest = manifest
            self._items = items.astype(np.int64, copy=False)
            self._candidate_mask = candidate_mask.astype(bool, copy=False)
            self._catalog = tuple(catalog)
            self._position_by_mal_id = {
                int(mal_id): position for position, mal_id in enumerate(self._items)
            }
            prerequisite_data = np.load(
                self._bundle / "prerequisites.npz", allow_pickle=False
            )
            candidate = prerequisite_data["candidate"]
            prequel = prerequisite_data["prequel"]
            if (
                candidate.ndim != 1
                or prequel.shape != candidate.shape
                or ((candidate < 0) | (candidate >= len(items))).any()
                or ((prequel < 0) | (prequel >= len(items))).any()
                or (candidate == prequel).any()
            ):
                raise ValueError("bundle prerequisite relations are invalid")
            prerequisites_by_position = {}
            for candidate_position, prequel_position in zip(candidate, prequel):
                prerequisites_by_position.setdefault(
                    int(candidate_position), set()
                ).add(int(self._items[int(prequel_position)]))
            self._prerequisites_by_position = {
                key: frozenset(value)
                for key, value in prerequisites_by_position.items()
            }
            files = manifest.get("files", {})
            catalogue_fingerprint = ":".join(
                str(files.get(name, {}).get("sha256") or "missing")[:12]
                for name in ("catalog.json", "candidate_mask.npy", "prerequisites.npz")
            )
            prerequisite_ids = {
                int(self._items[position]): frozenset(prequels)
                for position, prequels in self._prerequisites_by_position.items()
            }
            self._eligibility_context = EligibilityContext(
                catalog_version=f"onnx-v3:{catalogue_fingerprint}",
                catalog_by_mal_id={
                    int(self._items[position]): dict(row)
                    for position, row in enumerate(self._catalog)
                },
                covered_mal_ids=frozenset(
                    int(self._items[position])
                    for position in range(len(self._items))
                    if bool(self._candidate_mask[position])
                ),
                prerequisites_by_mal_id=prerequisite_ids,
                strict_release_dates=True,
            )
            self._sequence_length = int(manifest.get("contract", {}).get(
                "sequence_length", manifest.get("model", {}).get("maxlen", 0)
            ))
            if self._sequence_length <= 0:
                raise ValueError("bundle sequence length is invalid")
            self._bundle_loaded = True
        except RankingEngineUnavailable:
            raise
        except Exception as error:
            raise RankingEngineUnavailable(
                "The installed sequence-model bundle is unavailable or invalid."
            ) from error

    def _known_history_ids(self, history) -> set[int]:
        return {
            mal_id
            for row in history
            if (mal_id := self._positive_int(row.get("Anime ID"))) is not None
        }

    def _consumed_history_ids(self, history) -> set[int]:
        consumed = set()
        for row in history:
            mal_id = self._positive_int(row.get("Anime ID"))
            if mal_id is None:
                continue
            episodes = self._nonnegative_int(row.get("Episodes Watched"))
            event_type = self._interaction_type(
                row.get("Status"), episodes, row.get("Is Rewatching")
            )
            if event_type in {self._TYPE_COMPLETED, self._TYPE_WATCHING}:
                consumed.add(mal_id)
        return consumed

    def _history_inputs(self, history):
        import numpy as np

        events = []
        seen = set()
        for row in history:
            mal_id = self._positive_int(row.get("Anime ID"))
            dense_position = self._position_by_mal_id.get(mal_id)
            if dense_position is None:
                continue
            if mal_id in seen:
                raise IncompatibleRankingEngine(
                    "MyAnimeList history contains duplicate anime IDs."
                )
            seen.add(mal_id)
            updated_at = str(row.get("Updated At") or "").strip()
            if not updated_at:
                raise IncompatibleRankingEngine(
                    "MyAnimeList history is missing update timestamps."
                )
            episodes = self._nonnegative_int(row.get("Episodes Watched"))
            score = self._bounded_score(row.get("User Score"))
            event_type = self._interaction_type(
                row.get("Status"), episodes, row.get("Is Rewatching")
            )
            # AniRecTrainer orders equal timestamps by MAL anime ID.
            events.append((updated_at, mal_id, dense_position + 1, event_type, score))
        if not events:
            raise IncompatibleRankingEngine(
                "No history entries are covered by the installed sequence model."
            )
        events.sort(key=lambda value: (value[0], value[1]))
        return self._pack([events[-self._sequence_length :]])

    def _history_events(self, history):
        """The model-input events, oldest first, exactly as ``rank`` feeds them."""
        import numpy as np

        items, types, scores = self._history_inputs(history)
        return [
            (int(items[0, offset]), int(types[0, offset]), int(scores[0, offset]))
            for offset in range(items.shape[1])
            if items[0, offset]
        ]

    def _pack(self, sequences):
        """Left-pad event lists into one model batch, as training did."""
        import numpy as np

        batch = len(sequences)
        inputs = [
            np.zeros((batch, self._sequence_length), dtype=np.int64) for _ in range(3)
        ]
        for row, events in enumerate(sequences):
            start = self._sequence_length - len(events)
            for offset, event in enumerate(events, start=start):
                inputs[0][row, offset] = event[-3]
                inputs[1][row, offset] = event[-2]
                inputs[2][row, offset] = event[-1]
        return tuple(inputs)

    def _interaction_type(self, status, episodes: int, rewatch) -> int:
        if self._truthy(rewatch):
            return self._TYPE_WATCHING
        key = str(status or "").strip().casefold().replace("-", "_").replace(" ", "_")
        if key == "completed":
            return self._TYPE_COMPLETED
        if key == "watching":
            return self._TYPE_WATCHING if episodes > 0 else self._TYPE_WATCHING_NO_PROGRESS
        if key == "plan_to_watch":
            return self._TYPE_PLAN_TO_WATCH
        if key == "dropped":
            return self._TYPE_DROPPED
        if key == "on_hold":
            return self._TYPE_ON_HOLD
        return self._TYPE_UNKNOWN

    @staticmethod
    def _positive_int(value) -> int | None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _nonnegative_int(value) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError) as error:
            raise IncompatibleRankingEngine(
                "MyAnimeList history contains invalid episode progress."
            ) from error
        if number < 0:
            raise IncompatibleRankingEngine(
                "MyAnimeList history contains negative episode progress."
            )
        return number

    @staticmethod
    def _bounded_score(value) -> int:
        try:
            score = int(value)
        except (TypeError, ValueError) as error:
            raise IncompatibleRankingEngine(
                "MyAnimeList history contains an invalid personal score."
            ) from error
        if not 0 <= score <= 10:
            raise IncompatibleRankingEngine(
                "MyAnimeList history contains a personal score outside 0..10."
            )
        return score

    @staticmethod
    def _truthy(value) -> bool:
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes"}
        return bool(value)

    @staticmethod
    def _finite_float(value) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while block := handle.read(8 << 20):
                digest.update(block)
        return digest.hexdigest()


class FallbackRankingEngine:
    """Try a preferred engine and fall back only for availability failures.

    Programming and data errors are intentionally not swallowed. A future
    model adapter should translate missing artifacts, incompatible schemas,
    timeouts, and runtime startup failures into RankingEngineUnavailable.
    """

    engine_id = "fallback-router"

    def __init__(self, preferred: RankingEngine, fallback: RankingEngine) -> None:
        self._preferred = preferred
        self._fallback = fallback

    @property
    def preferred_engine(self) -> RankingEngine:
        return self._preferred

    @property
    def fallback_engine(self) -> RankingEngine:
        return self._fallback

    @property
    def requires_user_history(self) -> bool:
        return bool(getattr(self._preferred, "requires_user_history", False))

    def candidate_catalog(self, **kwargs):
        provider = getattr(self._preferred, "candidate_catalog", None)
        if not callable(provider):
            return None
        try:
            return provider(**kwargs)
        except RankingEngineUnavailable:
            return None

    def eligibility_context(self) -> EligibilityContext:
        provider = getattr(self._preferred, "eligibility_context", None)
        if not callable(provider):
            return EligibilityContext()
        try:
            return provider()
        except RankingEngineUnavailable:
            return EligibilityContext()

    def explain(self, request: RankingRequest, rows) -> list[dict]:
        """Explain rows the preferred engine ranked (fallback rows are additive)."""
        explain = getattr(self._preferred, "explain", None)
        if not callable(explain):
            return [unavailable_explanation("engine-cannot-explain") for _row in rows]
        return explain(request, rows)

    def rank(self, request: RankingRequest) -> RankingResult:
        try:
            return self._preferred.rank(request)
        except RankingEngineUnavailable as error:
            fallback_request = request
            fallback_candidates = request.context.get("fallback_candidates")
            if fallback_candidates is not None:
                fallback_context = dict(request.context)
                if "fallback_eligibility" in fallback_context:
                    fallback_context["eligibility"] = fallback_context[
                        "fallback_eligibility"
                    ]
                fallback_request = replace(
                    request,
                    candidates=tuple(fallback_candidates),
                    candidate_columns=tuple(
                        request.context.get("fallback_candidate_columns") or ()
                    ),
                    context=fallback_context,
                )
            result = self._fallback.rank(fallback_request)
            return replace(
                result,
                metadata=replace(
                    result.metadata,
                    fallback_used=True,
                    requested_engine_id=self._preferred.engine_id,
                ),
                warnings=(*result.warnings, str(error)),
            )
