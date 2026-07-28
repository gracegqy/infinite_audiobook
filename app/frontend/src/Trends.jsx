// Trends (Phase 6, DESIGN §8): what the ratings add up to, and whether that is
// actually reaching curation. Reads the SAME aggregation the curation prompt is
// built from (/api/taste returns taste.summary), so this screen cannot claim a
// preference the model was never told about.
//
// Entry 35: the figures are also editable. A manual score overrides the
// computed one, ✕ suppresses a tag, and "add" states a preference the ratings
// never produced. Overrides persist until reverted — they apply to every future
// batch, not just the next one.
import { useEffect, useState } from "react";

import * as api from "./api";

// Each row is (avg - 1) / 4 of the bar, i.e. 1/5 empty and 5/5 full, so a
// dislike reads as a short bar rather than as a missing one.
function barWidth(avg) {
  return `${Math.max(4, ((avg - 1) / 4) * 100)}%`;
}

function TagRow({ row, tone, onChanged }) {
  const [busy, setBusy] = useState(false);

  async function act(fn) {
    setBusy(true);
    try {
      await fn();
      await onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="taste-row">
      <div className="taste-label">
        {row.value} <span className="taste-kind">{row.kind}</span>
        {row.manual && <span className="taste-manual">set by you</span>}
      </div>
      <div className="taste-bar">
        <span className={`taste-fill ${tone}`} style={{ width: barWidth(row.avg) }} />
      </div>
      <select className="taste-score" value={row.avg.toFixed(1)} disabled={busy}
              onChange={(e) =>
                act(() => api.setTaste(row.kind, row.value,
                                       Number(e.target.value)))}>
        {["1.0", "2.0", "3.0", "4.0", "5.0"].map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
        {/* the computed value is rarely a whole number — keep it selectable */}
        {!["1.0", "2.0", "3.0", "4.0", "5.0"].includes(row.avg.toFixed(1)) && (
          <option value={row.avg.toFixed(1)}>{row.avg.toFixed(1)}</option>
        )}
      </select>
      <span className="taste-kind taste-n">{row.manual ? "—" : `n=${row.n}`}</span>
      {row.manual ? (
        <button className="clear-rating" disabled={busy} title="back to automatic"
                onClick={() => act(() => api.clearTaste(row.kind, row.value))}>
          ↺
        </button>
      ) : (
        <button className="clear-rating" disabled={busy} title="drop from profile"
                onClick={() => act(() => api.suppressTaste(row.kind, row.value))}>
          ✕
        </button>
      )}
    </div>
  );
}

function AddForm({ kinds, onChanged }) {
  const [kind, setKind] = useState("subgenre");
  const [value, setValue] = useState("");
  const [score, setScore] = useState("5.0");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!value.trim()) return;
    setBusy(true);
    try {
      await api.setTaste(kind, value.trim(), Number(score));
      setValue("");
      await onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="taste-add" onSubmit={submit}>
      <select value={kind} onChange={(e) => setKind(e.target.value)}>
        {kinds.map((k) => <option key={k} value={k}>{k}</option>)}
      </select>
      <input value={value} placeholder="e.g. ghost-stories"
             onChange={(e) => setValue(e.target.value)} />
      <select value={score} onChange={(e) => setScore(e.target.value)}>
        {["1.0", "2.0", "3.0", "4.0", "5.0"].map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
      <button disabled={busy || !value.trim()}>add</button>
    </form>
  );
}

export default function Trends() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = () => api.getTaste().then(setData).catch((e) => setError(String(e)));
  useEffect(() => { load(); }, []);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>loading…</p>;

  const { liked, disliked, rated_story_count: rated } = data;
  const short = rated < data.min_ratings_for_signal;
  const hasManual = [...liked, ...disliked].some((r) => r.manual);

  return (
    <div className="list">
      {short && !hasManual ? (
        <p className="empty">
          {rated} of {data.min_ratings_for_signal} ratings needed before a taste
          profile is built automatically. Below that, one rating would decide
          everything — rate a few more stories, or state a preference directly
          below.
        </p>
      ) : (
        <p className="card-sub taste-intro">
          From {rated} rated {rated === 1 ? "story" : "stories"}
          {data.channel ? ` on “${data.channel}”` : ""}. <strong>n</strong> is
          how many stories back each figure. Change a score to override it, ✕
          drops a tag, ↺ returns it to automatic — edits apply to every future
          batch until you revert them.
        </p>
      )}

      {/* Stated plainly, because it is conditional: `free` mode makes no model
          call, so ratings genuinely cannot steer it. */}
      {!data.applies_to_curation && (
        <p className="notice">
          Curation mode is <strong>{data.curation_mode}</strong>, which makes no
          model call — these preferences are <strong>not</strong> reaching
          curation. Switch to <strong>free sources + AI picks</strong> in
          Settings to have them count.
        </p>
      )}

      {liked.length > 0 && (
        <div>
          <h2 className="group">liked</h2>
          {liked.map((r) => (
            <TagRow key={`${r.kind}:${r.value}`} row={r} tone="good"
                    onChanged={load} />
          ))}
        </div>
      )}

      {disliked.length > 0 && (
        <div>
          <h2 className="group">disliked</h2>
          {disliked.map((r) => (
            <TagRow key={`${r.kind}:${r.value}`} row={r} tone="bad"
                    onChanged={load} />
          ))}
        </div>
      )}

      <h2 className="group">state a preference</h2>
      <AddForm kinds={data.kinds} onChanged={load} />

      {data.profile_text && (
        <details className="taste-raw">
          <summary>what the curator is actually sent</summary>
          <pre>{data.profile_text}</pre>
        </details>
      )}
    </div>
  );
}
