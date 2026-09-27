"""Filter a complete saved ranking before selecting a bounded display page."""
from types import SimpleNamespace


def catalogue(recommendations):
    return {
        "genres": sorted({g for r in recommendations for g in r.anime.genres}),
        "studios": sorted({s for r in recommendations for s in r.anime.studios}),
        "years": sorted({r.anime.year for r in recommendations if r.anime.year is not None}, reverse=True),
        "statuses": sorted({r.anime.status for r in recommendations if r.anime.status}),
    }


def fingerprint_rows(recommendations):
    return tuple(SimpleNamespace(mal_id=r.anime.mal_id, rank=r.rank,
        fit_rank=r.model_rank, ranking_id=r.ranking_id,
        selection_policy=r.selection_policy, adventurousness=r.adventurousness)
        for r in recommendations)


def query_feed(recommendations, query, hidden_ids):
    genres = {g.casefold() for g in query.genres}
    studios = {s.casefold() for s in query.studios}
    def matches(rec):
        anime = rec.anime
        if anime.mal_id in hidden_ids:
            return False
        if not genres <= {g.casefold() for g in anime.genres}:
            return False
        if studios and not studios.intersection(s.casefold() for s in anime.studios):
            return False
        if query.years and anime.year not in query.years:
            return False
        if query.minimumMalScore is not None and (anime.mean_score is None or anime.mean_score < query.minimumMalScore):
            return False
        if query.status and (anime.status or "").casefold() != query.status.casefold():
            return False
        if query.minimumEpisodes is not None and (anime.episodes is None or anime.episodes < query.minimumEpisodes):
            return False
        if query.maximumEpisodes is not None and (anime.episodes is None or anime.episodes > query.maximumEpisodes):
            return False
        return True
    rows = [rec for rec in recommendations if matches(rec)]
    # Personal fit retains the saved complete selection order. The original
    # ONNX rank remains on the card, independent of its browsing position.
    if query.sort == "mal-score":
        rows.sort(key=lambda r: (r.anime.mean_score is None, -(r.anime.mean_score or 0)))
    elif query.sort == "year":
        rows.sort(key=lambda r: (r.anime.year is None, -(r.anime.year or 0)))
    elif query.sort == "title":
        rows.sort(key=lambda r: (r.anime.english_title or r.anime.title).casefold())
    total = len(rows)
    page = min(query.page, max(0, (total - 1) // 50))
    return tuple(rows[page * 50:(page + 1) * 50]), total, page
