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

      <h2 className="group">Spending limit</h2>
      <SpendCap s={s} onSave={save} />

      <h2 className="group">Replenishment schedule</h2>
      <WorkerInterval s={s} onSave={save} />

      <h2 className="group">Off-machine backup</h2>
      <OffsiteBackup s={s} onSave={save} />

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

// Entry 37 (ii). Both the cap and its window are stored settings, so the number
// is never in the code. An explicit Apply rather than save-on-change: typing
// "2" on the way to "20" would otherwise store a cap of 2 mid-keystroke.
function SpendCap({ s, onSave }) {
  const [cap, setCap] = useState(String(s.spend_cap_usd ?? ""));
  useEffect(() => { setCap(String(s.spend_cap_usd ?? "")); },
            [s.spend_cap_usd]);
  const dirty = String(s.spend_cap_usd ?? "") !== cap;
  const pct = s.unlimited || !s.spend_cap_usd
    ? 0 : Math.min(100, (s.spent_in_period / s.spend_cap_usd) * 100);
  return (
    <div className="card">
      <div className="card-main">
        <div className="card-row">
          <label>Cap $
            <input type="number" min="0" step="0.50" value={cap} inputMode="decimal"
                   onChange={(e) => setCap(e.target.value)} />
          </label>
          <label>per
            <select value={s.spend_cap_period}
                    onChange={(e) => onSave({ spend_cap_period: e.target.value })}>
              {s.spend_cap_period_options.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
          <button disabled={!dirty}
                  onClick={() => onSave({ spend_cap_usd: Number(cap) })}>
            Apply
          </button>
        </div>

        {s.unlimited ? (
          <div className="card-sub">No cap set (0 = unlimited). Pool builds are
            still Grace-initiated only — nothing spends on its own.</div>
        ) : (
          <>
            <div className="meter"><span style={{ width: `${pct}%` }} /></div>
            <div className="card-sub">
              ${s.spent_in_period?.toFixed(4)} spent in the last{" "}
              {s.spend_cap_period}; ${s.remaining?.toFixed(4)} left.
              {s.exhausted && " ⚠ The next paid pool build will be refused."}
            </div>
          </>
        )}
        <div className="card-sub">
          Counts what this app recorded spending — it cannot see your Anthropic
          balance, so running out of credit is a separate error.
        </div>
      </div>
    </div>
  );
}

// Entry 37 (i). The launchd job carries no cadence of its own; the worker
// re-reads this value every cycle, so a change here applies on the next tick
// without a restart.
function WorkerInterval({ s, onSave }) {
  const [v, setV] = useState(String(s.worker_interval_s ?? ""));
  useEffect(() => { setV(String(s.worker_interval_s ?? "")); },
            [s.worker_interval_s]);
  const mins = Math.round((Number(v) || 0) / 60);
  const dirty = String(s.worker_interval_s ?? "") !== v;
  return (
    <div className="card">
      <div className="card-main">
        <div className="card-row">
          <label>Check the queue every
            <input type="number" min={s.worker_interval_min_s} step="60"
                   value={v} inputMode="numeric"
                   onChange={(e) => setV(e.target.value)} />
            s
          </label>
          <button disabled={!dirty}
                  onClick={() => onSave({ worker_interval_s: Number(v) })}>
            Apply
          </button>
        </div>
        <div className="card-sub">
          ≈ {mins} min. Minimum {s.worker_interval_min_s}s. Applies on the next
          cycle — no restart needed. The worker only consumes the already-paid
          pool, so the schedule can never spend money.
        </div>
      </div>
    </div>
  );
}

// Entry 37. OFF until you name a destination. The suggestion is a placeholder,
// never a default: an off-machine copy is your listening history leaving this
// Mac, so the path is yours to choose. Blank turns it off again.
function OffsiteBackup({ s, onSave }) {
  const [dir, setDir] = useState(s.backup_offsite_dir ?? "");
  useEffect(() => { setDir(s.backup_offsite_dir ?? ""); },
            [s.backup_offsite_dir]);
  const on = Boolean(s.backup_offsite_dir);
  const dirty = (s.backup_offsite_dir ?? "") !== dir;
  return (
    <div className="card">
      <div className="card-main">
        <div className="card-row">
          <input type="text" className="wide" value={dir}
                 placeholder={s.backup_offsite_suggestion}
                 onChange={(e) => setDir(e.target.value)} />
          <button disabled={!dirty}
                  onClick={() => onSave({ backup_offsite_dir: dir })}>
            {dir.trim() ? "Apply" : "Turn off"}
          </button>
        </div>
        <div className="card-sub">
          {on
            ? `On — each snapshot is copied there and verified at the destination.`
            : "Off. Snapshots stay in backups/ on this Mac, which covers "
              + "corruption and bad migrations but NOT losing the Mac. Any "
              + "path works: a cloud folder, an external disk, a NAS mount."}
        </div>
        <div className="card-sub">
          Contains titles, ratings and resume positions. Never your API keys —
          those live in .env and are not in the database.
        </div>
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
