// Views: Queue (default — AMENDMENT_02 semantics), Library (all-time history),
// Channels (R12 criteria editor), Voices (AMENDMENT_04 D audition gallery). Autoplay advances through READY
// stories in acquisition order; text_ready rows are visible + skippable +
// voice-pickable before any render cost. AMENDMENT_05 C: last-played story
// auto-restores paused; skip distinguishes "not interested" from "already
// read"; skips are revocable from the library.
import { useCallback, useEffect, useRef, useState } from "react";

import * as api from "./api";
import Channels from "./Channels";
import Player, { Stars } from "./Player";
import RenderBar from "./RenderBar";
import Settings from "./Settings";
import Voices from "./Voices";

const QUEUE_STATUSES = ["text_ready", "ready", "in_progress"];
const TABS = { queue: "Queue", library: "Library", channels: "Channels",
               voices: "Voices", settings: "Settings" };
const POLL_MS = 15000; // background renders surface without manual refresh
const RENDER_POLL_MS = 2000; // AMENDMENT_06: a progress bar needs to move

export default function App() {
  const [stories, setStories] = useState(null);
  const [voices, setVoices] = useState(null);
  const [error, setError] = useState(null);
  const [view, setView] = useState("queue");
  const [currentId, setCurrentId] = useState(null);
  const [autoplay, setAutoplay] = useState(false);
  const [detail, setDetail] = useState(null);
  const [renders, setRenders] = useState([]);
  const restoredRef = useRef(false);
  const hadRendersRef = useRef(false);

  const reload = useCallback(() =>
    api.listStories()
      .then(({ stories }) => { setStories(stories); setError(null); })
      .catch((e) => setError(String(e))), []);
  useEffect(() => { reload(); }, [reload]);
  useEffect(() => {
    api.listVoices().then((v) => setVoices(v.languages)).catch(() => {});
  }, []);
  useEffect(() => {
    const t = setInterval(() => {
      if (document.visibilityState === "visible") reload();
    }, POLL_MS);
    return () => clearInterval(t);
  }, [reload]);

  // Render jobs poll fast only while something is rendering (AMENDMENT_06);
  // idle, it rides the slow tick so a backgrounded phone isn't polling at 2 s.
  const pollRenders = useCallback(() =>
    api.listRenders()
      .then(({ renders }) => {
        setRenders(renders);
        // a render that just finished changed the library — pull it in once
        if (hadRendersRef.current && renders.length === 0) reload();
        hadRendersRef.current = renders.length > 0;
      })
      .catch(() => {}), [reload]);
  useEffect(() => { pollRenders(); }, [pollRenders]);
  useEffect(() => {
    const t = setInterval(() => {
      if (document.visibilityState === "visible") pollRenders();
    }, renders.length ? RENDER_POLL_MS : POLL_MS);
    return () => clearInterval(t);
  }, [pollRenders, renders.length]);

  const jobFor = (id) => renders.find((j) => j.story_id === id) || null;

  // auto-restore the last-played story, paused (AMENDMENT_05 C7)
  useEffect(() => {
    if (restoredRef.current || !stories) return;
    restoredRef.current = true;
    const last = stories
      .filter((s) => s.status === "in_progress" && s.progress_updated_at)
      .sort((a, b) => b.progress_updated_at.localeCompare(a.progress_updated_at))[0];
    if (last && !currentId) { setAutoplay(false); setCurrentId(last.id); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stories]);

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

  const play = (id) => { setAutoplay(true); setCurrentId(id); };

  // autoplay order = acquisition order over playable stories
  const advance = (fromId) => {
    const i = playable.findIndex((s) => s.id === fromId);
    const next = playable[i + 1] || playable.find((s) => s.id !== fromId);
    if (next) play(next.id); else setCurrentId(null);
  };

  const patchStory = (id, patch) =>
    setStories((ss) => ss.map((s) => (s.id === id ? { ...s, ...patch } : s)));

  return (
    <div className="shell">
      <header>
        <h1>Readaloud</h1>
        <nav>
          {Object.entries(TABS).map(([v, label]) => (
            <button key={v} className={view === v ? "tab on" : "tab"}
                    onClick={() => setView(v)}>{label}</button>
          ))}
        </nav>
      </header>

      {current && (
        <Player story={current} detail={detail} voices={voices}
          autoplay={autoplay} job={jobFor(currentId)}
          onRenderChanged={() => { reload(); pollRenders(); }}
          onFinished={(id) => { patchStory(id, { status: "read" }); advance(id); reload(); }}
          onSkipped={(id) => { patchStory(id, { status: "skipped" }); advance(id); reload(); }}
          onReadMarked={(id) => { patchStory(id, { status: "read" }); advance(id); reload(); }}
          onRated={(id, score) => patchStory(id, { rating: score })}
          onVoiceChanged={(id, v) => { patchStory(id, { voice: v }); reload(); }} />
      )}

      {view === "queue" &&
        <Queue queue={queue} currentId={currentId} voices={voices}
               jobFor={jobFor} onPlay={play}
               onChanged={() => { reload(); pollRenders(); }} />}
      {view === "library" &&
        <Library stories={stories} currentId={currentId} jobFor={jobFor}
                 onPlay={play}
                 onChanged={() => { reload(); pollRenders(); }} />}
      {view === "channels" && <Channels onChanged={reload} />}
      {view === "voices" && <Voices />}
      {view === "settings" && <Settings />}
    </div>
  );
}

function evidenceLine(s) {
  return (s.evidence || []).slice(0, 2).join(" · ");
}

function Queue({ queue, currentId, voices, jobFor, onPlay, onChanged }) {
  if (queue.length === 0)
    return <p className="empty">Queue is empty — run the pipeline to replenish
      (`python -m pipeline.worker`).</p>;

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
              {s.voice ? ` · ${s.voice}` : ""}
              {s.position_s != null && ` · at ${Math.floor(s.position_s / 60)}:${String(Math.floor(s.position_s % 60)).padStart(2, "0")}`}
            </div>
            {evidenceLine(s) && <div className="card-ev">{evidenceLine(s)}</div>}
          </div>
          <div className="card-actions">
            {s.status === "text_ready" && voices?.[s.language] && (
              // pre-render voice pick (AMENDMENT_05 C6): stores the choice and
              // kicks the render with it; an in-flight render aborts on mismatch
              <select value={s.voice || voices[s.language].find((v) => v.default)?.voice}
                      onChange={(e) => {
                        if (window.confirm(`Render "${s.title}" with ${e.target.value}?`))
                          api.setVoice(s.id, e.target.value).then(onChanged);
                      }}>
                {voices[s.language].map((v) => (
                  <option key={v.voice} value={v.voice}>
                    {v.voice}{v.default ? " (default)" : ""}
                  </option>
                ))}
              </select>
            )}
            <button className="danger" onClick={() => {
              if (window.confirm(`Skip "${s.title}" (not interested)? Use the player's remove button for "already read".`))
                api.skipStory(s.id).then(onChanged);
            }}>✕</button>
          </div>
          <RenderBar job={jobFor(s.id)} story={s} onChanged={onChanged} />
        </div>
      ))}
    </div>
  );
}

const LIB_ORDER = ["in_progress", "ready", "text_ready", "read", "skipped",
                   "queued", "fetching", "failed"];

function Library({ stories, currentId, jobFor, onPlay, onChanged }) {
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
              {s.status === "skipped" && (
                // misclick recovery (AMENDMENT_05 C4)
                <button onClick={() => api.unskipStory(s.id).then(onChanged)}>
                  undo
                </button>
              )}
              {s.rating != null && s.id !== currentId && (
                // display only — edits happen in the player (AMENDMENT_05 C8)
                <Stars rating={s.rating} readOnly />
              )}
              <RenderBar job={jobFor(s.id)} story={s} onChanged={onChanged} />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
