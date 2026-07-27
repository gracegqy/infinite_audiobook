# AMENDMENT 06 — Render progress bar + pause/cancel controls (2026-07-27)

> **Authority: HIGHEST**, applied on top of BRIEF_VERBATIM.md + AMENDMENTS 01–05
> + DESIGN v1.0. Status: **BINDING** on arrival — this is Grace's direct
> instruction, not a proposal of mine (the A05 A/B pattern of "PROPOSED until
> flipped" applies only to things I propose). Never edited from here; further
> changes are new amendment docs.

## Verbatim (Grace, 2026-07-27)

> "can you show a progress bar whenever a re-render starts (as well as for new
> renders), and give pause and cancel buttons at any time for the
> renders/downloads?"

## Ruling

1. **Progress bar on every render**, first render and voice re-render alike.
   Both paths already run through `ingest._finalize`, so both are instrumented
   at the same seam rather than twice.
2. **Pause / resume / cancel available while a render is in flight**, from the
   queue card, the library card, and the player.
3. **Cancel restores the story exactly as it was** — pre-render status back,
   existing audio untouched. This closes a latent bug that predates the
   amendment: a mid-render abort left the row stranded at `fetching` (the
   Entry-21 Damned Thing hand-repair).

## Two honest limits (accepted, not worked around)

- **Control granularity is one paragraph.** A paragraph render is not
  interruptible, so pause and cancel take effect at the next paragraph
  boundary — typically a few seconds at Kokoro's ~6.9x realtime, longer on a
  long paragraph. The UI says "finishing this paragraph…" rather than pretending
  the click was instant.
- **Fetch/tag/encode have no measurable total.** A fetch is one HTTP GET of a
  whole story; there is nothing to divide. Those phases show an indeterminate
  sweep, never a fabricated percentage. Only the synthesis phase reports
  `n/total ¶`, which is exact.

## Scope note

A *brand-new* story's fetch is not cancellable: `render_jobs.story_id` is a
foreign key to `stories`, and on the fresh-candidate path the fetch happens
before the story row exists. Every UI-triggered render goes through
`retry_story`, where the row already exists and the whole walk is covered. The
Phase 5 worker acquires stories to `text_ready` and renders them separately, so
its renders are covered too.

## Design delta

`render_jobs` table (one row per story, rewritten per render) is the
cross-process channel between the detached render subprocess and the server:
the pipeline writes phase/progress and reads `control`; the server writes
`control` and reads progress. Liveness is derived from the pid, never trusted
from the row — a job whose process died is reaped, so a bar on screen always
means a live render.

Traceability: extends DESIGN §5 (synthesis) and §6 (player); no schema change
to any existing table; no change to offsets math or the iOS rules.
