# STATE — horror_readaloud        Reconciled through JOURNAL Entry 13 · 2026-07-18

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
- TTS language gates (probe 1c, Entries 12–13): **fr OPEN** (Kokoro ff_siwis passed
  Grace's ear); **zh: Kokoro FAILED** ("weird accents", both first-round voices —
  model-level). zh candidates awaiting Grace's listen: 6 remaining Kokoro voices +
  edge-tts native Azure voices ($0, cloud, unofficial endpoint — needs fallback if
  adopted). Local no-cloud tier if those fail: CosyVoice2-0.5B / Fish Speech /
  IndexTTS-2, each needing its own probe. TTS engine will be per-language config.
  ja untested.

## Next actions

1. Grace: zh round-2 listen at http://100.117.147.107:8765/audio/probe1c/ —
   start with the ceiling: zh_edgetts_xiaoxiao.mp3 + zh_edgetts_yunxi.mp3 (native
   Azure voices, $0, cloud caveats); then, only if curious whether local Kokoro is
   salvageable, the six zh_original_zm_*/zf_*.m4a voices. Verdict options:
   (a) edge-tts passes → zh primary = edge-tts w/ fallback, (b) nothing passes →
   probe CosyVoice2 locally next session, (c) drop zh channels for now.
2. Grace: review DESIGN v0.2 (§7 queue, §5 source tiers + DRM boundary, §9
   rulings). Sign-off + the zh pick freeze DESIGN (as v0.3 with per-language TTS
   config) + bind AMENDMENTS 02/03, closing Phase 2.
3. After sign-off: stop the probe-5 server, then Phase 3 pipeline MVP per TASKS —
   one story end-to-end against the frozen schema, unit + round-trip tests same
   day. (Reddit app creation can wait until NoSleep matters.)

## Open decisions

- zh TTS engine: Grace's round-2 pick — edge-tts (native, $0, cloud/unofficial
  caveats) vs. best remaining Kokoro voice vs. probe CosyVoice2 vs. drop zh (Entry
  13). fr is decided: Kokoro. TTS becomes per-language config in v0.3 either way.
- All v0.1 §9 decisions are RULED (Entry 12) and encoded in DESIGN v0.2 + AMENDMENTS
  02/03 (proposed) — they bind at sign-off, nothing else is open.
