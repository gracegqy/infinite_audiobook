// AMENDMENT_06: live render progress + pause/resume/cancel, on every story
// being rendered — a first render from the queue and a voice re-render use the
// same job row, so the same bar covers both.
//
// Controls act at the next paragraph boundary (a paragraph render is not
// interruptible), so the button shows a pending state until the pipeline
// acknowledges. Fetch/tag/encode phases have no measurable total and render an
// indeterminate bar rather than a fabricated percentage.
import { useState } from "react";

import * as api from "./api";

const PHASE_LABEL = {
  fetching: "downloading text",
  tagging: "tagging",
  synthesizing: "rendering audio",
  encoding: "encoding audio",
};

export default function RenderBar({ job, story, onChanged }) {
  const [busy, setBusy] = useState(null);
  if (!job) return null;

  const paused = job.state === "paused";
  const pending = job.control !== "run" && !paused;
  const pct = job.fraction == null ? null : Math.round(job.fraction * 100);

  const act = (fn, label) => {
    setBusy(label);
    fn(job.story_id)
      .then(() => onChanged && onChanged())
      .catch(() => {})
      .finally(() => setBusy(null));
  };

  return (
    <div className="render">
      <div className={pct == null ? "render-track indet" : "render-track"}>
        <div className="render-fill"
             style={pct == null ? undefined : { width: `${pct}%` }} />
      </div>
      <div className="render-row">
        <span className="render-label">
          {paused ? "paused" : PHASE_LABEL[job.phase] || job.phase}
          {pct != null &&
            ` · ${job.paragraphs_done}/${job.paragraphs_total} ¶ (${pct}%)`}
          {job.voice ? ` · ${job.voice}` : ""}
          {pending && " · finishing this paragraph…"}
        </span>
        <span className="render-actions">
          {paused ? (
            <button disabled={busy} onClick={() => act(api.resumeRender, "resume")}>
              resume
            </button>
          ) : (
            <button disabled={busy || pending}
                    onClick={() => act(api.pauseRender, "pause")}>
              pause
            </button>
          )}
          <button className="danger" disabled={busy}
                  onClick={() => {
                    // cancel is safe by construction (the audio file is only
                    // written after the last paragraph) but it does throw away
                    // the work so far — worth one confirm
                    if (window.confirm(
                      `Cancel the render of "${story?.title || job.story_id}"? ` +
                      "Progress so far is discarded; any existing audio is kept."))
                      act(api.cancelRender, "cancel");
                  }}>
            cancel
          </button>
        </span>
      </div>
    </div>
  );
}
