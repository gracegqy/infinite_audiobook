"""Central constants — the single copy of every model ID, engine choice, and knob
(DESIGN §5, CLAUDE.md centralization rule)."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "app.db"
LIBRARY_DIR = DATA_DIR / "library"
INTERIM_DIR = DATA_DIR / "interim"
ENV_PATH = ROOT / ".env"

QUEUE_DEPTH = 3  # AMENDMENT_02

# Curation (DESIGN §5): Sonnet, capped searches, ≤$0.40/batch target. Never
# auto-escalate the model (R14) — changes are Grace-initiated only.
CURATION_MODEL = "claude-sonnet-5"
CURATION_MAX_SEARCHES = 6
CURATION_BATCH_SIZE = 8
# AMENDMENT_04 A: paid curation only refills the pool (explicit --build-pool);
# replenishment consumes stored candidates at $0 marginal.
POOL_BATCH_SIZE = 40
# $/M tokens (in, out) + $/search, for the curation_runs cost ledger (R11).
MODEL_PRICING = {
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}
WEB_SEARCH_COST = 0.01

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
