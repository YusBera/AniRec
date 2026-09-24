/**
 * Compare, as `gui/compare_page.py` lays it out: a selector panel, the
 * COMPATIBILITY header, then the backend's sections of title cards with a
 * YOU / THEM / GAP / MAL strip.
 *
 * No compatibility percentage is shown. The desktop's MATCH SCORE is an
 * uncalibrated figure (DOMAIN_RULES, "Scoring Honesty"), and the decision not
 * to calibrate it has not been made, so the header carries the counts only.
 * Section membership and order are the backend's; nothing is re-sorted here.
 */

import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { CompareRead } from "../api/types";
import { Icon } from "../assets/Icon";
import { malScoreText, metaLine, PosterArt } from "../discover/RecommendationCard";
import { PageHeading, number, useRead } from "./common";

type Report = NonNullable<CompareRead["report"]>;
type Entry = NonNullable<Report["sections"]>[number]["entries"] extends readonly (infer E)[] | undefined ? E : never;

const REASONS: Record<string, [string, string]> = {
  "username-required": ["Compare your taste", "Type any MyAnimeList username to see where your ratings agree and where they do not."],
  "not-connected": ["Compatibility is not built yet", "Comparing needs your own synchronized list, which is not available here. You can still inspect the bundled sample comparison."],
  "client-id-required": ["Compatibility is not built yet", "Live comparison is not available here. You can still inspect the bundled sample comparison."],
  "no-local-snapshot": ["Nothing to compare yet", "No synchronized completed-list snapshot is available for this profile."],
  "backend-missing": ["Compatibility is not built yet", "Live compatibility is not available in this build. You can still inspect the bundled sample comparison."],
  "user-not-found": ["No such profile", "MyAnimeList has no user by that name. Check the spelling and try again."],
  "private-list": ["That list is private", "That user exists, but their anime list is not public, so there is nothing to compare against."],
  network: ["MyAnimeList is unreachable", "AniRec could not reach MyAnimeList. Check your connection and try again."],
  "api-unavailable": ["MyAnimeList could not answer", "The request was refused or timed out. This usually clears on its own. Try again shortly."],
  busy: ["Too many lookups for now", "AniRec is limiting MyAnimeList lookups for a while. Try again later."],
};

const whole = (value: number | null | undefined) => value == null ? "N/A" : value.toFixed(0);

function ComparisonCard({ entry }: { entry: Entry }) {
  const model = entry.model;
  const scores = entry.scores;
  return <article className="card comparison-card" aria-label={model.display_title}>
    <div className="card-art"><PosterArt model={model} /></div>
    <h3 className="card-title">{model.display_title}</h3>
    <div className="card-secondary">{model.secondary_title || " "}</div>
    <div className="card-tags">
      {model.studios[0] ? <span className="card-tag studio"><span className="visually-hidden">Studio: </span>{model.studios[0]}</span> : null}
      {model.genres.map((genre) => <span className="card-tag" key={genre}><span className="visually-hidden">Genre: </span>{genre}</span>)}
    </div>
    <div className="card-meta">{metaLine(model)}</div>
    <div className="card-mal">{malScoreText(model)}</div>
    <dl className="score-strip comparison-strip">
      <div><dt>YOU</dt><dd data-tone="you" aria-label={`Your score: ${whole(scores?.your_score)}`}>{whole(scores?.your_score)}</dd></div>
      <div><dt>THEM</dt><dd data-tone="them" aria-label={`Their score: ${whole(scores?.friend_score)}`}>{whole(scores?.friend_score)}</dd></div>
      <div><dt>GAP</dt><dd aria-label={`Difference between the two scores: ${scores?.difference == null ? "N/A" : Math.abs(scores.difference).toFixed(0)}`}>{scores?.difference == null ? "N/A" : Math.abs(scores.difference).toFixed(0)}</dd></div>
      <div><dt>MAL</dt><dd aria-label={`MyAnimeList community score: ${scores?.mal_score == null ? "N/A" : scores.mal_score.toFixed(2)}`}>{scores?.mal_score == null ? "N/A" : scores.mal_score.toFixed(2)}</dd></div>
    </dl>
    {model.mal_id ? <a className="compare-mal" href={`https://myanimelist.net/anime/${model.mal_id}`} target="_blank" rel="noreferrer">MyAnimeList <span aria-hidden="true">↗</span></a> : null}
  </article>;
}

export function ComparePage() {
  const [sample, setSample] = useState(false);
  const [name, setName] = useState("");
  const [draft, setDraft] = useState("");
  const [liveName, setLiveName] = useState("");
  const [sampleNames, setSampleNames] = useState<string[]>([]);
  const read = useRead(() => api.compare(sample, sample ? name : liveName), `${sample}:${sample ? name : liveName}`);
  const report = read.result?.report;
  useEffect(() => {
    if (read.result?.sample_names?.length) setSampleNames([...read.result.sample_names]);
  }, [read.result]);
  const reason = read.result?.reason;
  const state = reason ? REASONS[reason] ?? ["Comparison is unavailable", "Try again, or inspect the bundled sample comparison."] : null;
  const loadingName = sample ? name || sampleNames[0] || "the sample" : liveName;

  return <main className="workspace-page">
    <section className="compare-selector panel">
      <PageHeading name="Compare" />
      <p className="workspace-intro">Enter a MyAnimeList username to see how your taste lines up with theirs.</p>
      {!sample ? <form className="compare-form" onSubmit={event => { event.preventDefault(); if (draft.trim() === liveName) read.retry(); else setLiveName(draft.trim()); }}>
        <label>MAL username<input required value={draft} maxLength={64} placeholder="MyAnimeList username" onChange={event => setDraft(event.target.value)} /></label>
        <button className="btn primary" disabled={read.loading && !!liveName} aria-label="Compare your anime list with this profile">
          {read.loading && liveName ? "Comparing…" : "Compare"}
        </button>
      </form> : null}
      <p className="compare-note">Compares your synchronized completed list with a public MAL completed list. A compatibility percentage is not calculated. The NSFW preference controls which titles MAL returns.</p>
      <div className="workspace-toolbar">
        <button className="btn" aria-pressed={sample} onClick={() => setSample(x => !x)}>{sample ? "Close sample comparison" : "Show a sample comparison"}</button>
        {sample && sampleNames.length > 1 ? <label>Sample friend<select value={name || sampleNames[0] || ""} onChange={e => setName(e.target.value)}>{sampleNames.map(n => <option key={n}>{n}</option>)}</select></label> : null}
      </div>
    </section>
    {sample ? <p className="sample-note">Bundled sample data. This comparison does not use your account.</p> : null}

    {read.error ? <div className="workspace-message" role="alert"><p>{read.error}</p><button className="btn" onClick={read.retry}>Try again</button></div> : null}
    {read.loading ? <div className="workspace-empty" role="status"><h2>Loading · Reading {loadingName}'s list</h2><p>Fetching their ratings and lining them up with yours.</p></div> : null}
    {!read.loading && state ? <div className="workspace-empty" role="status"><Icon name="nav-compare" className="empty-icon" /><h2>{state[0]}</h2><p>{state[1]}</p>
      {reason === "network" || reason === "api-unavailable" ? <button className="btn" onClick={read.retry}>Try again</button> : null}</div> : null}

    {report ? <>
      <section className="compat-header panel" aria-label="Compatibility">
        <div>
          <p className="legend-row"><span className="legend">COMPATIBILITY</span>{report.is_sample ? <span className="tag warn" title="A bundled example comparison. Connect MyAnimeList to compare real profiles.">SAMPLE DATA</span> : null}</p>
          <h2>{report.friend.username}</h2>
          {report.friend.match_label ? <p className="compat-label">{report.friend.match_label}</p> : null}
        </div>
        <dl className="identity-stats">
          <div><dt>{report.is_sample ? "ANIME ON THEIR LIST" : "COMPLETED ANIME RETURNED"}</dt><dd>{number(report.friend.total_anime)}</dd></div>
          <div><dt>SHARED ANIME</dt><dd>{number(report.friend.shared_anime)}</dd></div>
          <div><dt>BOTH RATED</dt><dd>{number(report.friend.both_rated)}</dd></div>
        </dl>
      </section>
      {report.sections?.map(section => <section key={section.section_id} className="compare-section">
        <h2>{section.title} <small>{section.entries?.length === 1 ? "1 TITLE" : `${section.entries?.length ?? 0} TITLES`}</small></h2>
        {section.description ? <p>{section.description}</p> : null}
        {!section.entries?.length ? <p>{section.empty_message || "Nothing to show in this section."}</p>
          : <div className="feed">{section.entries.map((entry, i) => <ComparisonCard key={`${entry.model.mal_id}-${i}`} entry={entry} />)}</div>}
      </section>)}
    </> : null}
  </main>;
}
