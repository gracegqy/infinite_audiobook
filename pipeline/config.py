"""Central constants — the single copy of every model ID, engine choice, and knob
(DESIGN §5, CLAUDE.md centralization rule)."""
import datetime
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
# HR_DATA_DIR redirects ALL state (db + library + interim) at once, so a
# throwaway server or probe can run against a COPY of the library instead of
# Grace's real one. Added after headless-browser UI checks pointed at the live
# server autoplayed audio and overwrote two real resume positions (Entry 26) —
# scripts/ui_sandbox.sh is the supported way to drive the UI.
DATA_DIR = pathlib.Path(os.environ.get("HR_DATA_DIR") or (ROOT / "data"))
DB_PATH = DATA_DIR / "app.db"
LIBRARY_DIR = DATA_DIR / "library"
INTERIM_DIR = DATA_DIR / "interim"
ENV_PATH = ROOT / ".env"  # keys stay in the repo root, never copied into a sandbox

QUEUE_DEPTH = 3  # AMENDMENT_02
# Replenishment worker (Phase 5): how often --loop re-checks the queue. Long,
# because the only thing that shortens the queue is Grace finishing a story.
WORKER_INTERVAL_S = 900

# Curation (DESIGN §5): Sonnet, capped searches, ≤$0.40/batch target. Never
# auto-escalate the model (R14) — changes are Grace-initiated only.
CURATION_MODEL = "claude-sonnet-5"
# Search budget SCALES with the ask (Entry 29). Prompt caching inverted the
# economics — cached search results re-read at 0.1x, so a search now costs about
# its $0.01 fee — but a FLAT cap starves a large batch: verifying one candidate
# takes ~3 searches (find the standalone edition, open its page, check the
# reputation claim), so 25 fits a batch of 8 and would strand a batch of 40 the
# same way 6 stranded run 4. The ceiling is a spend guard, not a target.
CURATION_SEARCHES_PER_CANDIDATE = 3
CURATION_MIN_SEARCHES = 10
CURATION_MAX_SEARCHES = 150  # hard ceiling: ~$1.50 of search fees


def curation_search_budget(batch: int) -> int:
    """web_search max_uses for a batch of `batch` candidates — the single copy
    of this scaling, so the pool build and a one-off run agree."""
    return max(CURATION_MIN_SEARCHES,
               min(CURATION_MAX_SEARCHES, batch * CURATION_SEARCHES_PER_CANDIDATE))


CURATION_BATCH_SIZE = 8
# Hard cap on pause_turn continuations (Entry 29). The loop used to be
# `while True:` with the cost ledger written only AFTER it exited — so a run
# that kept pausing spent money indefinitely AND invisibly. One run sat open 70
# minutes with no ledger row before being killed. Never remove this cap.
CURATION_MAX_TURNS = 12
# Thinking depth for curation (Entry 28). Curation is search-and-list, not deep
# reasoning, and adaptive thinking is ON BY DEFAULT on Sonnet 5 at `high` effort
# — so leaving this unset was silently buying reasoning tokens this task doesn't
# need. `medium` not `low`: effort also drives how willingly the model searches,
# and the prompt now asks it to work at finding standalone Gutenberg editions.
CURATION_EFFORT = "medium"
# AMENDMENT_04 A: paid curation only refills the pool (explicit --build-pool);
# replenishment consumes stored candidates at $0 marginal.
POOL_BATCH_SIZE = 40

# free_llm mode (Entry 32): the model picks POOL_BATCH_SIZE candidates from a
# shortlist this many times larger, assembled free by pipeline/sources.py. The
# shortlist is the whole cost — it is plain text, ~20 tokens a line — so a wide
# one is nearly free and gives the pick something to actually choose between.
# Capped so a source that grows to thousands of entries cannot quietly inflate
# the prompt.
FREE_SHORTLIST_MULTIPLIER = 6
FREE_SHORTLIST_MAX = 400
# Selection is pick-from-a-supplied-list against explicit criteria, not research:
# there is nothing unknown to reason toward, and adaptive thinking defaults ON at
# `high` on Sonnet 5. Raise to "medium" if the picks ever read as arbitrary.
SELECTION_EFFORT = "low"
SELECTION_MAX_TOKENS = 4000
# Ask the selection call for this many picks BEYOND the batch. The free verifier
# still rejects some picks — the first real run lost 2 of 12 to Gutenberg
# collection volumes — and a spare costs ~20 output tokens where a re-run costs
# another whole call. Spares also refill the balance quota when a reject empties
# one side.
SELECTION_SPARES = 6


def free_shortlist_size(batch: int) -> int:
    """How many free candidates to put in front of the model for a batch of
    `batch` — the single copy, so the pool build and any estimate agree."""
    return min(FREE_SHORTLIST_MAX, max(batch, batch * FREE_SHORTLIST_MULTIPLIER))

# $/M tokens (in, out) + $/search, for the curation_runs cost ledger (R11).
# Cache multipliers are Anthropic's published ratios: a cache READ costs 0.1x
# base input, a 5-minute cache WRITE costs 1.25x. Those are what make the
# pause-turn loop cheap (Entry 28) — without caching every accumulated web
# search result is re-read at full price on every turn.
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25
MODEL_PRICING = {
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}
WEB_SEARCH_COST = 0.01

# Sonnet 5 introductory pricing runs through 2026-08-31: $2/$10 per M instead of
# $3/$15. The ledger used list price, so it OVERSTATED every run by ~a third
# (Entry 28) — a cost ledger that overstates still misleads a spend decision.
INTRO_PRICING = {"claude-sonnet-5": ((2.0, 10.0), datetime.date(2026, 8, 31))}


def model_pricing(model: str, on: datetime.date | None = None) -> tuple[float, float]:
    """($/M input, $/M output) for `model` on a given date — the single copy of
    this lookup, so the ledger and any estimate agree."""
    intro = INTRO_PRICING.get(model)
    if intro and (on or datetime.date.today()) <= intro[1]:
        return intro[0]
    return MODEL_PRICING[model]


TAG_MODEL = "claude-haiku-4-5-20251001"

# TTS engine per language (DESIGN §5; Grace's probe-1/1c verdicts, Entries 13–14).
SAMPLE_RATE = 24000
TTS_BY_LANGUAGE = {
    "en": ("kokoro", "af_heart"),
    "fr": ("kokoro", "ff_siwis"),
    "zh": ("edge_tts", "zh-CN-YunxiNeural"),
}
KOKORO_LANG_CODES = {"en": "a", "fr": "f"}
# Per-story fallback for every language (probe 6) — also the edge-tts degrade rule.
FALLBACK_TTS = ("openai", "onyx")
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"

# Voice audition gallery (AMENDMENT_04 D): selectable voices per language,
# each pre-rendered ONCE into VOICE_SAMPLES_DIR by scripts/render_voice_samples.py.
# Defaults (first entry) match TTS_BY_LANGUAGE.
VOICE_OPTIONS = {
    "en": ["af_heart", "af_bella", "af_nicole", "af_sarah", "am_adam",
           "am_michael", "bf_emma", "bm_george"],
    "fr": ["ff_siwis"],
    "zh": ["zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural"],
}
VOICE_SAMPLES_DIR = DATA_DIR / "voice_samples"

# App server (DESIGN §1): binds the Mac's Tailscale interface ONLY — never
# 0.0.0.0. scripts/serve.sh resolves the live IP via `tailscale ip -4` and
# falls back to this last-known value.
APP_PORT = 8123
TAILSCALE_IP_FALLBACK = "100.117.147.107"

# clean-stage sanity bounds. Floor: deleted/empty wiki pages must be rejected
# (probe 4). Ceiling: a Gutenberg ref can turn out to be a collection volume or
# novel — reject fast instead of rendering hours of audio (gate-run lesson,
# 2026-07-18: "Tell-Tale Heart" ref fetched a 550KB Poe collection).
MIN_STORY_CHARS = 1500
MAX_STORY_CHARS = 120_000  # ~20k words — generous novella ceiling
# The paragraph floor strips leftover wiki chrome from HTML-derived sources
# ONLY. Gutenberg plain text gets no floor: real prose has paragraphs under
# 40 chars (gate-run lesson: Yellow Wallpaper loses 29 of them, e.g.
# "And what can one do?").
MIN_PARAGRAPH_CHARS = 40
HTML_SOURCE_CLASSES = ("creepypasta", "nosleep", "scp_cn")

USER_AGENT = ("horror-readaloud/0.1 (personal library; "
              "contact graceguqianying@uchicago.edu)")

CONTROLLED_VOCAB = {
    "era": ["pre-1800", "19th-century", "early-20th", "mid-20th", "late-20th",
            "contemporary"],
    "subgenre": ["gothic", "cosmic", "psychological", "supernatural", "ghost",
                 "monster", "body-horror", "folk", "found-footage", "slasher",
                 "thriller", "weird"],
    "origin": ["western", "chinese", "japanese", "french", "other"],
    "language": ["en", "zh", "fr"],
}


def anthropic_client():
    """The single copy of key-load + client construction (curate + tag)."""
    import anthropic
    key = load_env().get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(f"ANTHROPIC_API_KEY not in {ENV_PATH}")
    return anthropic.Anthropic(api_key=key)


def load_env(path=ENV_PATH):
    """Parse .env (stdlib only — keys never travel further than the API clients)."""
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env
