// Settings screen (DESIGN §6, unlocked by AMENDMENT_05 A): curation MODE
// (free catalog vs paid LLM — Entry 29), curation model selector (R14 — never
// auto-switched; the quality notice only ever points here) and per-language
// default voices for future renders.
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

      <h2 className="group">Curation mode</h2>
      <CurationMode s={s} onPick={(m) => save({ curation_mode: m })} />

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

// Labels, costs and source coverage all come from /api/settings — the previous
// version hardcoded two mode descriptions here and they described the wrong
// thing the moment a third mode existed. Coverage is per ACTIVE CHANNEL: a
// non-horror channel must be able to see that the horror-only source is off.
function CurationMode({ s, onPick }) {
  const modes = s.curation_modes || [];
  const current = modes.find((m) => m.mode === s.curation_mode);
  const sources = current?.sources;
  return (
    <div className="card">
      <div className="card-main">
        <select value={s.curation_mode} onChange={(e) => onPick(e.target.value)}>
          {modes.map((m) => (
            <option key={m.mode} value={m.mode}>{m.label}</option>
          ))}
        </select>
        <div className="card-sub">{current?.description}</div>

        {sources && (
          <div className="card-sub">
            {current.available
              ? "Free sources for this channel:"
              : "⚠ No free source covers this channel — a pool build in this "
                + "mode will stop with an explanation instead of running. "
                + "Switch to AI web search, or add a source."}
            <ul className="sources">
              {sources.map((src) => (
                <li key={src.name} className={src.covers ? "on" : "off"}>
                  {src.covers ? "✓" : "—"} <strong>{src.name}</strong>: {src.reason}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
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
