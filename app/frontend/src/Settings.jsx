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
      <div className="card">
        <div className="card-main">
          <select value={s.curation_mode}
                  onChange={(e) => save({ curation_mode: e.target.value })}>
            {(s.curation_mode_options || []).map((m) => (
              <option key={m} value={m}>
                {m === "catalog"
                  ? "catalog — free"
                  : "llm — paid, better reputation"}
              </option>
            ))}
          </select>
          <div className="card-sub">
            {s.curation_mode === "catalog"
              ? "Builds the pool from Project Gutenberg's own catalog: $0, no API "
                + "call, and ebook ids come from the catalog so they are never "
                + "guessed wrong. Public-domain classics only — no creepypasta — "
                + "and reputation is Gutenberg's bookshelves and subject headings "
                + "rather than a critic's list, so expect some obscure pulp "
                + "alongside the canon."
              : "Paid curation with web search: verifies reputation against named "
                + "lists and covers both classics and modern web horror. Costs "
                + "roughly $0.2–0.5 per batch with caching on. Its weak point is "
                + "the ebook id, which it can still get wrong."}
          </div>
        </div>
      </div>

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
