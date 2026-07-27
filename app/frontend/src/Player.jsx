// The player, built on the probe-5-proven mechanism (single m4a + range
// requests) and the four BINDING iOS rules of DESIGN §6:
//   1. resume seeks apply on loadedmetadata or later — never at page init
//   2. `ended` => server clears progress + marks read — never resume at EOF
//   3. progress saved server-side on pause/visibility-change + every ~5 s
//      while playing; saves suppressed until a pending resume has applied
//   4. skip via Media Session handlers — ±10 s per AMENDMENT_05 C1 (matches
//      Apple's default lock-screen icons; supersedes the ±15 s of v1)
import { useEffect, useRef, useState } from "react";

import * as api from "./api";
import RenderBar from "./RenderBar";

const SKIP_S = 10;
const SAVE_EVERY_MS = 5000;
const SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2];

function fmt(t) {
  if (!isFinite(t) || t < 0) return "0:00";
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60),
        s = Math.floor(t % 60);
  return (h ? `${h}:${String(m).padStart(2, "0")}` : `${m}`) +
         `:${String(s).padStart(2, "0")}`;
}

// paragraph playing at time t (offsets are sorted by t_start_s)
function paragraphAt(offsets, t) {
  if (!offsets?.paragraphs?.length) return -1;
  let lo = 0, hi = offsets.paragraphs.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (offsets.paragraphs[mid].t_start_s <= t) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

export default function Player({ story, detail, voices, autoplay, job,
                                 onFinished, onSkipped, onReadMarked, onRated,
                                 onVoiceChanged, onRenderChanged }) {
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
  const [skipMenu, setSkipMenu] = useState(false);
  const [rerenderNote, setRerenderNote] = useState("");
  const [bookmarks, setBookmarks] = useState(detail?.bookmarks || []);

  useEffect(() => setBookmarks(detail?.bookmarks || []), [detail]);

  // -- load + resume (rules 1 and 3) --
  useEffect(() => {
    const audio = audioRef.current;
    endedRef.current = false;
    pendingSeekRef.current = null;
    setNow(0);
    setDuration(story.duration_s || 0);
    setResumeNote("");
    setSkipMenu(false);
    setRerenderNote("");
    setPlaying(false); // never claim playback that isn't happening (A05 C2)
    let cancelled = false;
    api.getProgress(story.id).then(({ position_s }) => {
      if (cancelled || position_s == null) return;
      pendingSeekRef.current = position_s;
      setResumeNote(`resuming at ${fmt(position_s)}`);
      applyPendingSeek(); // metadata may already be loaded
    }).catch(() => {}); // no progress -> start at 0
    audio.src = `/api/stories/${story.id}/audio`;
    audio.load();
    // switching stories mid-play keeps playing (AMENDMENT_05 C2); the
    // element was blessed by the original gesture, so play() is allowed
    if (autoplay) audio.play().catch(() => setPlaying(false));
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

  // -- Media Session (rule 4, ±10 s) --
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

  // -- text follows playback (AMENDMENT_05 C5) --
  const currentPara = showText ? paragraphAt(detail?.offsets, now) : -1;
  useEffect(() => {
    if (currentPara < 0) return;
    document.getElementById(`para-${currentPara}`)
      ?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [currentPara]);

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

  async function skipAs(kind) {
    setSkipMenu(false);
    if (kind === "skip") {
      await api.skipStory(story.id);
      onSkipped(story.id);
    } else if (kind === "read") {
      await api.markRead(story.id);
      onReadMarked(story.id);
    }
  }

  async function onBookmark() {
    const note = window.prompt("Bookmark note (optional):") ?? null;
    const { id } = await api.addBookmark(story.id, now, note || null);
    setBookmarks((b) =>
      [...b, { id, position_s: now, note }].sort(
        (x, y) => x.position_s - y.position_s));
  }

  // voice re-render (AMENDMENT_05 C6), always behind a confirmation popup
  const voiceOptions = voices?.[story.language] || [];
  async function onVoicePick(v) {
    if (v === story.voice) return;
    const mins = Math.max(1, Math.round((story.duration_s || 300) / 60 / 7));
    if (!window.confirm(
      `Re-render "${story.title}" with ${v}? $0, ~${mins} min in the ` +
      "background; current audio keeps playing until it's replaced.")) return;
    await api.setVoice(story.id, v);
    setRerenderNote(`re-rendering with ${v} (~${mins} min) — this audio keeps ` +
      "playing; the new voice appears when the story shows ready again");
    onVoiceChanged(story.id, v);
  }

  return (
    <div className="player">
      <audio ref={audioRef} preload="metadata" />
      <div className="np-title">{story.title}</div>
      <div className="np-sub">
        {story.author || "unknown"}
        {story.year ? ` · ${story.year}` : ""} · {fmt(duration)}
      </div>
      {resumeNote && <div className="resume-note">{resumeNote}</div>}

      <input className="scrubber" type="range" min="0" max={duration || 0}
             step="0.1" value={Math.min(now, duration || 0)}
             onChange={(e) => seekTo(Number(e.target.value))} />
      <div className="times"><span>{fmt(now)}</span><span>-{fmt((duration || 0) - now)}</span></div>

      <div className="controls">
        <button className="ctl" onClick={() => nudge(-SKIP_S)}>−10s</button>
        <button className="ctl big" onClick={toggle}>{playing ? "⏸" : "▶"}</button>
        <button className="ctl" onClick={() => nudge(SKIP_S)}>+10s</button>
      </div>

      <div className="row">
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
          {SPEEDS.map((s) => <option key={s} value={s}>{s}×</option>)}
        </select>
        {voiceOptions.length > 1 && (
          <select value={story.voice || ""} title="voice"
                  onChange={(e) => onVoicePick(e.target.value)}>
            {story.voice && !voiceOptions.some((v) => v.voice === story.voice) &&
              <option value={story.voice}>{story.voice}</option>}
            {voiceOptions.map((v) => (
              <option key={v.voice} value={v.voice}>{v.voice}</option>
            ))}
          </select>
        )}
        <button onClick={onBookmark}>🔖</button>
        <button onClick={() => setShowText(!showText)}>
          {showText ? "hide text" : "text"}
        </button>
        <button className="danger" onClick={() => setSkipMenu(true)}>remove ✕</button>
      </div>

      {skipMenu && (
        <div className="skip-menu">
          <span>Remove “{story.title}”?</span>
          <button className="danger" onClick={() => skipAs("skip")}>
            Not interested (skip)
          </button>
          <button onClick={() => skipAs("read")}>Already read</button>
          <button onClick={() => setSkipMenu(false)}>Cancel</button>
        </div>
      )}

      {/* AMENDMENT_06: the live bar replaces the text note as soon as the
          spawned render registers its job (a second or two after the pick) */}
      {job
        ? <RenderBar job={job} story={story} onChanged={onRenderChanged} />
        : rerenderNote && <div className="resume-note">{rerenderNote}</div>}

      <div className="rating-row">
        <Stars rating={story.rating} onRate={(s) =>
          api.rate(story.id, s).then(() => onRated(story.id, s))} />
        {story.rating != null && (
          // rating misclick recovery (Grace, 2026-07-18, item 3)
          <button className="clear-rating" title="clear rating" onClick={() =>
            api.clearRating(story.id).then(() => onRated(story.id, null))}>
            clear
          </button>
        )}
      </div>

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
          {detail.paragraphs.map((p, i) => (
            <p key={i} id={`para-${i}`}
               className={i === currentPara ? "para-now" : undefined}>{p}</p>
          ))}
        </div>
      )}
    </div>
  );
}

export function Stars({ rating, onRate, readOnly = false }) {
  return (
    <div className="stars">
      {[1, 2, 3, 4, 5].map((s) => (
        <button key={s} className={s <= (rating || 0) ? "star on" : "star"}
                disabled={readOnly}
                onClick={() => !readOnly && onRate(s)}>★</button>
      ))}
    </div>
  );
}
