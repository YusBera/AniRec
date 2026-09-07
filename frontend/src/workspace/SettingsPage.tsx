import { useState } from "react";
import { AniRecApiError, api } from "../api/client";
import type { SettingsRead, SettingsWrite } from "../api/types";
import { ReadState, useRead } from "./common";

function editable(saved: SettingsRead): SettingsWrite {
  const { username: _username, client_id_present: _clientId, using_defaults: _defaults, ...preferences } = saved;
  return preferences;
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
    try { const result = await api.saveSettings(draft); setSaved(result); setDraft(editable(result)); setMessage("Preferences saved. Recommendation changes apply to the next generation; desktop appearance applies when the desktop app reloads its settings."); }
    catch (error) { setError(error instanceof AniRecApiError ? `${error.detail.description} ${error.detail.solution}` : "Preferences could not be saved. Your edits are kept; try again."); }
    finally { setBusy(false); }
  }}>
    {saved.using_defaults ? <p role="alert">Saved settings could not be read. Defaults are shown. Repair the settings in the desktop app before saving.</p> : null}
    <fieldset disabled={busy || saved.using_defaults} className="settings-form"><legend className="visually-hidden">Saved preferences</legend><div className="settings-groups">
      <section><h2>Recommendation</h2><div className="preference-fields">
        <label>Adventurousness (1–10)<input type="number" required min={1} max={10} value={draft.adventurousness} onChange={e => set("adventurousness", Number(e.target.value))} /></label>
        <label>Batch size<input type="number" required min={1} max={150} value={draft.batch_size} onChange={e => set("batch_size", Number(e.target.value))} /></label>
        <label>Minimum MAL score (blank for any)<input type="number" min={0} max={10} step="0.1" value={draft.minimum_mal_score ?? ""} onChange={e => set("minimum_mal_score", e.target.value === "" ? null : Number(e.target.value))} /></label>
        <label>Default sort<select value={draft.default_sort} onChange={e => set("default_sort", e.target.value as SettingsWrite["default_sort"])}>{["personal-match", "mal-score", "year", "alphabetical"].map(value => <option key={value}>{value}</option>)}</select></label>
        {([["include_hidden", "Include Not interested"], ["include_nsfw", "Include NSFW anime"], ["background_sync", "Desktop background sync"]] as const).map(([key, label]) => <label className="preference-check" key={key}><input type="checkbox" checked={draft[key]} onChange={e => set(key, e.target.checked)} />{label}</label>)}
      </div></section>
      <section><h2>Desktop appearance</h2><p>These controls save desktop preferences. This browser keeps AniRec's current dark appearance.</p><div className="preference-fields">
        <label>Theme<select value={draft.theme} onChange={e => set("theme", e.target.value as SettingsWrite["theme"])}>{["system", "dark", "light", "oled", "gradient"].map(value => <option key={value}>{value}</option>)}</select></label>
        <label>GUI scale<input type="number" required min={0.75} max={1.5} step="0.05" value={draft.gui_scale} onChange={e => set("gui_scale", Number(e.target.value))} /></label>
        <label>Font scale<input type="number" required min={0.8} max={1.4} step="0.05" value={draft.font_scale} onChange={e => set("font_scale", Number(e.target.value))} /></label>
        <label className="preference-check"><input type="checkbox" checked={draft.show_covers} onChange={e => set("show_covers", e.target.checked)} />Show anime covers</label>
      </div></section>
    </div><div className="workspace-toolbar"><button className="btn" disabled={!dirty}>{busy ? "Saving…" : "Save preferences"}</button><button className="btn" type="button" disabled={!dirty} onClick={() => { setDraft(editable(saved)); setError(""); setMessage(""); }}>Discard edits</button><span>{dirty ? "Unsaved edits" : "No unsaved edits"}</span></div></fieldset>
    {error ? <p role="alert">{error}</p> : null}<p role="status">{message}</p>
    <section><h2>Account and local data</h2><p>Active profile: {saved.username || "None"}. MAL Client ID: {saved.client_id_present ? "Configured" : "Not configured"}.</p><p>Connection has not been tested here. Connect or switch profiles, manage folders and clear caches in the desktop app.</p></section>
  </form>;
}

export function SettingsPage() {
  const read = useRead(api.settings, "settings");
  return <main className="workspace-page"><h1 tabIndex={-1}>Settings</h1><p className="workspace-intro">Save recommendation and desktop appearance preferences.</p><ReadState {...read} />{read.result ? <Preferences initial={read.result} /> : null}</main>;
}
