# STATE — horror_readaloud        Reconciled through JOURNAL Entry 12 · 2026-07-18

> PURE CURRENT STATE. No history (JOURNAL's job), no session summaries. Superseded content
> is DELETED, not annotated.

## Phase table

| Phase | Status | Gate | Gate evidence (command/check + result) |
|---|---|---|---|
| 0 — Scaffold | DONE | Scaffold gate (TASKS.md §0) | all items re-verified from artifacts 2026-07-18 (Entry 3); Grace review approved (Entry 4) |
| 1 — Pre-design probes | DONE | All 6 probe questions answered in probe_results.txt | All six answered (probe_results.txt gate block; Entries 5–11); probe 5 closed on Grace's four phone reports; one deferral w/ risk note (≥5-min backgrounding → Phase 4 gate) |
| 2 — Design | IN PROGRESS | DESIGN.md frozen; Grace sign-off | v0.2 draft encodes Grace's rulings + AMENDMENTS 02/03 (proposed); sign-off awaits her probe-1c zh/fr listen + v0.2 review (Entry 12) |
| 3 — Pipeline MVP | not started | One story end-to-end, playable audio + offsets | — |
| 4 — Player MVP | not started | Full listen on phone over Tailscale | — |
| 5 — Queue + sync + channels | not started | Queue self-heals to 5; sync visible on phone | — |
| 6 — Preference adaptation | not started | Curation demonstrably weighted by ratings | — |
| 7 — Hardening | not started | Fresh-session audit + runbook complete | — |

## Confirmed findings

- Sourcing = classics + modern web fiction, private-use only; TTS = Kokoro-local first
  with OpenAI fallback; hosting = Mac + Tailscale; Anthropic + OpenAI keys exist
  (interview, docs/BRIEF_VERBATIM.md).
- Pipeline is channel-driven (editable genre/language/topic criteria), not
  horror-hardcoded (docs/AMENDMENT_01).
- Git identity/remote conventions: personal repos use account `gracegqy`, identity
  Grace / graceguqianying@uchicago.edu (verified across ACTIVE repos, `git config` +
  `git remote -v`). GitHub credential present in macOS keychain (`git credential fill`
  returned a password for github.com).
- Kokoro runs locally at ~6.9x realtime (probe 1, 2026-07-18); per-paragraph
  synthesis + concat gives exact offsets (probe 2, energy-check verified). Quality
  verdict pending Grace's listen.
- Curation signal is real: named checkable reputation lists for both classic and
  NoSleep channels; PD/modern classification correct on 3 hand spot-checks (probe 3).
- Gutenberg + creepypasta-wiki fetch/clean work (with empty/deleted-page validation
  needed); Reddit anonymous JSON API is dead — OAuth app or HTML parsing required
  (probe 4; decision in Phase 2).
- Kokoro "random pauses" bug root-caused: newline-split chunking from hard-wrapped
  input text, fixed by whitespace normalization (probe 1b). Design constraint: clean
  stage must unwrap lines within paragraphs. Grace re-listens to *_fixed.* files.
- OpenAI TTS fallback confirmed working: $0.004/paragraph, ~$0.32/30-min story
  (probe 6, 2026-07-18).
- Tailscale installed on Mac + iPhone; Mac Tailscale IP 100.117.147.107. Probe 5
  server running on it (page 200, range 206 re-verified from Mac, Entry 9).
- iOS lock-screen/Media-Session controls work: title shows, skip buttons perform the
  handler's ±15s (icons cosmetically show Apple's default "10s"); playbackRate honored
  (R13 viable). Sustained ≥5-min backgrounding deferred w/ risk note to the Phase 4
  gate (Entry 11).
- iOS resume works on the real target: kill Safari + reopen resumes at saved position,
  scrubbing works (Grace retest, Entry 9). Design rules: apply resume seeks
  loadedmetadata-or-later, never at page init; AND on `ended`, clear/complete the
  resume position and mark the story read — never persist end-of-file as a resume
  point (Entry 10: a finished story "resumed" to its end, causing instant
  ended→pause that looked like broken playback).
- .env exists with both keys (verified gitignored).
- Kokoro zh works mechanically: misaki[zh] installs clean, renders 5.3–5.7x realtime
  (two voices); fr 5.0x with no extra deps (probe 1c, Entry 12). Quality verdicts =
  Grace's ear, pending. ja untested.

## Next actions

1. Grace: (a) listen to the three probe-1c samples (phone or Mac, server live):
   http://100.117.147.107:8765/audio/probe1c/zh_original_zf_xiaobei.m4a ·
   .../zh_original_zm_yunxia.m4a · .../fr_lehorla_ff_siwis.m4a — native-ear verdict
   on zh (tones/prosody/horror register), learner-ear on fr; (b) review DESIGN v0.2
   (esp. §7 queue-as-you-proposed, §5 source tiers + DRM boundary, §9 rulings as
   encoded). Sign-off freezes DESIGN.md + binds AMENDMENTS 02/03, closing Phase 2.
2. After sign-off: stop the probe-5 server (its job is done), then Phase 3 pipeline
   MVP per TASKS — one story end-to-end against the frozen schema, unit + round-trip
   tests same day. (Reddit app creation can wait until NoSleep matters.)

## Open decisions

- zh/fr channel go/no-go = Grace's probe-1c listening verdict (any failed language
  falls back to OpenAI TTS per story, or drops).
- All v0.1 §9 decisions are RULED (Entry 12) and encoded in DESIGN v0.2 + AMENDMENTS
  02/03 (proposed) — they bind at sign-off, nothing else is open.
