// Settings screen (DESIGN §6, unlocked by AMENDMENT_05 A): curation model
// selector (R14 — never auto-switched; the quality notice only ever points
// here) and per-language default voices for future renders.
import { useEffect, useState } from "react";

import * as api from "./api";

export default function Settings() {
  const [s, setS] = useState(null);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState("");

  useEffect(() => {
    api.getSettings().then(setS).catch((e) => setError(String(e)));
  }, []);

  async function save(body) {
    try {
      setS(await api.putSettings(body));
      setSaved("saved");
      setTimeout(() => setSaved(""), 1500);
    } catch (e) {
      setError(String(e));
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!s) return <p>loading…</p>;

  return (
    <div className="list settings">
      {s.quality_notice && (
        <div className="notice">⚠ {s.quality_notice}</div>
      )}

      <h2 className="group">Curation model</h2>
      <div className="card">
        <div className="card-main">
          <select value={s.curation_model}
                  onChange={(e) => save({ curation_model: e.target.value })}>
            {s.curation_model_options.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
          <div className="card-sub">
            Used for paid pool builds only; changes are never automatic.
          </div>
        </div>
      </div>

      <h2 className="group">Default voice per language</h2>
      {Object.entries(s.default_voices).map(([lang, voice]) => (
        <div key={lang} className="card">
          <div className="card-main">
            <div className="card-title">{lang}</div>
            <div className="card-sub">applies to future renders; existing
              stories re-render via the player's voice picker</div>
          </div>
          <VoicePick lang={lang} value={voice}
                     onPick={(v) => save({ default_voices: { [lang]: v } })} />
        </div>
      ))}
      {saved && <p className="empty">{saved}</p>}
    </div>
  );
}

function VoicePick({ lang, value, onPick }) {
  const [voices, setVoices] = useState(null);
  useEffect(() => {
    api.listVoices().then((v) => setVoices(v.languages[lang] || []))
      .catch(() => setVoices([]));
  }, [lang]);
  if (!voices) return null;
  return (
    <select value={value || ""} onChange={(e) => onPick(e.target.value)}>
      {voices.map((v) => <option key={v.voice} value={v.voice}>{v.voice}</option>)}
    </select>
  );
}
