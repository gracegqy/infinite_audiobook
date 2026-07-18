# AMENDMENT 01 — Customizable channels (2026-07-18)

> **Authority: HIGHEST**, applied on top of BRIEF_VERBATIM.md. Verbatim request, then the
> agreed interpretation. Never edit; further changes are new amendment docs.

## Verbatim (Grace, mid-scaffold)

spec update: would it be too much additional work to rescope the pipeline to be a
customizable scraper (I could modify genre/language/topic to scrape for at any point
through the ui) rather than a horror-specific one? assess honestly and let me know

## Assessment given, and agreed interpretation

Accepted at ~10–15% extra work because curation was already criteria-driven LLM work.
Encoded as the **channel** abstraction:

- A channel = an editable criteria record (genre, language, topics/themes, era, exclusions)
  stored in SQLite and editable in the UI. The queue-replenishment worker reads the active
  channel's criteria; nothing outside the default channel config hardcodes "horror".
- Default channel at launch = the horror brief (classics + modern web horror, high
  reputation bar). The reputation bar (many recommendations, video essays, ratings) is a
  channel-independent standing requirement.
- Known costs accepted: fetchers are source-specific (new genres may need a new fetcher
  incrementally); non-English Kokoro quality is a pre-design probe, with OpenAI TTS as the
  fallback for weak languages.
