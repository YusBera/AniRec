# MyAnimeList Data Semantics

This is the checked **local mapping contract** for values that can reach AniRec's
heuristic scorer. It records the upstream field, local representation, and exact
use. Local fixtures prove AniRec's behavior. External facts below also include
the user's 2026-09-22 findings from a structured copy of the MAL API v2 reference;
that copied reference and raw OpenAPI file are not tracked in this repository.

The authoritative external source is the [MyAnimeList API v2
reference](https://myanimelist.net/apiconfig/references/api/v2), Anime object.
Before changing schema or product copy beyond the facts recorded here, recheck
that source or the supplied structured copy. Do not use the raw spec to replace
the working authorization-code login with its obsolete implicit-flow section;
AniRec's PKCE (`plain`) flow is intentional. AniRec requests the fields in
`AniRec/core/mal_mapping.py::ANIME_FIELDS`, maps them once in `anime_from_node`,
and persists mapped values through `anime_to_row`.

| AniRec value | Expected MAL v2 field | Verified local treatment | Scoring use |
| --- | --- | --- | --- |
| `Anime ID` | `id` | Accepted only when positive and stored as external identity | Identity and exclusions; not a score |
| `Genres` | each `genres[].name` | Returned names are preserved as feature labels; AniRec does not infer genre/theme/demographic taxonomy | Binary feature membership |
| `Studios` | each `studios[].name` | Returned names are preserved | Binary feature membership |
| `Source` | `source` | Returned text is preserved | One binary feature |
| `Media Type` | `media_type` | Returned text is preserved | One binary feature and eligibility filtering for Music/CM/PV where available |
| `Year` | year of `start_date`, otherwise `start_season.year` | Derived by AniRec with the stated fallback | One decade bucket feature |
| `Mean Score` | `mean` | Treated by AniRec as a community mean on its quality scale | Quality term only; it is not user taste or popularity |
| `Scoring Users` | `num_scoring_users` | Treated by AniRec as a nonnegative scoring-user count | Confidence for the quality prior |
| `Popularity` / `Rank` | not requested or mapped | No local heuristic input | None |

Missing values are not numeric zero. The reference notes that MAL omits average
score and rank when too few users have rated a title, while `num_episodes == 0`
means the episode count is unknown. AniRec must render and model these as
unavailable values rather than real zeros.

`Idf` and “rarity” are AniRec-derived values, not MyAnimeList data points.
In the serving path, `build_taste_profile` receives the active ranking catalogue,
counts how many rows carry each feature, then computes
`max(log(document_count / (1 + count)), 0.01)`. If called without `catalog`, it
uses the completed-history rows instead. The serialized `Idf` column therefore
means feature rarity within whichever row population built that profile. It must
not be described as MAL popularity, MAL rank, or a global anime statistic.

The user-vector component is `affinity * Idf`. A candidate feature is binary.
The content cosine must consequently use `profile.weight(feature)` once in the
dot product and `sqrt(feature_count)` for the candidate norm. Multiplying by
`Idf` again on the candidate side squares the derived rarity and changes its
meaning.

## Verification boundary

`tests/test_mal_mapping.py` covers node-to-domain-to-CSV mapping, including the
year fallback. `tests/test_anime_data.py` asserts the request field set excludes
rank and popularity. `tests/test_scoring_invariants.py` covers the single-IDF
cosine identity. These are local behavior checks; consult the official reference
for fields not recorded in this document.

The current catalogue population differs by serving configuration: an installed
provider supplies its frozen model-aligned catalogue; a configuration without a
usable provider retains the fetched MAL ranking source as explicitly labelled
legacy compatibility. That population choice changes IDF and must be retained
with evaluation evidence.
Binary candidate normalization also makes metadata completeness relevant: rows
with more populated feature axes have a larger norm. Measure that sensitivity in
the owned-catalogue evaluation rather than assuming it is harmless.
