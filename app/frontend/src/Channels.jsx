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

const usd = (n) => (n === 0 ? "$0" : `$${n < 0.01 ? n.toFixed(4) : n.toFixed(2)}`);

export default function Channels({ onChanged }) {
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null); // id, or "new"
  const [draft, setDraft] = useState(BLANK);
  const [error, setError] = useState(null);
  // Channels we have just asked to build, before the subprocess has written
  // its first job row (a second or two). Without this the button press looks
  // like it did nothing — the exact failure this whole screen is fixing.
  const [starting, setStarting] = useState([]);

  const load = () => api.listChannels().then(setData).catch((e) => setError(String(e)));
  useEffect(() => { load(); }, []);

  const building = data ? data.channels.filter(
    (ch) => (ch.build && ch.build.active) || starting.includes(ch.id)) : [];
  // Poll only while something is running: a build takes minutes, and a screen
  // that polls forever is a battery bug on a phone.
  useEffect(() => {
    if (building.length === 0) return undefined;
    const t = setInterval(load, (data && data.poll_ms) || 2000);
    return () => clearInterval(t);
  }, [building.length, data && data.poll_ms]);
  // Drop the optimistic flag as soon as the real job row appears.
  useEffect(() => {
    if (!data || starting.length === 0) return;
    const seen = data.channels.filter((ch) => ch.build && ch.build.active)
      .map((ch) => ch.id);
    if (seen.length) setStarting((s) => s.filter((id) => !seen.includes(id)));
  }, [data]);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>loading…</p>;

  const build = (ch, approve) => {
    setError(null);
    setStarting((s) => [...s, ch.id]);
    api.buildPool(ch.id, approve)
      .then(() => load())
      .catch((e) => {
        setStarting((s) => s.filter((id) => id !== ch.id));
        setError(String(e.message || e));
      });
  };

  const stopBuild = (id) =>
    api.cancelBuild(id).then(load).catch((e) => setError(String(e.message || e)));

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
                <PoolState ch={ch} data={data} starting={starting.includes(ch.id)}
                           onStop={() => stopBuild(ch.id)} />
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
                {!(ch.build && ch.build.active) && !starting.includes(ch.id)
                  && ch.no_free_source_reason === null && (
                  <button onClick={() => {
                    if (!data.build_needs_approval) return build(ch, false);
                    if (window.confirm(
                      `This build is estimated at ${usd(data.build_estimate_usd)} ` +
                      `(${data.build_estimate_note}). Start it?`))
                      build(ch, true);
                  }}>
                    build pool · {usd(data.build_estimate_usd)}
                  </button>
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

// AMENDMENT_04 A: "an empty pool produces a notice with the cost estimate."
// That notice existed only in the CLI until Entry 43, so on the phone a channel
// with nothing to draw from looked exactly like a full one — which is how
// activating a new channel came to look like a no-op for six days.
function PoolState({ ch, data, starting, onStop }) {
  const job = ch.build;
  const live = starting || (job && job.active);

  if (live) {
    const pct = !job || job.fraction == null ? null : Math.round(job.fraction * 100);
    return (
      <div className="pool">
        <div className={pct == null ? "render-track indet" : "render-track"}>
          <div className="render-fill"
               style={pct == null ? undefined : { width: `${pct}%` }} />
        </div>
        <div className="card-ev">
          {starting && !job ? "starting…" : (
            <>
              {job.label}
              {job.total ? ` ${job.checked}/${job.total}` : ""}
              {job.phase === "verifying" ? ` · ${job.usable} usable so far` : ""}
            </>
          )}
          {job && <button className="link" onClick={onStop}>stop</button>}
        </div>
      </div>
    );
  }

  if (ch.no_free_source_reason) {
    return (
      <div className="card-ev warn">
        no free source covers this channel — {ch.no_free_source_reason} Switch
        curation to AI web search in Settings, or add a source.
      </div>
    );
  }
  if (ch.pool_candidates === 0) {
    return (
      <div className="card-ev warn">
        no candidates in the pool — nothing can be queued until you build one
        ({usd(data.build_estimate_usd)} in {data.curation_mode} mode).
        {job && job.note ? ` Last build: ${job.note}` : ""}
      </div>
    );
  }
  return (
    <div className="card-ev">
      {ch.pool_candidates} candidate{ch.pool_candidates === 1 ? "" : "s"} in the
      pool · sources: {ch.free_sources.join(", ") || "none"}
      {job && job.state === "cancelled" ? " · last build was stopped" : ""}
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
