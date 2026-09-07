import { useState } from "react";
import { api } from "../api/client";
import type { TitleVerdict } from "../api/types";
import { number, Poster, ReadState, Scores, useRead } from "./common";
import { ProfileSections } from "./ProfileSections";

function Evidence({ titles, label }: { titles: TitleVerdict[]; label: string }) {
  return <section><h2>{label}</h2>{!titles.length ? <p>No title evidence is available in this snapshot.</p> : <div className="evidence-shelf">{titles.map((title, i) => <article className="evidence-card" key={`${title.mal_id}-${i}`}>
    <Poster title={title.title} url={title.cover_url} /><div><h3>{title.title}</h3><Scores yours={title.your_score} theirs={title.community_score} />{title.mal_id ? <a href={`https://myanimelist.net/anime/${title.mal_id}`} target="_blank" rel="noreferrer">MyAnimeList ↗</a> : null}</div>
  </article>)}</div>}</section>;
}

export function ProfilePage() {
  const [sample, setSample] = useState(false);
  const read = useRead(() => api.profile(sample), `${sample}`);
  const profile = read.result?.profile;
  const readings = () => profile?.fingerprint?.map(reading => <div key={reading.reading_id}><h2>{reading.caption}</h2><strong>{reading.value_text}</strong><p>{reading.detail || reading.label}</p></div>);
  return <main className="workspace-page"><h1 tabIndex={-1}>Profile</h1><p className="workspace-intro">A portrait of your taste, read off the scores you have already given.</p>
    <div className="workspace-toolbar"><button className="btn" aria-pressed={!sample} onClick={() => setSample(false)}>Local profile</button><button className="btn" aria-pressed={sample} onClick={() => setSample(true)}>View sample profile</button></div>
    {sample ? <p className="sample-note">Bundled sample data. These figures describe anirec_sample, not your account.</p> : null}
    <ReadState {...read} />
    {read.result?.reason ? <div className="workspace-empty"><h2>Profile data unavailable</h2><p>{read.result.reason === "not-connected" ? "Connect a profile in the desktop app to see your own taste." : "Sync your library in the desktop app, then reload this view."}</p><button className="btn" onClick={read.retry}>Reload profile</button></div> : null}
    {profile ? <>
      <section className="identity-strip"><div><h2>{profile.identity?.username}</h2>{profile.identity?.member_since ? <p>MAL member since {profile.identity.member_since}</p> : null}</div>
        <dl>{([["Completed", profile.identity?.completed], ["Episodes", profile.identity?.episodes], ["Days watched", profile.identity?.days_watched], ["Mean score / 10", profile.identity?.mean_score]] as const).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{number(value, 2)}</dd></div>)}</dl>
      </section>
      <section className="profile-readings desktop-readings" aria-label="Taste readings">{readings()}</section>
      <details className="mobile-readings"><summary>Taste readings · {profile.fingerprint?.length ?? 0}</summary><div className="profile-readings">{readings()}</div></details>
      <Evidence label="Rated above the community" titles={profile.hot_takes?.higher ?? []} />
      <Evidence label="Rated below the community" titles={profile.hot_takes?.lower ?? []} />
      {read.result?.archetype ? <section><h2>{read.result.archetype.name}</h2><p>{read.result.archetype.sentence}</p><ul>{read.result.archetype.evidence?.map(evidence => <li key={evidence}>{evidence}</li>)}</ul></section> : null}
      <Evidence label="Highly ranked titles you rated low" titles={profile.hype_killers?.entries ?? []} />
      {profile.hype_killers?.biggest ? <Evidence label="Largest gap among highly ranked titles" titles={[profile.hype_killers.biggest]} /> : null}
      <Evidence label="Hidden gems" titles={profile.hidden_gems?.entries ?? []} />
      {profile.hidden_gems?.deepest ? <Evidence label="Deepest discovery" titles={[profile.hidden_gems.deepest]} /> : null}
      <ProfileSections profile={profile} />
    </> : null}
  </main>;
}
