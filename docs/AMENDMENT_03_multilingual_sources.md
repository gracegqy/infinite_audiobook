# AMENDMENT 03 — Multilingual scope: zh/fr channels + non-Western sources (2026-07-18)

> **Authority: HIGHEST**, applied on top of BRIEF_VERBATIM.md + AMENDMENTS 01–02.
> Status: **BINDING** as of Grace's DESIGN sign-off (v0.3 → frozen v1.0, 2026-07-18,
> JOURNAL Entry 15). Never edited from here; changes are new amendment docs.

## Verbatim (Grace, 2026-07-18)

on the sources, have you also considered nonwestern sources, like
a岛、小红书、知乎等论坛的怪谈板块；中文恐怖作家（像周德东、oobmab等）的高口碑作品；
日本或其他非英语作家的译作，在微信读书等阅读软件上能找到？for reference, I speak
english and chinese natively, and I'm learning french, so all three languages could be
in-scope, if the added workload is plausible. sonnet approved. if quality consistently
disappoints per feedback, give me a popup notice to change model selection here; don't
auto-escalate.

## Assessment given, and agreed interpretation

Languages in scope: **en, zh, fr** — each gated on a passed Kokoro quality probe in that
language before any channel uses it (en passed, probe 1; zh/fr = probe 1c, rendered
2026-07-18, awaiting Grace's listen; OpenAI TTS is the per-story fallback and supports
all three).

Source feasibility tiers (fetchers added incrementally per AMENDMENT_01):

- **Tier A — in scope:** Gutenberg zh/fr collections (聊斋志异 etc.; Maupassant, e.g.
  Le Horla — same fetcher, near-zero extra work); **SCP-CN wiki** — oobmab's works and
  the whole CN branch are **CC BY-SA licensed**, legally fetchable with attribution
  (new wikidot fetcher); **local import** — a new `local_import` source class where
  Grace drops legitimately-obtained .txt/.epub files (this is the lawful route to
  周德东-class commercial authors and translated Japanese fiction).
- **Tier B — probe before promising:** X岛/A岛-successor anonymous boards (JSON
  endpoints have existed; stability unproven); 知乎 columns (login walls + anti-bot;
  treat like Reddit — verify a fetch path before design relies on it).
- **Tier C — declined:** scraping 小红书 (app-walled, aggressively anti-scraping) and
  **微信读书 or any DRM'd reading platform — extracting their content is DRM
  circumvention, not web scraping, and stays out regardless of private-use posture.**
  Local import covers the same works legitimately.

Curation generalizes: the reputation bar maps to Chinese-web signals (豆瓣 ratings,
知乎 threads, bilibili 解说 video essays) — curator prompt becomes language-aware, no
mechanism change. Workload verdict given to Grace: plausible and incremental — fr is
nearly free, zh adds two fetchers + the TTS gate; neither disturbs the architecture.

Also encoded from the verbatim (curation model policy): **Sonnet is the standing
curation model; never auto-escalate.** If curation quality consistently disappoints
per feedback signals (skip-rate), the UI shows a notice prompting Grace to change the
model in settings — the model choice is always hers.
