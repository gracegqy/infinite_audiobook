# BRIEF — VERBATIM (immutable)

> **Authority: HIGHEST**, together with numbered amendment docs in this folder applied in
> order. Never edit this file. REQUIREMENTS.md is the working checklist derived from this
> and is *wrong* on any conflict.
> Captured 2026-07-18 from Grace's scaffold request.

as a horror fan, I want an automated process that scrapes the web for highly
reputed/classic/popular horror novellas and short stories, stores them as pure text, and
reads them to me aloud with high-quality AI voices. a few notes: 1) standards should be
high - only pick stories recommended by many people, on which there exist video essays,
that have high ratings, that are well reputed, etc. 2) always keep a queue of 5 unread
stories; if the number of unread stories drop to less than that, scrape and process to
keep the stored content at 5. 3) Ideally this should have a user-friendly interface, maybe
taking the final form of a web app? (subject to your discretion - whatever makes most
sense for the end goals) the point is, it should be 1. easily accessible on both mobile
and laptop, 2. have stored content (retains memory of the last place paused, keeps a
record of the stories that have been read/are in progress so that no repeated scraping
happens, 3. have a spotify-like interface with basic functions like pause/resume,
back/forward 15s, drag timeline to jump or go back in audio, have the text script i could
access at any point while listening (preferably with tracking that syncs with the audio),
select story, bookmark story, etc. anything at all that's practical and helpful to
implement. 4) this is a bonus, so tell me if it's feasible/reasonably economical. it'd be
nice for the pipeline to adapt to my preference - I'd select how much I liked a story on a
scale of 5, and the pipeline would keep a record of the trends, reducing or increasing
stories of certain genres, origins, themes, elements, authors, etc. according to my
preference. 5) keep the pipeline economical and efficient. no exorbitant costs, and no
feature/storage/algorithm sprawl that would make the pipeline take too much time to
respond to ui interactions. keep things smooth and highly functional

## Interview answers (2026-07-18, same session)

1. **Sourcing scope:** Both public-domain classics and modern web horror, private-use
   only (no public deploy of content; modern works kept defensible as personal use).
2. **TTS & budget:** Local-first (Kokoro, free) with paid-API fallback per story only if
   the local render disappoints.
3. **Hosting:** Grace's Mac + Tailscale; app and audio never leave her machines. $0/mo.
4. **Existing keys:** Anthropic API key, OpenAI API key.
