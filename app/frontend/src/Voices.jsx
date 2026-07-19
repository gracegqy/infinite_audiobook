// Voice audition gallery (AMENDMENT_04 D2): one pre-rendered sample per
// available voice — switching preview is instant and costs nothing per listen.
// Per-story voice choice lives in the queue (picker) or via explicit re-render
// from here later; this screen is audition only.
import { useEffect, useRef, useState } from "react";

import * as api from "./api";

export default function Voices() {
  const [languages, setLanguages] = useState(null);
  const [error, setError] = useState(null);
  const [playingVoice, setPlayingVoice] = useState(null);
  const audioRef = useRef(null);

  useEffect(() => {
    api.listVoices().then((v) => setLanguages(v.languages))
      .catch((e) => setError(String(e)));
  }, []);

  function preview(v) {
    const audio = audioRef.current;
    if (playingVoice === v.voice) {
      audio.pause();
      setPlayingVoice(null);
      return;
    }
    audio.src = v.sample_url;
    audio.play();
    setPlayingVoice(v.voice);
  }

  if (error) return <p className="error">{error}</p>;
  if (!languages) return <p>loading…</p>;

  return (
    <div className="list">
      <audio ref={audioRef} onEnded={() => setPlayingVoice(null)} />
      {Object.entries(languages).map(([lang, voices]) => (
        <div key={lang}>
          <h2 className="group">{lang}</h2>
          {voices.map((v) => (
            <div key={v.voice} className="card">
              <div className="card-main">
                <div className="card-title">
                  {v.voice}{v.default ? " · channel default" : ""}
                </div>
                {!v.sample_url && (
                  <div className="card-sub">
                    sample not rendered yet — scripts/render_voice_samples.py
                  </div>
                )}
              </div>
              {v.sample_url && (
                <button className="ctl" onClick={() => preview(v)}>
                  {playingVoice === v.voice ? "⏸" : "▶"}
                </button>
              )}
            </div>
          ))}
        </div>
      ))}
      <p className="empty">
        To change a story's voice: pick it in the queue before rendering, or
        re-render a finished story from the pipeline
        (retry --voice) — $0, ~5 min per story.
      </p>
    </div>
  );
}
