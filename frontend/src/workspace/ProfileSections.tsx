/**
 * THE INSTRUMENT: every reading behind the board, one folded section each,
 * in `ProfilePage._build_sections` order with `PROFILE_TEXT` legends:
 * fingerprint, rating distribution, hot takes, hype killers, hidden gems,
 * genre DNA, studio DNA, era preferences, watching habits, taste through time.
 *
 * A section the API has no data for says "Not measured yet." (or its own
 * empty sentence) instead of drawing an empty instrument.
 */

import type { ReactNode } from "react";
import type { TasteProfile, TitleVerdict } from "../api/types";
import { number, Poster } from "./common";

function Section({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <details className="profile-section">
    <summary><span className="section-legend">{title}</span><span className="section-description">{description}</span></summary>
    <div className="section-body">{children}</div>
  </details>;
}

function Titles({ titles }: { titles: readonly { title: string; your_score?: number | null }[] }) {
  return titles.length ? <ul className="taste-title-list">{titles.map((title, i) => <li key={i}>{title.title} <strong>{number(title.your_score, 1)} / 10</strong></li>)}</ul> : <p>No titles recorded.</p>;
}

/** A named title with YOU / MAL / GAP, in the readout vocabulary the desktop uses. */
export function Verdicts({ titles, empty }: { titles: readonly TitleVerdict[]; empty: string }) {
  if (!titles.length) return <p>{empty}</p>;
  return <div className="evidence-shelf">{titles.map((title, i) => <article className="evidence-card" key={`${title.mal_id}-${i}`}>
    <Poster title={title.title} url={title.cover_url} />
    <div>
      <h4>{title.title}</h4>
      <dl className="score-strip">
        <div><dt>YOU</dt><dd data-tone="you">{title.your_score == null ? "N/A" : title.your_score.toFixed(0)}</dd></div>
        <div><dt>MAL</dt><dd data-tone="them">{title.community_score == null ? "N/A" : title.community_score.toFixed(2)}</dd></div>
        <div><dt>GAP</dt><dd>{title.delta == null ? "N/A" : `${title.delta >= 0 ? "+" : ""}${title.delta.toFixed(1)}`}</dd></div>
      </dl>
      {title.mal_id ? <a href={`https://myanimelist.net/anime/${title.mal_id}`} target="_blank" rel="noreferrer">MyAnimeList <span aria-hidden="true">↗</span></a> : null}
    </div>
  </article>)}</div>;
}

export function ProfileSections({ profile }: { profile: TasteProfile }) {
  const buckets = [...(profile.rating_distribution?.buckets ?? [])].sort((a, b) => b.score - a.score);
  const peak = Math.max(1, ...buckets.map(bucket => bucket.count ?? 0));
  const genres = profile.genres;
  const studios = profile.studios;
  const empty = <p>Not measured yet.</p>;
  return <>
    <Section title="TASTE FINGERPRINT" description="How your scores sit against everyone else's. None of these is a grade. They describe a reader; they do not rank one.">
      {profile.fingerprint?.length ? <dl className="settings-readings">{profile.fingerprint.map(reading => <div key={reading.reading_id}><dt>{reading.caption}</dt><dd>{reading.value_text}{reading.detail || reading.label ? ` · ${reading.detail || reading.label}` : ""}</dd></div>)}</dl> : empty}
    </Section>
    <Section title="RATING DISTRIBUTION" description="Every score you have given, and how often.">
      {buckets.some(bucket => bucket.count) ? <div className="rating-distribution" aria-label="Number of anime by rating">{buckets.map(bucket => <div key={bucket.score}><span>{bucket.score} / 10</span><meter min={0} max={peak} value={bucket.count ?? 0} aria-label={`${bucket.score} out of 10: ${bucket.count ?? 0} anime`} /><strong>{bucket.count ?? 0}</strong></div>)}</div> : <p>No rated titles in this snapshot.</p>}
    </Section>
    <Section title="HOT TAKES" description="Where your score and the community's are furthest apart.">
      <h4 className="subhead">YOU RATED HIGHER</h4>
      <Verdicts titles={profile.hot_takes?.higher ?? []} empty="No large disagreements on record." />
      <h4 className="subhead">YOU RATED LOWER</h4>
      <Verdicts titles={profile.hot_takes?.lower ?? []} empty="No large disagreements on record." />
    </Section>
    <Section title="HYPE KILLERS" description="Titles the community ranks near the top that you did not get on with.">
      {profile.hype_killers?.biggest ? <><h4 className="subhead">BIGGEST CASUALTY</h4><Verdicts titles={[profile.hype_killers.biggest]} empty="" /></> : null}
      <Verdicts titles={profile.hype_killers?.entries ?? []} empty="Nothing highly ranked has been rated low." />
    </Section>
    <Section title="HIDDEN GEMS" description="Little-watched titles you scored well above the room.">
      {profile.hidden_gems?.rate_text && profile.hidden_gems.rate_text !== "N/A" ? <p>HIDDEN GEM RATE <strong>{profile.hidden_gems.rate_text}</strong></p> : null}
      {profile.hidden_gems?.deepest ? <><h4 className="subhead">DEEPEST CUT</h4><Verdicts titles={[profile.hidden_gems.deepest]} empty="" /></> : null}
      <Verdicts titles={profile.hidden_gems?.entries ?? []} empty="No obscure titles rated highly yet." />
    </Section>
    <Section title="GENRE DNA" description="What you watch, and how you score it. Select a genre to list the titles behind its figures.">
      {([["BEST MATCH", genres?.best_match], ["QUESTIONABLE RELATIONSHIP", genres?.weakness], ["MOST DIVISIVE", genres?.divisive]] as const).map(([label, verdict]) => verdict ? <details className="taste-detail" key={label}><summary>{label}: {verdict.name}</summary>{verdict.detail ? <p>{verdict.detail}</p> : null}<p>{number(verdict.watched)} watched · {number(verdict.average, 2)} / 10</p><Titles titles={verdict.titles ?? []} />{verdict.lowest?.length ? <><h5>Lowest ratings</h5><Titles titles={verdict.lowest} /></> : null}</details> : null)}
      {(genres?.readings ?? []).map(genre => <details className="taste-detail" key={genre.name}><summary>{genre.name} · {number(genre.watched)} watched · {number(genre.average, 2)} / 10</summary><p>List share: {genre.share == null ? "N/A" : `${number(genre.share * 100, 1)}%`} · Score spread: {number(genre.spread, 2)}</p><Titles titles={genre.titles ?? []} /></details>)}
      {!genres?.readings?.length ? empty : null}
    </Section>
    <Section title="STUDIO DNA" description="The houses you keep going back to, for and against.">
      {([["MOST WATCHED", studios?.most_watched], ["MOST TRUSTED", studios?.most_trusted], ["STUDIO NEMESIS", studios?.nemesis]] as const).map(([label, studio]) => studio ? <details className="taste-detail" key={label}><summary>{label}: {studio.name} · {number(studio.watched)} watched · {number(studio.average, 2)} / 10</summary><Titles titles={studio.titles ?? []} />{studio.lowest?.length ? <><h5>Lowest ratings</h5><Titles titles={studio.lowest} /></> : null}</details> : null)}
      {studios?.readings?.length ? <details className="taste-detail"><summary>All supplied studios · {studios.readings.length}</summary>{studios.readings.map(studio => <details key={studio.name}><summary>{studio.name} · {number(studio.watched)} watched · {number(studio.average, 2)} / 10</summary><Titles titles={studio.titles ?? []} /></details>)}</details> : null}
      {!studios?.most_watched && !studios?.readings?.length ? empty : null}
    </Section>
    <Section title="ERA PREFERENCES" description="When the anime you finish was made, and how it scored.">
      {profile.eras?.golden ? <p>GOLDEN ERA: {profile.eras.golden.label} · {number(profile.eras.golden.average, 2)} / 10</p> : null}
      {profile.eras?.buckets?.length ? <dl className="settings-readings">{profile.eras.buckets.map(era => <div key={era.label}><dt>{era.label}</dt><dd>{number(era.watched)} watched · {number(era.average, 2)} / 10</dd></div>)}</dl> : empty}
      {profile.eras?.seasons?.length ? <><h4 className="subhead">SEASONAL TASTE</h4><dl className="settings-readings">{profile.eras.seasons.map(season => <div key={season.name}><dt>{season.name}</dt><dd>{number(season.watched)} watched · {number(season.average, 2)} / 10</dd></div>)}</dl></> : null}
      {profile.eras?.season_of_choice ? <p>SEASON OF CHOICE: {profile.eras.season_of_choice}</p> : null}
    </Section>
    <Section title="WATCHING HABITS" description="What you do with a series once you have started it.">
      {profile.habits?.readings?.length ? <dl className="settings-readings">{profile.habits.readings.map(reading => <div key={reading.reading_id}><dt>{reading.caption}</dt><dd>{reading.value_text}</dd></div>)}</dl> : <p>This snapshot does not supply the list-status history needed to measure watching habits.</p>}
      {profile.habits?.most_rewatched ? <p>MOST REWATCHED: {profile.habits.most_rewatched.title} · {number(profile.habits.most_rewatched.watches)} watches</p> : null}
    </Section>
    <Section title="TASTE THROUGH TIME" description="Your mean score, year by year.">
      {profile.timeline?.points?.length ? <>{profile.timeline.trend ? <p>RATING TREND: {profile.timeline.trend} {profile.timeline.trend_detail}</p> : null}<dl className="settings-readings">{profile.timeline.points.map(point => <div key={point.year}><dt>{point.year}</dt><dd>{number(point.rated)} rated · {number(point.average, 2)} / 10</dd></div>)}</dl></> : <p>Rating dates are unavailable in this snapshot. Air years are not rating dates.</p>}
    </Section>
  </>;
}
