/**
 * Profile, as `gui/profile_page.py` builds it: the READER block, THE READING
 * verdict, the "NOT ON YOUR MAL PROFILE" board, then THE INSTRUMENT.
 *
 * The Local / Sample switch stays: sample evidence is opt-in and labelled,
 * and a local profile that cannot be read never silently becomes the sample.
 */

import { useState } from "react";
import { api } from "../api/client";
import { Icon } from "../assets/Icon";
import { ChannelHeading, number, ReadState, useRead } from "./common";
import { boardFacts, scoreText } from "./profileFacts";
import { ProfileSections } from "./ProfileSections";

/** `STATE_FOR_REASON`, worded for a client that cannot connect an account yet. */
const UNAVAILABLE: Record<string, [string, string, boolean]> = {
  "not-connected": ["Connect your account first", "A taste profile is read from your MyAnimeList history. Connecting an account is not available in the web client yet. You can still inspect the bundled sample profile.", false],
  "backend-missing": ["Your taste profile is not built yet", "Live profile statistics are not available in this build. You can still inspect the bundled sample profile.", false],
  "private-list": ["Your list is private", "AniRec can only read a public list. Make yours public on MyAnimeList, then try again.", false],
  network: ["MyAnimeList is unreachable", "AniRec could not reach MyAnimeList. Check your connection and try again.", true],
  "api-unavailable": ["MyAnimeList could not answer", "The request was refused or timed out. This usually clears on its own. Try again shortly.", true],
  "user-not-found": ["Nothing to read yet", "A taste profile needs scored anime. Rate a few titles on MyAnimeList, sync, and this page fills in.", false],
};

/** `ProfileIdentity.initials`: the first and last letters of the name. */
function initials(username: string): string {
  const letters = [...username].filter((char) => /[\p{L}\p{N}]/u.test(char));
  if (!letters.length) return "??";
  return letters.length === 1 ? letters[0]!.toLocaleUpperCase() : (letters[0]! + letters[letters.length - 1]!).toLocaleUpperCase();
}

export function ProfilePage() {
  const [sample, setSample] = useState(false);
  const read = useRead(() => api.profile(sample), `${sample}`);
  const profile = read.result?.profile;
  const reason = read.result?.reason;
  const unavailable = reason ? UNAVAILABLE[reason] ?? ["Profile data unavailable", "No synchronized library is available for this profile yet. You can still inspect the bundled sample profile.", false] : null;
  const identity = profile?.identity;
  const archetype = read.result?.archetype;
  const facts = profile ? boardFacts(profile) : [];
  const memberYear = identity?.member_since?.match(/\d{4}/)?.[0];

  return <main className="workspace-page">
    <ChannelHeading name="Profile" mark="TASTE READOUT" />
    <p className="workspace-intro">A portrait of your taste, read off the scores you have already given.</p>
    <div className="workspace-toolbar" role="group" aria-label="Profile source">
      <button className="btn" aria-pressed={!sample} onClick={() => setSample(false)}>Local profile</button>
      <button className="btn" aria-pressed={sample} onClick={() => setSample(true)}>View sample profile</button>
    </div>
    <ReadState {...read} />
    {unavailable ? <div className="workspace-empty">
      <Icon name="details-inspector" className="empty-icon" />
      <h2>{unavailable[0]}</h2><p>{unavailable[1]}</p>
      <div className="empty-actions">
        {unavailable[2] ? <button className="btn" onClick={read.retry}>Try again</button> : null}
        <button className="btn" onClick={() => setSample(true)}>Show a sample profile</button>
      </div>
    </div> : null}
    {profile ? <>
      <section className="identity-panel panel" aria-label="Reader">
        <div className="avatar" aria-hidden="true">{initials(identity?.username ?? "")}</div>
        <div className="identity-name">
          <p className="legend-row"><span className="legend">READER</span>{profile.is_sample ? <span className="tag warn" title="A bundled example profile. Connect MyAnimeList and generate recommendations to see your own figures here.">SAMPLE DATA</span> : null}</p>
          <h2>{identity?.username || "Unknown reader"}</h2>
          <p className="legend">MAL MEMBER SINCE {memberYear ?? "N/A"}</p>
        </div>
        <dl className="identity-stats">
          <div><dt>COMPLETED</dt><dd>{number(identity?.completed)}</dd></div>
          <div><dt>EPISODES</dt><dd>{number(identity?.episodes)}</dd></div>
          <div><dt>DAYS</dt><dd>{scoreText(identity?.days_watched, 1)}</dd></div>
          <div><dt>MEAN</dt><dd data-tone="you">{scoreText(identity?.mean_score, 2)}</dd></div>
        </dl>
      </section>
      {profile.is_sample ? <p className="sample-note">Bundled sample data. These figures describe {identity?.username || "the sample reader"}, not your account.</p> : null}

      <section className="verdict-panel panel" aria-labelledby="the-reading">
        <p className="legend" id="the-reading">THE READING</p>
        <h2 className="verdict-name">You are {archetype?.name ?? "still writing the profile"}.</h2>
        <p>{archetype?.sentence ?? "There is not enough scored history yet to give your taste a fair headline. A few more ratings will sharpen the picture."}</p>
      </section>

      <section className="unlisted panel" aria-labelledby="unlisted-title">
        <h2 id="unlisted-title">NOT ON YOUR MAL PROFILE</h2>
        <p className="unlisted-description">None of this is a number MyAnimeList shows you. It comes out of comparing every score you have given against everyone else's.</p>
        {facts.length ? <ul className="fact-board">{facts.map((fact, i) => <li key={`${fact.legend}-${i}`} className="fact-card" data-tone={fact.tone}>
          <p className="fact-head"><Icon name={fact.icon} className="fact-mark" /><span className="legend">{fact.legend}</span></p>
          <p className="fact-value">{fact.value}</p>
          <p className="fact-caption">{fact.caption}</p>
          {fact.evidence.length ? <ul className="fact-evidence" aria-label="Titles behind this">{fact.evidence.map((line) => <li key={line}>{line}</li>)}</ul> : null}
        </li>)}</ul> : <p>Not measured yet.</p>}
      </section>

      <h2 className="instrument-title">THE INSTRUMENT</h2>
      <p className="unlisted-description">Every reading behind the above, in full. Open whichever you want.</p>
      <ProfileSections profile={profile} />
    </> : null}
  </main>;
}
