// Channel criteria editor (R12 / AMENDMENT_01): genre, language, topics, era,
// exclusions and free-text criteria are all editable, and all of them reach
// the curation prompt — an editor whose fields changed nothing would be a lie.
// Switching the active channel re-targets replenishment (DESIGN §7); other
// channels' stories stay in the library, they just stop counting toward the
// queue.
import { useEffect, useState } from "react";

import * as api from "./api";

const BLANK = { name: "", genre: "", language: "en", era: "", topics: [],
                exclusions: [], extra_criteria: "" };

const csv = (a) => (a || []).join(", ");
const parseCsv = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);

export default function Channels({ onChanged }) {
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null); // id, or "new"
  const [draft, setDraft] = useState(BLANK);
  const [error, setError] = useState(null);

  const load = () => api.listChannels().then(setData).catch((e) => setError(String(e)));
  useEffect(() => { load(); }, []);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>loading…</p>;

  const startEdit = (ch) => {
    setEditing(ch.id);
    setDraft({ ...BLANK, ...ch });
    setError(null);
  };

  const save = () => {
    const body = {
      name: draft.name, genre: draft.genre, language: draft.language,
      era: draft.era, topics: draft.topics, exclusions: draft.exclusions,
      extra_criteria: draft.extra_criteria,
    };
    const p = editing === "new"
      ? api.createChannel(body)
      : api.updateChannel(editing, body);
    p.then(() => { setEditing(null); load(); onChanged && onChanged(); })
     .catch((e) => setError(String(e)));
  };

  const activate = (id) =>
    api.activateChannel(id)
      .then(() => { load(); onChanged && onChanged(); })
      .catch((e) => setError(String(e)));

  return (
    <div className="settings">
      <h2 className="group">Channels</h2>
      <p className="hint">
        The active channel is what the worker replenishes, {data.queue_depth} unread
        deep. Editing criteria changes the next curation batch, not stories you
        already have.
      </p>

      {data.channels.map((ch) => (
        <div key={ch.id} className={ch.is_active ? "card now" : "card"}>
          {editing === ch.id ? (
            <ChannelForm draft={draft} setDraft={setDraft} languages={data.languages}
                         onSave={save} onCancel={() => setEditing(null)} />
          ) : (
            <>
              <div className="card-main">
                <div className="card-title">
                  {ch.name}{ch.is_active && " · active"}
                </div>
                <div className="card-sub">
                  {ch.genre || "any genre"} · {ch.language}
                  {ch.era ? ` · ${ch.era}` : ""} · {ch.unread} unread
                </div>
                {ch.topics.length > 0 &&
                  <div className="card-ev">topics: {csv(ch.topics)}</div>}
                {ch.exclusions.length > 0 &&
                  <div className="card-ev">avoid: {csv(ch.exclusions)}</div>}
              </div>
              <div className="card-actions">
                <button onClick={() => startEdit(ch)}>edit</button>
                {!ch.is_active && (
                  <button onClick={() => {
                    if (window.confirm(
                      `Make "${ch.name}" the active channel? Replenishment ` +
                      "re-targets to it; your other stories stay in the library."))
                      activate(ch.id);
                  }}>activate</button>
                )}
              </div>
            </>
          )}
        </div>
      ))}

      {editing === "new" ? (
        <div className="card">
          <ChannelForm draft={draft} setDraft={setDraft} languages={data.languages}
                       onSave={save} onCancel={() => setEditing(null)} />
        </div>
      ) : (
        <button onClick={() => { setEditing("new"); setDraft(BLANK); setError(null); }}>
          + new channel
        </button>
      )}
    </div>
  );
}

function ChannelForm({ draft, setDraft, languages, onSave, onCancel }) {
  const set = (k) => (e) => setDraft({ ...draft, [k]: e.target.value });
  const setList = (k) => (e) => setDraft({ ...draft, [k]: parseCsv(e.target.value) });
  return (
    <div className="chan-form">
      <label>name<input value={draft.name} onChange={set("name")} /></label>
      <label>genre
        <input value={draft.genre || ""} onChange={set("genre")}
               placeholder="horror" /></label>
      <label>language
        <select value={draft.language} onChange={set("language")}>
          {languages.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
      </label>
      <label>era
        <input value={draft.era || ""} onChange={set("era")}
               placeholder="pre-1930, modern…" /></label>
      <label>topics (comma-separated)
        <input value={csv(draft.topics)} onChange={setList("topics")}
               placeholder="cosmic, haunted house" /></label>
      <label>avoid (comma-separated)
        <input value={csv(draft.exclusions)} onChange={setList("exclusions")}
               placeholder="gore, body horror" /></label>
      <label>extra criteria
        <textarea rows={3} value={draft.extra_criteria || ""}
                  onChange={set("extra_criteria")} /></label>
      <div className="row">
        <button onClick={onSave} disabled={!draft.name.trim()}>save</button>
        <button onClick={onCancel}>cancel</button>
      </div>
    </div>
  );
}
