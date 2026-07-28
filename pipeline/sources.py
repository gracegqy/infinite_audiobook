"""Free source registry — the channel-general half of curation.

Why this exists (Grace's ruling, Entry 32): catalog mode was Gutenberg-only, and
the obvious way to add creepypasta was "a mode that also reads the creepypasta
wiki". That would have hardcoded horror into the pipeline, which AMENDMENT_01
forbids — the first non-horror channel would have silently received horror
candidates, or nothing, with no explanation.

So a source does not decide it is relevant; it DECLARES what it covers, and the
registry asks. A sci-fi channel gets Gutenberg alone. A Chinese-language channel
gets a clear "no free source covers this — use llm mode" instead of an empty
pool. Adding a source later (r/nosleep, a Chinese archive) means adding one class
here, not editing the modes.

This also pays the "source-class registry" debt standing since Entry 16.

Cost: every source in here is $0 — plain HTTP against a public catalog or API,
no key, no model. What varies is the reputation signal each one can honestly
claim, which is recorded per-candidate in `evidence` / `unverified`.
"""
import json
import urllib.parse
import urllib.request

from . import config, textproc


class FreeSource:
    """One free candidate source. Subclasses declare coverage and produce
    candidates in the same shape the paid curator returns (curate.PROMPT_TEMPLATE)
    so pool/verify/ingest/worker cannot tell the paths apart."""

    name: str = ""
    source_class: str = ""

    def covers(self, channel) -> tuple[bool, str]:
        """(serves this channel?, human reason). The reason is shown in Settings
        for BOTH answers — a source that excludes itself should say why."""
        raise NotImplementedError

    def candidates(self, conn, channel, known_titles: list[str], limit: int,
                   log=print) -> list[dict]:
        raise NotImplementedError


# ---- Gutenberg ----

class GutenbergCatalogSource(FreeSource):
    """Project Gutenberg's own catalog (the Entry-29 path, unchanged in
    substance — now behind the registry so it can be combined with others)."""

    name = "gutenberg-catalog"
    source_class = "gutenberg"

    def covers(self, channel) -> tuple[bool, str]:
        from . import catalog, curate
        keywords = catalog.genre_keywords(
            channel["genre"], curate.channel_list_field(channel, "topics_json"))
        if not keywords:
            return False, ("channel has no genre or topics to match against "
                           "Gutenberg's subjects and bookshelves")
        return True, ("public-domain texts matching subject/bookshelf terms "
                      f"({', '.join(keywords[:4])}…); catalog is majority "
                      "English, so non-English channels yield less")

    def candidates(self, conn, channel, known_titles, limit, log=print):
        from . import catalog
        catalog.fetch_catalog(log=log)
        rows = catalog.read_rows()
        out = catalog.select(rows, channel, known_titles, limit)
        log(f"[{self.name}] {len(rows):,} records → {len(out)} candidates")
        return out


# ---- Creepypasta wiki ----

# The wiki's two editorially-curated categories. These are the reputation
# signal: a human editor put the story there, which is checkable on the page
# itself. Everything else on the wiki is unfiltered user submission.
CREEPYPASTA_API = "https://creepypasta.fandom.com/api.php"
REPUTATION_CATEGORIES = {
    "PotM": "Pasta of the Month",
    "Spotlighted Pastas": "Spotlighted Pasta",
}
CREEPYPASTA_CACHE = "creepypasta_reputation.json"
CREEPYPASTA_MAX_AGE_DAYS = 30
# Terms that mean "this channel wants horror". The ONLY place this source ties
# itself to a genre — and it ties itself, rather than the pipeline tying it.
HORROR_TERMS = ("horror", "creepypasta", "scary", "ghost", "supernatural",
                "paranormal", "occult", "gothic", "weird", "macabre", "terror")
# The wiki API reports page length in bytes of WIKI MARKUP, not prose. Markup is
# always >= the prose it wraps (templates, categories, headers), so a markup
# length below MIN_STORY_CHARS proves the prose is too short — a safe reject
# that costs no fetch. The reverse does NOT hold, so the upper bound is padded
# and the real arbiter stays the length gate in verify/ingest, which reads the
# actual cleaned text.
MARKUP_MAX_MULTIPLIER = 1.5


def _api(**params):
    params.setdefault("format", "json")
    url = CREEPYPASTA_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _category_members(category: str) -> list[str]:
    """All main-namespace pages in a category, following continuations."""
    out, cont = [], {}
    while True:
        r = _api(action="query", list="categorymembers",
                 cmtitle=f"Category:{category}", cmlimit=500, cmnamespace=0,
                 **cont)
        out += [m["title"] for m in r["query"]["categorymembers"]]
        if "continue" not in r:
            return out
        cont = r["continue"]


def _page_lengths(titles: list[str]) -> dict[str, int]:
    """Markup byte length per title, 50 at a time (the API's cap).

    Keyed by the title WE ASKED FOR, not the one the API answers with: MediaWiki
    normalizes ("the rake" → "The rake", "Ted_the_Caver" → "Ted the Caver") and
    reports the mapping in `query.normalized`. Category listings happen to come
    back already normalized, so this has never bitten — but keying on the reply
    would silently drop those pages' lengths, or KeyError on the caller's index.
    """
    sizes = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        r = _api(action="query", prop="info", titles="|".join(batch))
        back = {n["to"]: n["from"]
                for n in r["query"].get("normalized", [])}
        for page in r["query"]["pages"].values():
            asked = back.get(page["title"], page["title"])
            if "length" in page:
                sizes[asked] = page["length"]
    return sizes


def creepypasta_cache_path():
    return config.INTERIM_DIR / CREEPYPASTA_CACHE


def fetch_reputation_index(force: bool = False, log=print) -> dict:
    """{title: {"length": int, "categories": [...]}} for every editorially
    recognised page. ~5 free API calls, cached like the Gutenberg catalog."""
    import datetime

    path = creepypasta_cache_path()
    stale = None
    if path.exists() and not force:
        age = datetime.datetime.now() - datetime.datetime.fromtimestamp(
            path.stat().st_mtime)
        if age.days < CREEPYPASTA_MAX_AGE_DAYS:
            return json.loads(path.read_text())
        log(f"[creepypasta-wiki] index is {age.days} days old — refreshing")
        stale = path  # keep it: a failed refresh must not lose a good index

    try:
        index: dict[str, dict] = {}
        for cat, label in REPUTATION_CATEGORIES.items():
            members = _category_members(cat)
            log(f"[creepypasta-wiki] category {cat}: {len(members)} pages")
            for t in members:
                index.setdefault(t, {"length": None, "categories": []})
                index[t]["categories"].append(label)
        for title, length in _page_lengths(sorted(index)).items():
            if title in index:  # see _page_lengths on title normalization
                index[title]["length"] = length
    except Exception as e:
        if stale is None:
            raise
        # An expired cache still beats no cache: the wiki's editorial picks
        # change monthly at most, so month-old data is a far better answer than
        # failing the whole pool build (the same reasoning verify.py applies to
        # transient errors — an outage must not condemn).
        log(f"[creepypasta-wiki] refresh failed ({e}); using the stale index")
        return json.loads(stale.read_text())

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=1))
    log(f"[creepypasta-wiki] cached {len(index)} pages at {path}")
    return index


def plausible_length(length: int | None) -> bool:
    """Markup-length prefilter. None (API gave no length) is kept — an unknown
    is not a rejection, same rule verify.py uses for transient failures."""
    if length is None:
        return True
    return (config.MIN_STORY_CHARS <= length
            <= config.MAX_STORY_CHARS * MARKUP_MAX_MULTIPLIER)


def to_candidate(title: str, entry: dict) -> dict:
    cats = entry.get("categories") or []
    return {
        "title": textproc.normalize_ws(title),
        "author": None,   # the API does not carry it; the story page credits it
        "year": None,
        "source_class": "creepypasta",
        # The page title IS the fetcher's argument, so unlike the paid path
        # there is no reference to guess and none to get wrong.
        "source_ref": title,
        "license_class": "modern_private",
        "evidence": [f"Creepypasta Wiki editorial category: {c}" for c in cats],
        "unverified": ["reputation is the wiki's own editorial selection, not "
                       "an external critic's list or award"],
    }


class CreepypastaWikiSource(FreeSource):
    """Editorially recognised pages on the creepypasta wiki.

    Horror-only BY DECLARATION — see covers(). This is the source that made the
    registry necessary: it must never be offered to a non-horror channel."""

    name = "creepypasta-wiki"
    source_class = "creepypasta"

    def covers(self, channel) -> tuple[bool, str]:
        from . import curate
        if channel["language"] != "en":
            return False, (f"English-language wiki; channel language is "
                           f"{channel['language']}")
        terms = " ".join(filter(None, [
            channel["genre"] or "",
            " ".join(curate.channel_list_field(channel, "topics_json")),
            channel["extra_criteria"] or "",
        ])).lower()
        if not any(t in terms for t in HORROR_TERMS):
            return False, ("horror-only source; channel genre/topics do not "
                           "ask for horror")
        return True, ("modern web horror from the wiki's Pasta of the Month and "
                      "Spotlighted Pastas categories")

    def candidates(self, conn, channel, known_titles, limit, log=print):
        index = fetch_reputation_index(log=log)
        known = {textproc.normalize_ws(t).lower() for t in known_titles}
        from . import curate
        avoid = [a.strip().lower() for a in
                 curate.channel_list_field(channel, "exclusions_json") if a.strip()]

        picked, short, long_, excluded = [], 0, 0, 0
        for title, entry in sorted(index.items()):
            length = entry.get("length")
            if not plausible_length(length):
                if length is not None and length < config.MIN_STORY_CHARS:
                    short += 1
                else:
                    long_ += 1
                continue
            low = title.lower()
            if low in known or any(a in low for a in avoid):
                excluded += 1
                continue
            picked.append(to_candidate(title, entry))
        log(f"[{self.name}] {len(index)} recognised pages → {len(picked)} "
            f"candidates ({short} too short, {long_} over length, "
            f"{excluded} already known/excluded)")
        # No ranking signal exists WITHIN these categories — the wiki does not
        # rank its own picks — so order is alphabetical and honestly arbitrary.
        # free_llm mode is where taste enters; free mode does not pretend to it.
        return picked[:limit]


REGISTRY: tuple[FreeSource, ...] = (
    GutenbergCatalogSource(),
    CreepypastaWikiSource(),
)


def for_channel(channel) -> tuple[list[FreeSource], list[tuple[FreeSource, str]]]:
    """(sources that cover this channel, [(source, why not) …])."""
    covering, skipped = [], []
    for src in REGISTRY:
        ok, reason = src.covers(channel)
        (covering if ok else skipped).append(src if ok else (src, reason))
    return covering, skipped


class NoFreeSource(RuntimeError):
    """No registered free source covers the channel. Raised rather than
    returning an empty pool, and never by falling back to the paid path — a
    silent switch to a paid mode is exactly what AMENDMENT_04 A forbids."""


def gather(conn, channel, known_titles: list[str], limit: int,
           log=print) -> list[dict]:
    """Candidates from every covering source, interleaved.

    Interleaving is the structural answer to the balance problem the paid prompt
    kept failing at (Entries 27-28): a batch is half classics and half modern
    because it is BUILT that way, not because a prompt asked nicely."""
    covering, skipped = for_channel(channel)
    for src, why in skipped:
        log(f"[sources] skip {src.name}: {why}")
    if not covering:
        raise NoFreeSource(
            f"no free source covers channel '{channel['name']}' "
            f"(genre={channel['genre']}, language={channel['language']}). "
            + " ".join(f"{s.name}: {w}." for s, w in skipped)
            + " Use curation_mode=llm for this channel, or add a source to "
              "pipeline/sources.py.")

    # One unreachable source must not fail the build. Gutenberg and the wiki are
    # independent networks; losing the wiki should cost the modern half, not the
    # classics too. Same principle as verify.py's ok=None: a transient failure is
    # not a verdict. Only a build where EVERY source failed is a real error.
    per_source, failures = [], []
    for src in covering:
        try:
            per_source.append(
                src.candidates(conn, channel, known_titles, limit, log=log))
        except Exception as e:
            log(f"[sources] {src.name} unavailable — {type(e).__name__}: {e}")
            failures.append((src, e))
    if failures and not any(per_source):
        raise NoFreeSource(
            "every free source covering channel "
            f"'{channel['name']}' failed: "
            + " ".join(f"{s.name}: {e}." for s, e in failures)
            + " This is usually transient — retry before switching modes.")
    out, seen = [], set()
    for i in range(max((len(p) for p in per_source), default=0)):
        for candidates in per_source:
            if i >= len(candidates):
                continue
            key = candidates[i]["title"].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(candidates[i])
            if len(out) >= limit:
                return out
    return out
