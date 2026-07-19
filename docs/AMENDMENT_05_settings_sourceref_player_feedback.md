# AMENDMENT 05 — Settings table, stored source_ref, phone-gate player feedback (2026-07-18)

> **Authority: HIGHEST**, applied on top of BRIEF_VERBATIM.md + AMENDMENTS 01–04 +
> DESIGN v1.0. Status: **part C BINDING** (Grace's phone-test directives, verbatim
> below, implemented same day); **parts A/B PROPOSED** — schema changes on the
> frozen design, drafted under Grace's go-ahead ("2. approved", 2026-07-18) but
> awaiting her explicit sign-off before any code writes to them. Never edited from
> here; further changes are new amendment docs.

## Verbatim (Grace, 2026-07-18, after the Phase 4 phone test)

1. tested. 1) could you change +-15s to +-10s to match the apple default ui?
2) minor note: when I switch stories mid-play without pausing the current one
first, the new one's audio doesn't play automatically, but its icon appears as if
the play is in progress by default. 3) skip doesn't distinguish between "don't
like" and "already read", which may affect preference adaptation. 4) "skipped"
can't be undone, which makes misclicks costly. add a way for me to manually flag
a revoke. 5) could "show text" automatically open on the line I'm listening to at
the moment? let me know if that'd be difficult. 6) there's a queue view, but I
don't get to pick the voice anywhere. there's only a "voices" page for me to test
play each voice, but they can't be applied anywhere, and there's no place to
change the default voices. also, what happens if I switch voice mid-render? could
you set it to abort the in-progress render and restart with my new chosen voice?
(with a confirmation popup for me beforehand) 7) killing safari mid-play reopened
with the audio progress saved, but the last-played stories doesn't automatically
appear on the top half of the screen. could you changte that? 8) minor:
capitalize "Queue", "Library", and "Voices" headers. 8) making story rating
editable when the story is not played risks misclicks. allow rating display in
library list view, but only allow edits when a story is in the current player.
9) could you make the header button strip ("Readaloud queue library voices")
persistent even when i scroll down a page? 10) no other issues spotted at this
stage. 2. approved

## A. `settings` table (PROPOSED — schema change, awaits sign-off)

```sql
settings(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT)
```

One key-value row per setting; all state stays in SQLite (DESIGN §1). Initial
keys: `curation_model` (R14 selector, §6 settings screen) and
`default_voice.<language>` (her item 6: "no place to change the default voices" —
overrides config.TTS_BY_LANGUAGE's voice half; engine choice stays config).
The §6 settings screen ships once this is BINDING.

## B. `stories.source_ref` column (PROPOSED — schema change, awaits sign-off)

Store the curator's source_ref explicitly at insert; `candidate_from_row` stops
reverse-parsing it from source_url (Entry-16 accepted debt: the reverse parse is
fragile per source class). Backfill from existing source_url rows at migration.

## C. Player directives (BINDING — implemented 2026-07-18)

1. **±10 s** skip everywhere (buttons + Media Session), matching Apple's default
   lock-screen icons. Supersedes DESIGN §6 iOS rule 4's "±15 s accepted".
2. **Story switch mid-play autoplays** the new story; play-state icon never
   claims playback that isn't happening.
3. **Skip asks "Not interested" vs "Already read"** — read ≠ dislike must reach
   Phase 6 preference adaptation and the §5 skip-rate quality signal untainted.
4. **Manual un-skip** (misclick recovery): explicit revoke from the library
   restores status from artifacts (audio on disk → ready; text → text_ready;
   nothing fetched → failed/retryable). Carve-out to AMENDMENT_02's "skips are
   permanent history": permanence still holds against the CURATOR (no automatic
   re-proposal — the row is never deleted); only Grace's explicit revoke undoes.
5. **Text view follows playback** — auto-highlight + scroll to the paragraph at
   the current offset (pulls Phase 5's sync-highlight forward; offsets existed).
6. **Voice applies from the player** (any rendered story, confirmation popup →
   $0 background re-render) — not only the text_ready queue window. A voice
   change during an in-flight render aborts it at the next paragraph boundary
   and a fresh render restarts with the chosen voice (confirmation popup first;
   extends AMENDMENT_04 C's abort-on-skip mechanism to voice changes).
7. **Last-played story auto-restores** into the player (paused, at its resume
   position) on app open.
8. Capitalized tab headers; **ratings editable only for the story in the
   player** (read-only stars elsewhere); **sticky header** while scrolling.
