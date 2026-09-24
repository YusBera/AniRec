import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Genres, number, Poster, ReadState, Scores, useRead } from "./common";

export function ComparePage() {
  const [sample, setSample] = useState(false);
  const [name, setName] = useState("");
  const [draft, setDraft] = useState("");
  const [liveName, setLiveName] = useState("");
  const [sampleNames, setSampleNames] = useState<string[]>([]);
  const read = useRead(() => api.compare(sample, sample ? name : liveName), `${sample}:${sample ? name : liveName}`);
  const report = read.result?.report;
  useEffect(() => {
    if (read.result?.sample_names?.length) setSampleNames(read.result.sample_names);
  }, [read.result]);
  return <main className="workspace-page"><h1 tabIndex={-1}>Compare</h1><p className="workspace-intro">See how two readers' interests and ratings line up.</p>
    {!sample ? <p className="workspace-message">Compare your synchronized completed list with a public MAL completed list. A compatibility percentage is not calculated. The NSFW preference controls which titles MAL returns.</p> : null}
    {!sample ? <form className="workspace-toolbar" onSubmit={event => { event.preventDefault(); if (draft.trim() === liveName) read.retry(); else setLiveName(draft.trim()); }}><label>MAL username<input required value={draft} maxLength={64} onChange={event => setDraft(event.target.value)} /></label><button className="btn" disabled={read.loading}>Compare completed lists</button></form> : null}
    <div className="workspace-toolbar"><button className="btn" aria-pressed={sample} onClick={() => setSample(x => !x)}>{sample ? "Close sample comparison" : "Explore sample comparison"}</button>
      {sample && sampleNames.length > 1 ? <label>Sample friend<select value={name || sampleNames[0] || ""} onChange={e => setName(e.target.value)}>{sampleNames.map(n => <option key={n}>{n}</option>)}</select></label> : null}</div>
    {sample ? <p className="sample-note">Bundled sample data. This comparison does not use your account.</p> : null}
    <ReadState {...read} />
    {sample && read.result?.reason ? <p role="status">The sample comparison is unavailable ({read.result.reason}).</p> : null}
    {!sample && read.result?.reason ? <p role="status">{({ "username-required": "Enter a MAL username to compare.", "not-connected": "A local profile is not connected. Profile connection is not available in this browser build; you can explore a sample comparison above.", "client-id-required": "A MAL Client ID has not been configured on this device, so live comparison is unavailable.", "no-local-snapshot": "No synchronized completed-list snapshot is available for this profile." } as Record<string, string>)[read.result.reason] || "Comparison is unavailable. Try again or explore a sample comparison."}</p> : null}
    {report ? <>
      <section className="identity-strip"><div><h2>{report.friend.username}</h2><p>{report.friend.match_label}</p></div><dl>
        <div className="compatibility-reading"><dt>Compatibility</dt><dd>{report.friend.match_score == null ? "N/A" : `${number(report.friend.match_score)}%`}</dd></div>
        <div><dt>{report.is_sample ? "Anime on their list" : "Completed anime returned"}</dt><dd>{number(report.friend.total_anime)}</dd></div>
        <div><dt>Shared anime</dt><dd>{number(report.friend.shared_anime)}</dd></div><div><dt>Both rated</dt><dd>{number(report.friend.both_rated)}</dd></div>
      </dl></section>
      {report.sections?.map(section => <section key={section.section_id}><h2>{section.title}</h2><p>{section.description}</p>
        {!section.entries?.length ? <p>{section.empty_message || "No titles in this section."}</p> : <div className="comparison-shelf">{section.entries.map((entry, i) => <article className="comparison-card" key={`${entry.model.mal_id}-${i}`}>
          <Poster title={entry.model.display_title} url={entry.model.cover_url} /><h3>{entry.model.display_title}</h3><Genres genres={entry.model.genres} />
          <Scores yours={entry.scores?.your_score} theirs={entry.scores?.friend_score} other="Friend" />
          {entry.model.mal_id ? <a href={`https://myanimelist.net/anime/${entry.model.mal_id}`} target="_blank" rel="noreferrer">MyAnimeList ↗</a> : null}
        </article>)}</div>}
      </section>)}
    </> : null}
  </main>;
}
