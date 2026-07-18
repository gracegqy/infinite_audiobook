"""Candidate pool (AMENDMENT_04 A): replenishment draws already-paid-for
candidates from curation_runs before any new API spend."""
import json

from . import textproc


def _norm_title(t: str) -> str:
    return textproc.normalize_ws(t).lower()


def pool_candidates(conn) -> list[dict]:
    """Unconsumed candidates across all curation runs, newest run first,
    preserving in-run order. Consumed = a stories row already exists with the
    same normalized title (any status — ready, failed, skipped, read and
    pre-marked rows all count; every ingest outcome now leaves a row)."""
    seen_titles = {_norm_title(r["title"]) for r in
                   conn.execute("SELECT title FROM stories")}
    out = []
    for run in conn.execute(
            "SELECT candidates_json FROM curation_runs ORDER BY id DESC"):
        try:
            candidates = json.loads(run["candidates_json"])
        except (TypeError, ValueError):
            continue
        if not isinstance(candidates, list):  # {"unparsed": ...} failure rows
            continue
        for c in candidates:
            t = _norm_title(c.get("title", ""))
            if t and t not in seen_titles:
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
