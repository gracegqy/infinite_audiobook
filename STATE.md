# STATE — horror_readaloud        Reconciled through JOURNAL Entry 5 · 2026-07-18

> PURE CURRENT STATE. No history (JOURNAL's job), no session summaries. Superseded content
> is DELETED, not annotated.

## Phase table

| Phase | Status | Gate | Gate evidence (command/check + result) |
|---|---|---|---|
| 0 — Scaffold | DONE | Scaffold gate (TASKS.md §0) | all items re-verified from artifacts 2026-07-18 (Entry 3); Grace review approved (Entry 4) |
| 1 — Pre-design probes | IN PROGRESS | All 6 probe questions answered in probe_results.txt | probes 2+4 + 3's signal half answered with recorded evidence (probe_results.txt, Entry 5); rest blocked on Grace inputs |
| 2 — Design | not started | DESIGN.md frozen; Grace sign-off | — |
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
- Tailscale is NOT installed on this Mac (probe 5, contradicts brief assumption) —
  blocks phone-target testing until Grace installs it on Mac + iPhone.
- No .env yet; Anthropic/OpenAI keys obtained by Grace 2026-07-18 but not yet placed.

## Next actions (all on Grace; scripts are ready to run)

1. Put API keys in `.env` (project root: `ANTHROPIC_API_KEY=…` / `OPENAI_API_KEY=…`),
   then have a session run `probe3_curation_api.py` and `probe6_openai_tts.py`.
2. Listening test: data/interim/probe1/*.wav (≥2 min horror sample, male-voice + Spanish
   variants) and data/interim/probe2/concat_A_buttjoin.wav (seam check).
3. Install Tailscale on Mac + iPhone (same tailnet) → run probe 5 phone test
   (instructions in probe_results.txt §5).
4. When all six probes are answered: close Phase 1 gate, start Phase 2 design.

## Open decisions

- Queue semantics under multiple channels: one global queue of 5 vs. 5 per active channel
  (Phase 2; default assumption = queue of 5 for the active channel).
- Frontend PWA offline caching of audio (nice-to-have; decide in Phase 4).
