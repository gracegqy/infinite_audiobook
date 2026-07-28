// Trends (Phase 6, DESIGN §8): what the ratings add up to, and whether that is
// actually reaching curation. Reads the SAME aggregation the curation prompt is
// built from (/api/taste returns taste.summary), so this screen cannot claim a
// preference the model was never told about.
import { useEffect, useState } from "react";

import * as api from "./api";

// Each row is (avg - 1) / 4 of the bar, i.e. 1/5 empty and 5/5 full, so a
// dislike reads as a short bar rather than as a missing one.
function barWidth(avg) {
  return `${Math.max(4, ((avg - 1) / 4) * 100)}%`;
}

function TagRow({ row, tone }) {
  return (
    <div className="taste-row">
      <div className="taste-label">
        {row.value} <span className="taste-kind">{row.kind}</span>
      </div>
      <div className="taste-bar">
        <span className={`taste-fill ${tone}`} style={{ width: barWidth(row.avg) }} />
      </div>
      <div className="taste-num">
        {row.avg.toFixed(1)}
        <span className="taste-kind"> n={row.n}</span>
      </div>
    </div>
  );
}

export default function Trends() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getTaste().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>loading…</p>;

  const { liked, disliked, rated_story_count: rated } = data;
  const short = rated < data.min_ratings_for_signal;

  return (
    <div className="list">
      {short ? (
        <p className="empty">
          {rated} of {data.min_ratings_for_signal} ratings needed before a taste
          profile is built. Below that, one rating would decide everything —
          rate a few more stories in the player.
        </p>
      ) : (
        <p className="card-sub taste-intro">
          From {rated} rated {rated === 1 ? "story" : "stories"}
          {data.channel ? ` on “${data.channel}”` : ""}. <strong>n</strong> is
          how many stories back each figure — a single 5 counts for far less
          than a steady 4.
        </p>
      )}

      {/* Stated plainly, because it is conditional: `free` mode makes no model
          call, so ratings genuinely cannot steer it. */}
      {!short && !data.applies_to_curation && (
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
            <TagRow key={`${r.kind}:${r.value}`} row={r} tone="good" />
          ))}
        </div>
      )}

      {disliked.length > 0 && (
        <div>
          <h2 className="group">disliked</h2>
          {disliked.map((r) => (
            <TagRow key={`${r.kind}:${r.value}`} row={r} tone="bad" />
          ))}
        </div>
      )}

      {!short && liked.length === 0 && disliked.length === 0 && (
        <p className="empty">
          Ratings so far agree on nothing — no tag stands out either way.
        </p>
      )}

      {data.profile_text && (
        <details className="taste-raw">
          <summary>what the curator is actually sent</summary>
          <pre>{data.profile_text}</pre>
        </details>
      )}
    </div>
  );
}
