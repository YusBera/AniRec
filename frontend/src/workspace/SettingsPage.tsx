/**
 * Settings, in `gui/settings_page.py` order: RECOMMENDATION, APPEARANCE,
 * PROFILES, MYANIMELIST API, LOCAL DATA, DEVELOPER TOOLS.
 *
 * Only the allowlisted preferences in `SettingsWriteRequest` are editable.
 * Where the desktop has a control the web API cannot act on, the section says
 * so instead of drawing a control that does nothing. A Client ID is never
 * displayed; the response only says whether one is configured.
 */

import { useId, useState, type ReactNode } from "react";
import { AniRecApiError, api } from "../api/client";
import type { SettingsRead, SettingsWrite } from "../api/types";
import { ChannelHeading, ReadState, useRead } from "./common";

function editable(saved: SettingsRead): SettingsWrite {
  const { username: _username, client_id_present: _clientId, using_defaults: _defaults, ...preferences } = saved;
  return preferences;
}

const sortOptions = [
  ["personal-match", "Personal match"],
  ["mal-score", "MAL score"],
  ["year", "Airing year"],
  ["alphabetical", "Alphabetical"],
] as const;

const themes = [["system", "System"], ["dark", "Dark"], ["light", "Light"], ["oled", "OLED black"], ["gradient", "Gradient"]] as const;

const NOT_IN_WEB = "Not available in the web client.";

function Group({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return <section className="settings-group panel" aria-labelledby={id}><h2 id={id}>{title}</h2>{children}</section>;
}

/** One labelled row: the legend on the left, the control and its hint on the right. */
function Row({ legend, children, hint }: { legend: string; children: ReactNode; hint?: string }) {
  return <div className="settings-row"><span className="settings-legend" aria-hidden="true">{legend}</span><div className="settings-control">{children}{hint ? <p className="settings-hint">{hint}</p> : null}</div></div>;
}

function Preferences({ initial }: { initial: SettingsRead }) {
  const [saved, setSaved] = useState(initial);
  const [draft, setDraft] = useState(() => editable(initial));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const dirty = JSON.stringify(draft) !== JSON.stringify(editable(saved));
  const set = <K extends keyof SettingsWrite>(key: K, value: SettingsWrite[K]) => {
    setDraft(previous => ({ ...previous, [key]: value })); setMessage("");
  };
  return <form onSubmit={async event => {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try { const result = await api.saveSettings(draft); setSaved(result); setDraft(editable(result)); setMessage("Preferences saved. Recommendation changes apply to the next analysis; desktop appearance applies when the desktop app reloads its settings."); }
    catch (caught) { setError(caught instanceof AniRecApiError ? `${caught.detail.description} ${caught.detail.solution}` : "Preferences could not be saved. Your edits are kept; try again."); }
    finally { setBusy(false); }
  }}>
    {saved.using_defaults ? <p role="alert">Saved settings could not be read. Defaults are shown. Repair the settings in the desktop app before saving.</p> : null}
    <fieldset disabled={busy || saved.using_defaults} className="settings-form"><legend className="visually-hidden">Saved preferences</legend>
      <div className="settings-groups">
        <Group title="RECOMMENDATION">
          <Row legend="ADVENTUROUSNESS" hint="Low keeps close to what you already love. High reaches further for something unexpected.">
            <div className="stepped adventurousness">
              <span aria-hidden="true">FAMILIAR</span>
              <input type="range" min={1} max={10} step={1} value={draft.adventurousness} aria-label="Adventurousness (1–10)"
                aria-valuetext={`${draft.adventurousness} of 10`} onChange={e => set("adventurousness", Number(e.target.value))} />
              <span aria-hidden="true">SURPRISING</span>
              <output aria-hidden="true">{draft.adventurousness}</output>
            </div>
          </Row>
          <Row legend="BATCH SIZE" hint="Applies to the desktop app. The web client shows 50 per page and continues the same ranking on the next page."><input type="number" required min={1} max={150} aria-label="Batch size" value={draft.batch_size} onChange={e => set("batch_size", Number(e.target.value))} /></Row>
          <Row legend="MIN MAL SCORE" hint="Leave blank for any score.">
            <input type="number" min={0} max={10} step="0.1" aria-label="Minimum MAL score" placeholder="Any" value={draft.minimum_mal_score ?? ""} onChange={e => set("minimum_mal_score", e.target.value === "" ? null : Number(e.target.value))} />
          </Row>
          <Row legend="DEFAULT SORT"><select aria-label="Default sort" value={draft.default_sort} onChange={e => set("default_sort", e.target.value as SettingsWrite["default_sort"])}>{sortOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Row>
          <Row legend="NOT INTERESTED"><label className="preference-check"><input type="checkbox" checked={draft.include_hidden} onChange={e => set("include_hidden", e.target.checked)} />Include anime marked Not interested</label></Row>
          <Row legend="MAL CONTENT"><label className="preference-check"><input type="checkbox" checked={draft.include_nsfw} onChange={e => set("include_nsfw", e.target.checked)} />Include NSFW anime</label></Row>
          <Row legend="KEEP IN SYNC" hint="Off by default. AniRec already checks once when you open a profile. This keeps checking every 30 minutes, so a title you finish elsewhere leaves your Watch Later list without a restart. It only reads your list and never writes to your account. The desktop app does this checking; the web client does not check in the background yet.">
            <label className="preference-check"><input type="checkbox" checked={draft.background_sync} onChange={e => set("background_sync", e.target.checked)} />Check MyAnimeList for anime you have finished, while AniRec is open</label>
          </Row>
        </Group>
        <Group title="APPEARANCE">
          <p className="settings-note">The web client is dark-only. The settings below are saved for the desktop app and do not change this page.</p>
          <Row legend="THEME"><select aria-label="Desktop theme" value={draft.theme} onChange={e => set("theme", e.target.value as SettingsWrite["theme"])}>{themes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Row>
          <Row legend="GUI SCALE" hint="Resizes everything together in the desktop app: cards, portraits, badges, spacing and text.">
            <input type="number" required min={0.75} max={1.5} step="0.05" aria-label="Desktop GUI scale" value={draft.gui_scale} onChange={e => set("gui_scale", Number(e.target.value))} />
          </Row>
          <Row legend="FONT SCALE"><input type="number" required min={0.8} max={1.4} step="0.05" aria-label="Desktop font scale" value={draft.font_scale} onChange={e => set("font_scale", Number(e.target.value))} /></Row>
          <Row legend="ARTWORK"><label className="preference-check"><input type="checkbox" checked={draft.show_covers} onChange={e => set("show_covers", e.target.checked)} />Show anime covers in the desktop app</label></Row>
        </Group>
      </div>
      <div className="workspace-toolbar settings-save">
        <button className="btn primary" disabled={!dirty}>{busy ? "Saving…" : "Save preferences"}</button>
        <button className="btn" type="button" disabled={!dirty} onClick={() => { setDraft(editable(saved)); setError(""); setMessage(""); }}>Discard edits</button>
        <span>{dirty ? "Unsaved edits" : "No unsaved edits"}</span>
      </div>
    </fieldset>
    {error ? <p role="alert">{error}</p> : null}<p role="status">{message}</p>
    <div className="settings-groups">
      <Group title="PROFILES">
        <p>Active profile: {saved.username || "None"}.</p>
        <p className="settings-note">Switching, adding, opening and deleting local profiles: {NOT_IN_WEB}</p>
      </Group>
      <Group title="MYANIMELIST API">
        <p>Client ID: {saved.client_id_present ? "Configured" : "Not configured"}.</p>
        <p className="settings-note">Entering a Client ID and testing the connection: {NOT_IN_WEB}</p>
      </Group>
      <Group title="LOCAL DATA">
        <p className="settings-note">Clearing the cache, downloaded covers and local data, and opening the log folder: {NOT_IN_WEB}</p>
      </Group>
      <Group title="DEVELOPER TOOLS">
        <p>Shows the individual data steps AniRec runs for you. Not needed for normal use.</p>
        <p className="settings-note">{NOT_IN_WEB}</p>
      </Group>
    </div>
  </form>;
}

export function SettingsPage({ version = null }: { version?: string | null }) {
  const read = useRead(api.settings, "settings");
  return <main className="workspace-page">
    <ChannelHeading name="Settings" mark="CONFIGURATION" />
    <p className="workspace-intro">Manage recommendation behavior, local profiles, MyAnimeList API access, and appearance.</p>
    <ReadState {...read} />{read.result ? <Preferences initial={read.result} /> : null}
    {/* The build line left the page chrome (D-019); it lives here, with the
        other things only someone troubleshooting looks for. */}
    <p className="settings-version">{version ? `AniRec version ${version}` : "AniRec version unavailable"}</p>
  </main>;
}
