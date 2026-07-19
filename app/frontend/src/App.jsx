// Views: Queue (default — AMENDMENT_02 semantics), Library (all-time history),
// Voices (AMENDMENT_04 D audition gallery). Autoplay advances through READY
// stories in acquisition order; text_ready rows are visible + skippable +
// voice-pickable before any render cost.
import { useCallback, useEffect, useState } from "react";

import * as api from "./api";
import Player, { Stars } from "./Player";
import Voices from "./Voices";

const QUEUE_STATUSES = ["text_ready", "ready", "in_progress"];

export default function App() {
  const [stories, setStories] = useState(null);
  const [error, setError] = useState(null);
  const [view, setView] = useState("queue");
  const [currentId, setCurrentId] = useState(null);
  const [detail, setDetail] = useState(null);

  const reload = useCallback(() =>
    api.listStories()
      .then(({ stories }) => { setStories(stories); setError(null); })
      .catch((e) => setError(String(e))), []);
  useEffect(() => { reload(); }, [reload]);

  useEffect(() => {
    if (!currentId) { setDetail(null); return; }
    let gone = false;
    api.storyDetail(currentId).then((d) => { if (!gone) setDetail(d); })
      .catch(() => {});
    return () => { gone = true; };
  }, [currentId]);

  if (error) return <div className="shell"><p className="error">{error}</p>
    <button onClick={reload}>retry</button></div>;
  if (!stories) return <div className="shell"><p>loading…</p></div>;

  const queue = stories.filter((s) => QUEUE_STATUSES.includes(s.status));
  const playable = queue.filter((s) => s.status !== "text_ready");
  const current = stories.find((s) => s.id === currentId) || null;

  // autoplay order = acquisition order over playable stories
  const advance = (fromId) => {
    const i = playable.findIndex((s) => s.id === fromId);
    const next = playable[i + 1] || playable.find((s) => s.id !== fromId);
    setCurrentId(next ? next.id : null);
  };

  const patchStory = (id, patch) =>
    setStories((ss) => ss.map((s) => (s.id === id ? { ...s, ...patch } : s)));

  return (
    <div className="shell">
      <header>
        <h1>Readaloud</h1>
        <nav>
          {["queue", "library", "voices"].map((v) => (
            <button key={v} className={view === v ? "tab on" : "tab"}
                    onClick={() => setView(v)}>{v}</button>
          ))}
        </nav>
      </header>

      {current && (
        <Player story={current} detail={detail}
          onFinished={(id) => { patchStory(id, { status: "read" }); advance(id); reload(); }}
          onSkipped={(id) => { patchStory(id, { status: "skipped" }); advance(id); reload(); }}
          onRated={(id, score) => patchStory(id, { rating: score })} />
      )}

      {view === "queue" &&
        <Queue queue={queue} currentId={currentId}
               onPlay={setCurrentId} onChanged={reload} />}
      {view === "library" &&
        <Library stories={stories} currentId={currentId}
                 onPlay={setCurrentId} onChanged={reload} />}
      {view === "voices" && <Voices />}
    </div>
  );
}

function evidenceLine(s) {
  return (s.evidence || []).slice(0, 2).join(" · ");
}

function Queue({ queue, currentId, onPlay, onChanged }) {
  const [voices, setVoices] = useState(null);
  useEffect(() => { api.listVoices().then((v) => setVoices(v.languages)).catch(() => {}); }, []);

  if (queue.length === 0)
    return <p className="empty">Queue is empty — run the pipeline to replenish
      (worker arrives in Phase 5).</p>;

  return (
    <div className="list">
      {queue.map((s) => (
        <div key={s.id} className={s.id === currentId ? "card now" : "card"}>
          <div className="card-main" onClick={() =>
            s.status !== "text_ready" && onPlay(s.id)}>
            <div className="card-title">{s.title}</div>
            <div className="card-sub">
              {s.author || "unknown"}{s.year ? ` · ${s.year}` : ""} ·{" "}
              {s.status === "text_ready"
                ? "rendering pending"
                : `${Math.round((s.duration_s || 0) / 60)} min`}
              {s.position_s != null && ` · at ${Math.floor(s.position_s / 60)}:${String(Math.floor(s.position_s % 60)).padStart(2, "0")}`}
            </div>
            {evidenceLine(s) && <div className="card-ev">{evidenceLine(s)}</div>}
          </div>
          <div className="card-actions">
            {s.status === "text_ready" && voices && voices[s.language] && (
              // queue-window voice picker (AMENDMENT_04 D1): choose BEFORE synthesis
              <select value={s.voice || voices[s.language].find((v) => v.default)?.voice}
                      onChange={(e) =>
                        api.setVoice(s.id, e.target.value).then(onChanged)}>
                {voices[s.language].map((v) => (
                  <option key={v.voice} value={v.voice}>
                    {v.voice}{v.default ? " (default)" : ""}
                  </option>
                ))}
              </select>
            )}
            <button className="danger" onClick={() => {
              if (window.confirm(`Skip "${s.title}" permanently?`))
                api.skipStory(s.id).then(onChanged);
            }}>✕</button>
          </div>
        </div>
      ))}
    </div>
  );
}

const LIB_ORDER = ["in_progress", "ready", "text_ready", "read", "skipped",
                   "queued", "fetching", "failed"];

function Library({ stories, currentId, onPlay, onChanged }) {
  const groups = LIB_ORDER.map((st) =>
    [st, stories.filter((s) => s.status === st)]).filter(([, g]) => g.length);
  if (!groups.length) return <p className="empty">Library is empty.</p>;
  return (
    <div className="list">
      {groups.map(([st, group]) => (
        <div key={st}>
          <h2 className="group">{st.replace("_", " ")} ({group.length})</h2>
          {group.map((s) => (
            <div key={s.id} className={s.id === currentId ? "card now" : "card"}>
              <div className="card-main" onClick={() =>
                (s.status === "ready" || s.status === "in_progress" || s.status === "read")
                  && onPlay(s.id)}>
                <div className="card-title">{s.title}</div>
                <div className="card-sub">
                  {s.author || "unknown"}{s.year ? ` · ${s.year}` : ""}
                  {s.duration_s ? ` · ${Math.round(s.duration_s / 60)} min` : ""}
                  {s.voice ? ` · ${s.voice}` : ""}
                  {s.status === "failed" && s.failure_note
                    ? ` · ${s.failure_note.slice(0, 80)}` : ""}
                </div>
              </div>
              {(s.status === "read" || s.rating) && (
                <Stars rating={s.rating}
                       onRate={(score) => api.rate(s.id, score).then(onChanged)} />
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
