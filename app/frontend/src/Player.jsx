// The player, built on the probe-5-proven mechanism (single m4a + range
// requests) and the four BINDING iOS rules of DESIGN §6:
//   1. resume seeks apply on loadedmetadata or later — never at page init
//   2. `ended` => server clears progress + marks read — never resume at EOF
//   3. progress saved server-side on pause/visibility-change + every ~5 s
//      while playing; saves suppressed until a pending resume has applied
//   4. ±15 s via Media Session handlers (lock-screen icon may say "10s")
import { useEffect, useRef, useState } from "react";

import * as api from "./api";

const SKIP_S = 15;
const SAVE_EVERY_MS = 5000;
const SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2];

function fmt(t) {
  if (!isFinite(t) || t < 0) return "0:00";
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60),
        s = Math.floor(t % 60);
  return (h ? `${h}:${String(m).padStart(2, "0")}` : `${m}`) +
         `:${String(s).padStart(2, "0")}`;
}

export default function Player({ story, detail, onFinished, onSkipped, onRated }) {
  const audioRef = useRef(null);
  // pendingSeek doubles as the save-suppression flag (iOS rule 3): non-null
  // means the resume target hasn't been applied yet, so nothing saves
  const pendingSeekRef = useRef(null);
  const endedRef = useRef(false);
  const [now, setNow] = useState(0);
  const [duration, setDuration] = useState(story.duration_s || 0);
  const [playing, setPlaying] = useState(false);
  const [resumeNote, setResumeNote] = useState("");
  const [speed, setSpeed] = useState(
    () => Number(localStorage.getItem("speed")) || 1);
  const [showText, setShowText] = useState(false);
  const [bookmarks, setBookmarks] = useState(detail?.bookmarks || []);

  useEffect(() => setBookmarks(detail?.bookmarks || []), [detail]);

  // -- load + resume (rules 1 and 3) --
  useEffect(() => {
    const audio = audioRef.current;
    endedRef.current = false;
    pendingSeekRef.current = null;
    setNow(0);
    setResumeNote("");
    let cancelled = false;
    api.getProgress(story.id).then(({ position_s }) => {
      if (cancelled || position_s == null) return;
      pendingSeekRef.current = position_s;
      setResumeNote(`resuming at ${fmt(position_s)}`);
      applyPendingSeek(); // metadata may already be loaded
    }).catch(() => {}); // no progress -> start at 0
    audio.src = `/api/stories/${story.id}/audio`;
    audio.load();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [story.id]);

  function applyPendingSeek() {
    const audio = audioRef.current;
    if (pendingSeekRef.current == null || !audio || audio.readyState < 1) return;
    audio.currentTime = pendingSeekRef.current;
    pendingSeekRef.current = null;
    setResumeNote("");
  }

  function save() {
    const audio = audioRef.current;
    if (!audio || pendingSeekRef.current != null || endedRef.current) return;
    if (!isFinite(audio.duration) || audio.duration <= 0) return;
    api.saveProgress(story.id, audio.currentTime);
  }

  // -- audio element wiring --
  useEffect(() => {
    const audio = audioRef.current;
    const onLoaded = () => { setDuration(audio.duration || 0); applyPendingSeek(); };
    const onPlaying = () => { applyPendingSeek(); setPlaying(true); };
    const onPause = () => { setPlaying(false); save(); };
    const onTime = () => setNow(audio.currentTime || 0);
    const onEnded = () => {
      endedRef.current = true; // block any late save re-creating progress
      api.markEnded(story.id).then(() => onFinished(story.id)).catch(() => {});
    };
    audio.addEventListener("loadedmetadata", onLoaded);
    audio.addEventListener("playing", onPlaying);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("ended", onEnded);
    const tick = setInterval(() => { if (!audio.paused) save(); }, SAVE_EVERY_MS);
    const onHide = () => { if (document.visibilityState === "hidden") save(); };
    document.addEventListener("visibilitychange", onHide);
    window.addEventListener("pagehide", save);
    return () => {
      audio.removeEventListener("loadedmetadata", onLoaded);
      audio.removeEventListener("playing", onPlaying);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("ended", onEnded);
      clearInterval(tick);
      document.removeEventListener("visibilitychange", onHide);
      window.removeEventListener("pagehide", save);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [story.id]);

  useEffect(() => {
    audioRef.current.playbackRate = speed;
    localStorage.setItem("speed", String(speed));
  }, [speed, story.id]);

  // -- Media Session (rule 4) --
  useEffect(() => {
    if (!("mediaSession" in navigator)) return;
    const audio = audioRef.current;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: story.title,
      artist: story.author || "unknown",
      album: "Readaloud",
    });
    const move = (d) => () => {
      audio.currentTime = Math.max(
        0, Math.min((audio.duration || 0) - 0.5, audio.currentTime + d));
    };
    navigator.mediaSession.setActionHandler("play", () => audio.play());
    navigator.mediaSession.setActionHandler("pause", () => audio.pause());
    navigator.mediaSession.setActionHandler("seekbackward", move(-SKIP_S));
    navigator.mediaSession.setActionHandler("seekforward", move(SKIP_S));
    navigator.mediaSession.setActionHandler("seekto", (e) => {
      if (e.seekTime != null) audio.currentTime = e.seekTime;
    });
  }, [story.id, story.title, story.author]);

  // read the ref at call time — a first-render closure could capture null
  const toggle = () => {
    const audio = audioRef.current;
    if (audio) audio.paused ? audio.play() : audio.pause();
  };
  const nudge = (d) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(
      0, Math.min((audio.duration || 0) - 0.5, audio.currentTime + d));
  };
  const seekTo = (t) => {
    const audio = audioRef.current;
    if (audio) audio.currentTime = t;
  };

  async function onSkipClick() {
    if (!window.confirm(`Skip "${story.title}" permanently?`)) return;
    await api.skipStory(story.id);
    onSkipped(story.id);
  }

  async function onBookmark() {
    const note = window.prompt("Bookmark note (optional):") ?? null;
    const { id } = await api.addBookmark(story.id, now, note || null);
    setBookmarks((b) =>
      [...b, { id, position_s: now, note }].sort(
        (x, y) => x.position_s - y.position_s));
  }

  return (
    <div className="player">
      <audio ref={audioRef} preload="metadata" />
      <div className="np-title">{story.title}</div>
      <div className="np-sub">
        {story.author || "unknown"}
        {story.year ? ` · ${story.year}` : ""} · {fmt(duration)}
        {story.voice ? ` · ${story.voice}` : ""}
      </div>
      {resumeNote && <div className="resume-note">{resumeNote}</div>}

      <input className="scrubber" type="range" min="0" max={duration || 0}
             step="0.1" value={Math.min(now, duration || 0)}
             onChange={(e) => seekTo(Number(e.target.value))} />
      <div className="times"><span>{fmt(now)}</span><span>-{fmt((duration || 0) - now)}</span></div>

      <div className="controls">
        <button className="ctl" onClick={() => nudge(-SKIP_S)}>−15s</button>
        <button className="ctl big" onClick={toggle}>{playing ? "⏸" : "▶"}</button>
        <button className="ctl" onClick={() => nudge(SKIP_S)}>+15s</button>
      </div>

      <div className="row">
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
          {SPEEDS.map((s) => <option key={s} value={s}>{s}×</option>)}
        </select>
        <button onClick={onBookmark}>🔖 bookmark</button>
        <button onClick={() => setShowText(!showText)}>
          {showText ? "hide text" : "text"}
        </button>
        <button className="danger" onClick={onSkipClick}>skip ✕</button>
      </div>

      <Stars rating={story.rating} onRate={(s) =>
        api.rate(story.id, s).then(() => onRated(story.id, s))} />

      {bookmarks.length > 0 && (
        <div className="bookmarks">
          {bookmarks.map((b) => (
            <div key={b.id} className="bookmark">
              <button onClick={() => seekTo(b.position_s)}>
                {fmt(b.position_s)}
              </button>
              <span>{b.note || ""}</span>
              <button className="danger" onClick={() =>
                api.deleteBookmark(b.id).then(() =>
                  setBookmarks((bs) => bs.filter((x) => x.id !== b.id)))}>
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {showText && detail?.paragraphs && (
        <div className="story-text">
          {detail.paragraphs.map((p, i) => <p key={i}>{p}</p>)}
        </div>
      )}
    </div>
  );
}

export function Stars({ rating, onRate }) {
  return (
    <div className="stars">
      {[1, 2, 3, 4, 5].map((s) => (
        <button key={s} className={s <= (rating || 0) ? "star on" : "star"}
                onClick={() => onRate(s)}>★</button>
      ))}
    </div>
  );
}
