# AMENDMENT 04 — Curation cost ~$0, pre-extraction flow, chunking verdict, voice policy (2026-07-18)

> **Authority: HIGHEST**, applied on top of BRIEF_VERBATIM.md + AMENDMENTS 01–03 +
> DESIGN v1.0. Status: **FULLY BINDING** — parts A/B were Grace's directives,
> part D her explicit delegation, and part C (chunking declined, abort-on-skip
> adopted) approved by Grace 2026-07-18: "chunking verdict approved" (JOURNAL
> Entry 18). Never edited from here; further changes are new amendment docs.

## Verbatim (Grace, 2026-07-18)

(2) would it be a good idea to break queued stories into roughly 5-minute chunks,
given that producing the audio seems to take a long time to complete for the whole
text? it would also reduce the wasted cost on stories I dislike or skip. also, could
you make the final output show me the title of the next targeted extracted story even
before extraction begins, so that I could mark stories i recognize as already read
beforehand to save extraction cost? (3) sonnet api cost needs to be significantly
reduced - i can't spend $2 on a single story; ideally the cost should be close to 0.
try to find a cost-reducing solution for sonnet, and if that doesn't work, we could
use cheaper models like codex, kimi, or haiku

also: how would free voice selection work if the whole piece is extracted in advance?
would it make more sense to run the voice conversion in real time, caching maybe only
a few paragraphs at a time? you decide, critically, what design works best

## A. Pool-based curation (BINDING — Grace's cost directive)

Measured reality: $0.90–$2.13 per 8-candidate Sonnet batch; the driver is web-search
result tokens, not the search count, so knob-turning on Sonnet cannot reach "~$0 per
story". The fix is architectural — stop paying per replenishment:

- **Replenishment consumes a candidate POOL at $0 marginal.** curation_runs already
  stores every batch's candidates_json; the pipeline draws unconsumed candidates
  (title not yet in the all-time stories history) before ANY new API call.
- **Paid pool builds are rare, large, and Grace-initiated only** (`--build-pool`,
  ~40 candidates/run, cost printed). Extends R14's no-silent-model-change to
  no-silent-spend: an empty pool produces a notice with the cost estimate, never an
  automatic API call.
- Amortized target: ~$2 per ~40-candidate build ≈ **$0.05/story**, marginal
  per-story cost $0 (+~$0.01 tag call). Cheaper models (Haiku no-search) remain a
  Grace-selectable option for pool builds; cross-provider models (kimi etc.) are
  not added while an already-keyed option suffices.

## B. Pre-extraction visibility + pre-marking (BINDING — Grace's directive)

- The pipeline announces the next candidate (title/author/evidence) **before fetch
  begins**.
- New `pipeline.mark read|skip "<title>"` records the verdict as a permanent
  stories row (provisional dedup key when no text was ever fetched) — recognized/
  already-read stories are excluded from all future curation and never fetched or
  rendered. Extends AMENDMENT_02's "skips are permanent history" to the candidate
  stage, before any cost is incurred.

## C. ~5-minute audio chunks (DECLINED — approved by Grace 2026-07-18)

Assessment (Grace asked for critical): chunked delivery attacks costs that are
already ~zero, and pays real costs to do it —

- Wasted render cost is CPU-minutes, not money: en/fr Kokoro and zh edge-tts are $0;
  only the rare OpenAI-fallback story (~$0.32) has marginal cost.
- The Phase 5 worker pre-renders the queue in acquisition order ahead of listening,
  so render latency is invisible in steady state; today's foreground waiting is a
  Phase-3-CLI artifact, not the end-state UX.
- iOS Safari cannot gaplessly join separate files: every ~5-min boundary is an
  audible seam + a Media-Session/resume complication — re-opening exactly the
  fragile area probe 5 de-risked with single static files + range requests
  (probe-2's verdict: seams matter).

Adopted instead (captures ~all of the waste reduction, no format change):
- **Abort-render-on-skip**: synthesis checks the story's status between paragraphs;
  a skip/read mark mid-render aborts the remaining paragraphs immediately.
- Part B's pre-marking kills doomed candidates before any fetch/render.
Chunking is revisitable if on-demand listening (no pre-rendered queue) becomes the
common path.

## D. Voice selection policy (BINDING under Grace's delegation — "you decide")

Ruling: **pre-render stays; real-time voice conversion is declined.**

- Real-time synthesis makes every playback depend on a live render loop (Mac awake,
  Kokoro keeping ahead of up-to-2x playback (R13), and for zh an undocumented
  Microsoft endpoint being healthy mid-listen) — converting the accepted
  render-time edge-tts risk into a playback-time risk. It also requires streaming-
  stitched audio on iOS (MSE/segment juggling), reopening probe 5's hardest
  problems (background, lock-screen, scrubbing, resume), breaks seek-ahead into
  unrendered audio, and violates the frozen negative spec's "no per-listen API
  calls" (R11).
- Voice is a low-frequency preference, not a per-listen variable. Design:
  1. Voice is chosen **before synthesis** (channel default from config; per-story
     override while the story sits at text_ready in the queue window).
  2. **Voice audition gallery** (Phase 4 settings UI): one short sample paragraph
     pre-rendered once per available voice — switching preview is instant, costs
     nothing per listen.
  3. **Re-render on demand**: changing a rendered story's voice is an explicit
     action (retry path with a voice override) — a $0 background re-render,
     ~5 min/story, never blocking playback of the existing audio.

## Implementation notes

`pipeline/pool.py` (pool draw), `pipeline/mark.py` (pre-marking CLI),
`record_provisional` in ingest, `should_abort` hook + `AbortRender` in synthesize,
`retry --voice <voice>` re-render, run_story announces next-up + `--build-pool`.
Voice gallery + queue-window voice picker land with the Phase 4 UI.
