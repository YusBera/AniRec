/**
 * Filter and sort controls, and the pill row that shows what is active.
 *
 * Qt equivalents: filter_pills.py (351 lines), discover_filters.py's widget
 * half, typeahead.py (310 lines) and the sort control inside
 * recommendation_page.py. The vocabulary they all normalise against now lives
 * in AniRec/presentation/filters.py, so the terms a pill shows here are the
 * terms the Python side would send to a query.
 */

import type { Catalogue } from "../api/types";
import { EMPTY_FILTERS, activeFilterCount, type Filters, type SortMode } from "./filtering";

const SORTS: { value: SortMode; label: string }[] = [
  { value: "personal-match", label: "Match" },
  { value: "mal-score", label: "MAL" },
  { value: "year", label: "Year" },
  { value: "title", label: "Title" },
];

interface Props {
  catalogue: Catalogue;
  filters: Filters;
  sortMode: SortMode;
  onFilters: (next: Filters) => void;
  onSort: (next: SortMode) => void;
}

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

export function Controls({ catalogue, filters, sortMode, onFilters, onSort }: Props) {
  const count = activeFilterCount(filters);

  return (
    <>
      <div className="controls">
        <div className="control-group" role="group" aria-label="Genre filters">
          <div className="control-head">
            <span className="lbl">Genre</span>
            <span className="line" />
            <span className="lbl">{catalogue.genres.length}</span>
          </div>
          <div className="term-row">
            {catalogue.genres.map((genre) => (
              <button
                key={genre}
                type="button"
                className="pill"
                aria-pressed={filters.genres.includes(genre)}
                onClick={() => onFilters({ ...filters, genres: toggle(filters.genres, genre) })}
              >
                {genre}
              </button>
            ))}
          </div>
        </div>

        <div className="control-group" role="group" aria-label="Studio filters">
          <div className="control-head">
            <span className="lbl">Studio</span>
            <span className="line" />
            <span className="lbl">{catalogue.studios.length}</span>
          </div>
          <div className="term-row">
            {catalogue.studios.map((studio) => (
              <button
                key={studio}
                type="button"
                className="pill"
                aria-pressed={filters.studios.includes(studio)}
                onClick={() => onFilters({ ...filters, studios: toggle(filters.studios, studio) })}
              >
                {studio}
              </button>
            ))}
          </div>
        </div>

        <div className="control-group">
          <div className="control-head">
            <span className="lbl">Minimum MAL score</span>
            <span className="line" />
            <span className="lbl">
              {filters.minimumMalScore === null ? "any" : filters.minimumMalScore.toFixed(1)}
            </span>
          </div>
          {/* Qt: SteppedSlider(QSlider) with a paintEvent drawing graduations
              by hand. Here the graduations are a repeating-linear-gradient on
              the track and the stepping is the input's own `step`. */}
          <div className="stepped">
            <label className="visually-hidden" htmlFor="score-floor">
              Minimum MyAnimeList score
            </label>
            <input
              id="score-floor"
              type="range"
              min={0}
              max={10}
              step={0.5}
              value={filters.minimumMalScore ?? 0}
              aria-valuetext={filters.minimumMalScore === null ? "Any score" : `${filters.minimumMalScore.toFixed(1)} out of 10`}
              onChange={(event) => {
                const value = Number(event.target.value);
                onFilters({ ...filters, minimumMalScore: value === 0 ? null : value });
              }}
            />
            <div className="stepped-scale">
              <span>0</span>
              <span>5</span>
              <span>10</span>
            </div>
          </div>

          <div className="control-head">
            <span className="lbl">Sort</span>
            <span className="line" />
          </div>
          <div className="sort-row" role="group" aria-label="Sort recommendations">
            {SORTS.map((option) => (
              <button
                key={option.value}
                type="button"
                className="pill"
                aria-pressed={sortMode === option.value}
                onClick={() => onSort(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="pill-row">
        <span className="lbl">Active</span>
        {count === 0 ? (
          <span className="lbl lbl-strong">none</span>
        ) : (
          <>
            {filters.genres.map((genre) => (
              <Pill
                key={`g-${genre}`}
                kind="Genre"
                value={genre}
                onDismiss={() => onFilters({ ...filters, genres: toggle(filters.genres, genre) })}
              />
            ))}
            {filters.studios.map((studio) => (
              <Pill
                key={`s-${studio}`}
                kind="Studio"
                value={studio}
                onDismiss={() =>
                  onFilters({ ...filters, studios: toggle(filters.studios, studio) })
                }
              />
            ))}
            {filters.minimumMalScore !== null ? (
              <Pill
                kind="Score"
                // The en dash is the display form; a query would carry "7-10".
                value={`${filters.minimumMalScore.toFixed(1)}–10`}
                onDismiss={() => onFilters({ ...filters, minimumMalScore: null })}
              />
            ) : null}
            <button type="button" className="pill" onClick={() => onFilters(EMPTY_FILTERS)}>
              Clear all
            </button>
          </>
        )}
      </div>
    </>
  );
}

function Pill({
  kind,
  value,
  onDismiss,
}: {
  kind: string;
  value: string;
  onDismiss: () => void;
}) {
  return (
    <span className="pill" data-active="true">
      <span className="kind">{kind}</span>
      {value}
      <button
        type="button"
        className="dismiss"
        aria-label={`Remove ${kind} filter ${value}`}
        onClick={onDismiss}
      >
        ×
      </button>
    </span>
  );
}
