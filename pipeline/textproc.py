"""Pure text logic: cleaning, paragraph segmentation, dedup keys, offsets math.
No I/O, no network — everything here is unit-tested (tests/test_textproc.py,
tests/test_offsets.py)."""
import hashlib
import re


def normalize_ws(s: str) -> str:
    """Collapse all whitespace runs to single spaces. Applied per paragraph before
    TTS — hard line-wraps inside a paragraph cause Kokoro chunk-break pauses
    (probe 1b, binding clean rule DESIGN §5)."""
    return re.sub(r"\s+", " ", s).strip()


def split_paragraphs(text: str, min_chars: int = 0) -> list[str]:
    """Blank-line paragraph segmentation, each paragraph unwrapped to one line.
    Paragraphs under min_chars are dropped (wiki chrome / stray headings)."""
    paras = [normalize_ws(p) for p in re.split(r"\n\s*\n", text)]
    return [p for p in paras if p and len(p) >= min_chars]


def dedup_key(title: str, text: str) -> str:
    """sha1 of normalized title + first 500 normalized chars (probe 4)."""
    basis = normalize_ws(title).lower() + "|" + normalize_ws(text).lower()[:500]
    return hashlib.sha1(basis.encode()).hexdigest()


def title_slug(title: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "story"


def story_id(key: str, title: str) -> str:
    """<12 hex of dedup key>-<slug> (DESIGN §2)."""
    return f"{key[:12]}-{title_slug(title)}"


def story_length_problem(text: str, min_chars: int, max_chars: int) -> str | None:
    """None if the cleaned text is a plausible single short story, else the
    rejection reason. Too short = empty/deleted page (probe 4); too long =
    collection volume or novel that would render for hours."""
    if len(text) < min_chars:
        return f"cleaned text too short ({len(text)} chars) — empty/deleted page?"
    if len(text) > max_chars:
        return (f"cleaned text too long ({len(text)} chars > {max_chars}) — "
                "collection volume or novel, not a single short story")
    return None


def strip_gutenberg(raw: str) -> tuple[str, bool]:
    """Cut Project Gutenberg header/footer between *** START/END *** markers
    (probe 4: 10/10). Returns (body, markers_found)."""
    m = re.search(r"\*\*\* ?START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", raw)
    n = re.search(r"\*\*\* ?END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", raw)
    if m and n and m.end() < n.start():
        return raw[m.end():n.start()].strip(), True
    return raw.strip(), False


def build_offsets(paragraphs: list[str], durations_s: list[float]) -> list[dict]:
    """Offsets manifest entries from per-paragraph durations (DESIGN §4).

    char offsets index into the canonical story text (paragraphs joined by
    blank lines); time offsets are cumulative durations — exact by construction
    for butt-join concatenation (probe 2).
    """
    if len(paragraphs) != len(durations_s):
        raise ValueError(f"{len(paragraphs)} paragraphs vs {len(durations_s)} durations")
    out, char_pos, t = [], 0, 0.0
    for i, (p, d) in enumerate(zip(paragraphs, durations_s)):
        if d < 0:
            raise ValueError(f"negative duration at paragraph {i}")
        out.append({"i": i, "char_start": char_pos, "char_end": char_pos + len(p),
                    "t_start_s": round(t, 4), "t_end_s": round(t + d, 4)})
        char_pos += len(p) + 2  # the "\n\n" joiner
        t += d
    return out
