# STATE — horror_readaloud        Reconciled through JOURNAL Entry 2 · 2026-07-18

> PURE CURRENT STATE. No history (JOURNAL's job), no session summaries. Superseded content
> is DELETED, not annotated.

## Phase table

| Phase | Status | Gate | Gate evidence (command/check + result) |
|---|---|---|---|
| 0 — Scaffold | IN PROGRESS | Scaffold gate (TASKS.md §0) | pending |
| 1 — Pre-design probes | not started | All 6 probe questions answered in probe_results.txt | — |
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

## Next actions

1. Finish Phase 0 gate: first commit, private remote pushed, .gitignore proven, smoke
   test run, Grace reviews STATE.md + CLAUDE.md.
2. Run Phase 1 probes (TASKS.md §1), starting with Kokoro install/quality — it's the
   biggest architectural unknown.

## Open decisions

- Queue semantics under multiple channels: one global queue of 5 vs. 5 per active channel
  (Phase 2; default assumption = queue of 5 for the active channel).
- Frontend PWA offline caching of audio (nice-to-have; decide in Phase 4).
