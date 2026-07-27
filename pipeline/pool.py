"""Candidate pool (AMENDMENT_04 A): replenishment draws already-paid-for
candidates from curation_runs before any new API spend."""
import json

from . import db, textproc


def _norm_title(t: str) -> str:
    return textproc.normalize_ws(t).lower()


def ref_key(source_class: str | None, source_ref: str | None) -> tuple[str, str]:
    """The identity of a SOURCE (not a story). Single copy of this normalization."""
    return (str(source_class or "").strip().lower(),
            _norm_title(str(source_ref or "")))


def failed_refs(conn) -> set[tuple[str, str]]:
    """(source_class, source_ref) pairs that failed to yield a story: deleted
    wiki pages, collection ebook ids, missing ids. Skipped forever — retrying
    the same bad ref would fail identically (Entry-16 lesson: the 550 KB Poe
    collection must never be re-proposed). The TITLE stays available, so a
    later batch offering a correct ref for the same story is accepted."""
    return {ref_key(r["source_class"], r["source_ref"]) for r in conn.execute(
        "SELECT source_class, source_ref FROM stories WHERE status='failed'")}


def pool_candidates(conn, channel_id: int | None = None) -> list[dict]:
    """Unconsumed candidates across curation runs, newest run first, preserving
    in-run order.

    Two independent exclusions, because they answer different questions:
      - TITLE already known (we have the story, or Grace read/skipped it)
      - REF already failed (that source cannot produce a story)

    channel_id restricts to that channel's runs — switching channels re-targets
    replenishment (DESIGN §7). Omitted = every run, which is what the manual
    drivers want."""
    seen_titles = {_norm_title(t) for t in db.known_titles(conn)}
    dead_refs = failed_refs(conn)
    where = "WHERE channel_id=?" if channel_id is not None else ""
    args = (channel_id,) if channel_id is not None else ()
    out = []
    for run in conn.execute(
            f"SELECT candidates_json FROM curation_runs {where} ORDER BY id DESC",
            args):
        try:
            candidates = json.loads(run["candidates_json"])
        except (TypeError, ValueError):
            continue
        if not isinstance(candidates, list):  # {"unparsed": ...} failure rows
            continue
        for c in candidates:
            t = _norm_title(c.get("title", ""))
            if not t or t in seen_titles:
                continue
            if ref_key(c.get("source_class"), c.get("source_ref")) in dead_refs:
                continue  # that source already proved it cannot yield the story
            seen_titles.add(t)  # dedup across runs too
            out.append(c)
    return out


def find_candidate(conn, title_fragment: str) -> dict | None:
    """Pool candidate whose title contains the fragment (case-insensitive)."""
    frag = _norm_title(title_fragment)
    for c in pool_candidates(conn):
        if frag in _norm_title(c["title"]):
            return c
    return None
