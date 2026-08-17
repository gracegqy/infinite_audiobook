"""Catalog curation (Entry 29): build a candidate pool from Project Gutenberg's
own catalog instead of an LLM, at $0 and with no API key.

Why this exists: the LLM's single biggest failure mode was the `source_ref` — it
proposed collection-volume ebook ids, or "unknown", and each bad ref wasted a
candidate. The catalog carries the ebook id as a FIELD. There is nothing to
guess, so that failure mode disappears rather than being mitigated.

What it trades away, stated plainly: reputation evidence. The LLM verifies a
named list, essay, or award ("NPR's 100 Best Horror"). Here the evidence is
Gutenberg's own metadata — the editor-curated bookshelves it appears on and its
Library of Congress subject headings. Both are checkable on the ebook's page,
which satisfies the standing "no vague widely-considered" bar, but it is a
weaker claim than an external critic. That is the choice `curation_mode` exposes.

Collections and novels are excluded twice over: once here (the `Novels` category
is dropped, `Short Stories` preferred) and once for free by the existing
length gate in verify/ingest, which is the same gate the LLM path relies on.
"""
import csv
import datetime
import gzip
import io
import urllib.request

from . import config, textproc

CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz"
CATALOG_CACHE = "pg_catalog.csv.gz"
CATALOG_MAX_AGE_DAYS = 30

# Channel genre/topic words → the subject + bookshelf vocabulary Gutenberg
# actually uses. Without this, a channel genre of "horror" would miss the 85
# records filed only under "Ghost stories" and the 67 under "Gothic fiction".
GENRE_SYNONYMS = {
    "horror": ["horror", "ghost", "gothic", "supernatural", "occult",
               "paranormal", "weird"],
    "science fiction": ["science fiction", "sf", "fantasy"],
    "mystery": ["mystery", "detective", "crime", "thriller"],
    "fantasy": ["fantasy", "mythology", "legends", "folklore"],
}
# Bookshelves that are a reputation signal in their own right (Gutenberg
# editors curate these by hand, unlike the auto-derived LoC subjects).
CURATED_SHELVES = ("horror", "classics of literature", "short stories",
                   "best books ever listings", "harvard classics")
# A record on the Novels shelf is a novel — drop it before spending a fetch.
NOVEL_SHELF = "category: novels"
SHORT_STORY_SHELF = "category: short stories"
# How far a Novels-shelf record drops in the ranking (see is_shelved_as_novel).
# Big enough to put it behind everything with a curated shelf, small enough that
# it is still reached when the top of the list runs out — which is the whole
# point of demoting rather than excluding.
NOVEL_SHELF_PENALTY = 4


# ---- pure logic ----

def genre_keywords(genre: str | None, topics: list[str]) -> list[str]:
    """Channel criteria → catalog match terms. The single copy of this mapping."""
    terms: list[str] = []
    for raw in ([genre] if genre else []) + list(topics or []):
        word = (raw or "").strip().lower()
        if not word:
            continue
        terms.extend(GENRE_SYNONYMS.get(word, [word]))
    return list(dict.fromkeys(terms))  # dedupe, keep order


def record_haystack(row) -> str:
    return f"{row.get('Subjects', '')} ; {row.get('Bookshelves', '')}".lower()


def matches(row, keywords: list[str], avoid: list[str]) -> bool:
    """Subject/bookshelf match, minus the channel's exclusions. A record with no
    keywords at all never matches — an empty keyword list means "no criteria",
    which should return nothing rather than the entire 79k-record catalog."""
    if not keywords:
        return False
    hay = record_haystack(row)
    if any(a.strip().lower() in hay for a in avoid if a.strip()):
        return False
    return any(k in hay for k in keywords)


def is_shelved_as_novel(row) -> bool:
    """On the `Category: Novels` shelf, without a short-story shelf to offset it.

    This USED to exclude the record (`is_probably_short`, Entry 29). Entry 43
    measured what that cost outside English: Gutenberg applies the Novels shelf
    loosely, and on French rows it carries novellas and single short stories
    too — 11 of the 16 usable French sci-fi candidates sit on it, among them
    Rosny's *Les Xipéhuz* and Wells's *Dans l'abîme*. Excluding on it threw away
    two thirds of the channel's supply to save a few fetches.

    So it now DEMOTES instead of excluding (see `reputation_score`): the record
    stays reachable, and the length gate — which reads the actual text and is
    the only thing that can really tell — remains the arbiter, exactly as this
    module's docstring always claimed.
    """
    shelves = (row.get("Bookshelves") or "").lower()
    return NOVEL_SHELF in shelves and SHORT_STORY_SHELF not in shelves


# Title markers for multi-story volumes. The length gate alone is NOT enough
# here (Entry 29): it rejects a 500k-char Poe omnibus, but a four-story Bierce
# collection is ~60k chars and sails through, so catalog mode's first run
# returned mostly collections. Titles announce them reliably, and unlike the
# length gate this costs no fetch.
#
# Keyed BY LANGUAGE since Entry 43. The list was English-only, so the first
# non-English channel got no collection filtering at all: 25 of the 30 French
# sci-fi candidates were collections or novels, and "Contes bruns", "Histoires
# extraordinaires" and "Les fleurs animées - Tome 1" all read as single stories.
# A source cannot be channel-general (AMENDMENT_01) while its filters speak one
# language. An unlisted language falls back to the shared markers alone.
COLLECTION_MARKERS = {
    "en": ("works of", "complete works", "complete tales", "and other",
           "selected ", "short stories", "ghost stories", "collected "),
    # plural forms only: "contes"/"histoires" announce a volume, while the
    # singular "Conte"/"Histoire" is how French titles a single story
    # ("L'élixir de vie: Conte magique", "Histoire du véritable Gribouille").
    "fr": ("contes", "histoires", "nouvelles", "récits", "recits", "tome ",
           "suivi de", "et autres", "oeuvres", "œuvres", "choisies", "choisis",
           "recueil"),
    "zh": ("全集", "文集", "小说集", "故事集", "选集"),
}
# Markers that carry across every language this project serves.
COLLECTION_MARKERS_ANY = ("collection", "anthology", "anthologie", "omnibus",
                          "volume", "complete", "complet")
# A bare plural ending says the same thing as an explicit marker.
COLLECTION_ENDINGS = {
    "en": ("tales", "stories"),
    "fr": ("contes", "histoires", "nouvelles", "récits"),
}


def looks_like_collection(title: str, language: str = "en") -> bool:
    """True when the TITLE itself says multi-story volume. Deliberately errs
    toward rejecting: a missed single story costs nothing (the catalog has 514
    candidates), while an accepted collection wastes a fetch and, worse, could
    render hours of the wrong audio."""
    low = f" {(title or '').lower()} "
    markers = COLLECTION_MARKERS_ANY + COLLECTION_MARKERS.get(language, ())
    if any(m in low for m in markers):
        return True
    endings = COLLECTION_ENDINGS.get(language, ())
    return bool(endings) and low.rstrip().rstrip(".").endswith(endings)


def reputation_score(row) -> int:
    """Rank by how much curation the record carries. Not a popularity metric —
    the catalog has no download counts — so it is honestly a weaker signal than
    the LLM path's named lists."""
    hay = record_haystack(row)
    score = sum(3 for shelf in CURATED_SHELVES if shelf in hay)
    score += min(3, len([s for s in (row.get("Subjects") or "").split(";") if s.strip()]))
    if SHORT_STORY_SHELF in hay:
        score += 2
    if is_shelved_as_novel(row):
        score -= NOVEL_SHELF_PENALTY
    return score


def evidence_for(row) -> list[str]:
    """Checkable provenance strings — each verifiable on the ebook's own page."""
    out = []
    shelves = [s.strip() for s in (row.get("Bookshelves") or "").split(";") if s.strip()]
    subjects = [s.strip() for s in (row.get("Subjects") or "").split(";") if s.strip()]
    if shelves:
        out.append("Project Gutenberg bookshelves: " + ", ".join(shelves[:3]))
    if subjects:
        out.append("Library of Congress subjects: " + ", ".join(subjects[:3]))
    out.append(f"Project Gutenberg catalog record #{row.get('Text#')}")
    return out


def author_of(row) -> str | None:
    """"Bierce, Ambrose, 1842-1914" → "Ambrose Bierce"."""
    raw = (row.get("Authors") or "").split(";")[0].strip()
    if not raw:
        return None
    name = raw.split("[")[0].strip()
    parts = [p.strip() for p in name.split(",")]
    if len(parts) >= 2 and parts[1] and not parts[1][0].isdigit():
        return f"{parts[1]} {parts[0]}".strip()
    return parts[0]


def year_of(row) -> int | None:
    """Issued date is the Gutenberg posting date, not the publication year, so
    it is deliberately NOT used as `year` — reporting it would be wrong. The
    author's death date is the closest honest proxy the catalog offers, and it
    is still not a publication year, so this returns None."""
    return None


def to_candidate(row, language: str) -> dict:
    return {
        "title": textproc.normalize_ws(row.get("Title") or "").replace("\n", " "),
        "author": author_of(row),
        "year": year_of(row),
        "source_class": "gutenberg",
        "source_ref": str(row.get("Text#") or "").strip(),
        "license_class": "pd",
        "language": language,
        "evidence": evidence_for(row),
        "unverified": ["reputation is Gutenberg catalog metadata (bookshelves + "
                       "LoC subjects), not an external critic's list"],
    }


def select(rows, channel, known_titles, limit: int) -> list[dict]:
    """The whole decision, as a pure function over catalog rows."""
    from . import curate  # deferred: curate imports config only
    language = channel["language"]
    keywords = genre_keywords(channel["genre"],
                              curate.channel_list_field(channel, "topics_json"))
    avoid = curate.channel_list_field(channel, "exclusions_json")
    known = {textproc.normalize_ws(t).lower() for t in known_titles}

    picked = []
    for row in rows:
        if row.get("Type") != "Text" or row.get("Language") != language:
            continue
        if not matches(row, keywords, avoid):
            continue
        cand = to_candidate(row, language)
        if not cand["source_ref"] or not cand["title"]:
            continue
        if looks_like_collection(cand["title"], language):
            continue
        if cand["title"].lower() in known:
            continue
        picked.append((reputation_score(row), cand))

    picked.sort(key=lambda p: -p[0])
    seen, out = set(), []
    for _score, cand in picked:
        key = cand["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
        if len(out) >= limit:
            break
    return out


# ---- I/O ----

def catalog_path():
    return config.INTERIM_DIR / CATALOG_CACHE


def fetch_catalog(force: bool = False, log=print):
    """Download the catalog once and cache it. ~5 MB gzipped, no API key, free.
    Refreshed after CATALOG_MAX_AGE_DAYS so new Gutenberg postings show up."""
    path = catalog_path()
    if path.exists() and not force:
        age = datetime.datetime.now() - datetime.datetime.fromtimestamp(
            path.stat().st_mtime)
        if age.days < CATALOG_MAX_AGE_DAYS:
            return path
        log(f"[catalog] cache is {age.days} days old — refreshing")
    path.parent.mkdir(parents=True, exist_ok=True)
    log(f"[catalog] downloading {CATALOG_URL}")
    req = urllib.request.Request(CATALOG_URL,
                                 headers={"User-Agent": config.USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        path.write_bytes(r.read())
    log(f"[catalog] cached {path.stat().st_size / 1e6:.1f} MB at {path}")
    return path


def read_rows(path=None):
    path = path or catalog_path()
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


# The pool build that used to live here moved to pipeline/freepool.py in Entry
# 32, when Gutenberg stopped being the only free source. What remains is the
# catalog-specific logic, which `sources.GutenbergCatalogSource` drives — one
# build path for every free source rather than one per source.
