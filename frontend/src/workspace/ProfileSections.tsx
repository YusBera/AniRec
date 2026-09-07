import type { TasteProfile } from "../api/types";
import { number } from "./common";

function Titles({ titles }: { titles: { title: string; your_score?: number | null }[] }) {
  return titles.length ? <ul className="taste-title-list">{titles.map((title, i) => <li key={i}>{title.title} <strong>{number(title.your_score, 1)} / 10</strong></li>)}</ul> : <p>No title evidence supplied.</p>;
}

export function ProfileSections({ profile }: { profile: TasteProfile }) {
  const buckets = [...(profile.rating_distribution?.buckets ?? [])].sort((a, b) => b.score - a.score);
  const peak = Math.max(1, ...buckets.map(bucket => bucket.count ?? 0));
  const genres = profile.genres;
  const studios = profile.studios;
  return <>
    <section><h2>Rating distribution</h2>{buckets.some(bucket => bucket.count) ? <div className="rating-distribution" aria-label="Number of anime by rating">{buckets.map(bucket => <div key={bucket.score}><span>{bucket.score} / 10</span><meter min={0} max={peak} value={bucket.count ?? 0} aria-label={`${bucket.score} out of 10: ${bucket.count ?? 0} anime`} /><strong>{bucket.count ?? 0}</strong></div>)}</div> : <p>No rated titles in this snapshot.</p>}</section>
    <section><h2>Genre DNA</h2><p>Counts and averages from the supplied library; a title may belong to several genres.</p>
      {(genres?.readings ?? []).map(genre => <details className="taste-detail" key={genre.name}><summary>{genre.name} · {number(genre.watched)} watched · {number(genre.average, 2)} / 10</summary><p>List share: {genre.share == null ? "N/A" : `${number(genre.share * 100, 1)}%`} · Score spread: {number(genre.spread, 2)}</p><Titles titles={genre.titles ?? []} /></details>)}
      {!genres?.readings?.length ? <p>No genre analysis is available.</p> : null}
      {([["Best match", genres?.best_match], ["Weakness", genres?.weakness], ["Most divisive", genres?.divisive]] as const).map(([label, verdict]) => verdict ? <details className="taste-detail" key={label}><summary>{label}: {verdict.name}</summary><p>{verdict.detail}</p><p>{number(verdict.watched)} watched · {number(verdict.average, 2)} / 10</p><Titles titles={verdict.titles ?? []} />{verdict.lowest?.length ? <><h3>Lowest ratings</h3><Titles titles={verdict.lowest} /></> : null}</details> : null)}
    </section>
    <section><h2>Studio DNA</h2>{([["Most watched", studios?.most_watched], ["Most trusted", studios?.most_trusted], ["Lowest rated", studios?.nemesis]] as const).map(([label, studio]) => studio ? <details className="taste-detail" key={label}><summary>{label}: {studio.name} · {number(studio.watched)} watched · {number(studio.average, 2)} / 10</summary><Titles titles={studio.titles ?? []} />{studio.lowest?.length ? <><h3>Lowest ratings</h3><Titles titles={studio.lowest} /></> : null}</details> : null)}
      {studios?.readings?.length ? <details className="taste-detail"><summary>All supplied studios · {studios.readings.length}</summary>{studios.readings.map(studio => <details key={studio.name}><summary>{studio.name} · {number(studio.watched)} watched · {number(studio.average, 2)} / 10</summary><Titles titles={studio.titles ?? []} /></details>)}</details> : null}
      {!studios?.most_watched && !studios?.readings?.length ? <p>No studio analysis is available.</p> : null}
    </section>
    <section><h2>Era and season preferences</h2>{profile.eras?.golden ? <p>Highest-rated era: {profile.eras.golden.label} · {number(profile.eras.golden.average, 2)} / 10</p> : null}
      {profile.eras?.buckets?.length ? <dl className="settings-readings">{profile.eras.buckets.map(era => <div key={era.label}><dt>{era.label}</dt><dd>{number(era.watched)} watched · {number(era.average, 2)} / 10</dd></div>)}</dl> : <p>No era analysis is available.</p>}
      {profile.eras?.season_of_choice ? <p>Season of choice: {profile.eras.season_of_choice}</p> : null}<dl className="settings-readings">{profile.eras?.seasons?.map(season => <div key={season.name}><dt>{season.name}</dt><dd>{number(season.watched)} watched · {number(season.average, 2)} / 10</dd></div>)}</dl>
    </section>
    <section><h2>Watching habits</h2>{profile.habits?.readings?.length ? <dl className="settings-readings">{profile.habits.readings.map(reading => <div key={reading.reading_id}><dt>{reading.caption}</dt><dd>{reading.value_text}</dd></div>)}</dl> : <p>This snapshot does not supply the list-status history needed to measure watching habits.</p>}{profile.habits?.most_rewatched ? <p>Most rewatched: {profile.habits.most_rewatched.title} · {number(profile.habits.most_rewatched.watches)} watches</p> : null}</section>
    <section><h2>Taste through time</h2>{profile.timeline?.points?.length ? <><p>{profile.timeline.trend} {profile.timeline.trend_detail}</p><dl className="settings-readings">{profile.timeline.points.map(point => <div key={point.year}><dt>{point.year}</dt><dd>{number(point.rated)} rated · {number(point.average, 2)} / 10</dd></div>)}</dl></> : <p>Rating dates are unavailable in this snapshot. Air years are not rating dates.</p>}</section>
  </>;
}
