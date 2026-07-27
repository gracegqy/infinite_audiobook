"""Candidate verification (Entry 25): before a paid batch enters the pool, check
that each `source_ref` actually resolves to a usable story.

Why this exists: the first two paid batches yielded 1 usable story out of 6
reachable candidates — the model asserted reputation correctly but proposed
collection ebook ids and stub wiki pages. The curation prompt now asks it to
verify references itself, but the model's self-report is not what the pipeline
trusts. This module re-checks mechanically, for free (HTTP only, no API spend).

The verdict is deliberately the SAME code the worker will run at acquisition
time (`ingest._fetch_clean`), so the pool cannot promise something ingest then
rejects.

Three outcomes, and the difference matters:
  ok=True            → fetched and passed every length/segmentation gate
  ok=False           → definitively unusable (stub page, collection volume, no
                       usable reference). Excluded from the pool.
  ok=None (unknown)  → transient trouble (network down, timeout). NOT excluded —
                       a flaky moment must never permanently discard a good
                       candidate.
"""
import urllib.error

from . import fetch, ingest


TRANSIENT = (TimeoutError, urllib.error.URLError, ConnectionError, OSError)


def check_candidate(candidate: dict) -> tuple[bool | None, str]:
    """(ok, note). See module docstring for the three outcomes."""
    if candidate.get("source_class") not in fetch.ENABLED_SOURCE_CLASSES:
        return False, f"source_class {candidate.get('source_class')!r} has no fetcher"
    if not fetch.usable_ref(candidate):
        return False, f"unusable source_ref {candidate.get('source_ref')!r}"
    try:
        paragraphs, text, _url = ingest._fetch_clean(candidate)
    except fetch.FetchError as e:
        # FetchError is the pipeline's own verdict — a real rejection. Its
        # transient causes (a URLError) are wrapped, so unwrap and re-classify.
        if isinstance(e.__cause__, TRANSIENT):
            return None, f"could not check now: {e.__cause__}"
        return False, str(e)[:200]
    except TRANSIENT as e:
        return None, f"could not check now: {e}"
    except Exception as e:  # unexpected shape — do not condemn on a surprise
        return None, f"could not check now: {type(e).__name__}: {e}"
    return True, f"ok: {len(paragraphs)} paragraphs, {len(text)} chars"


def annotate(candidates: list[dict], log=print) -> list[dict]:
    """Stamp each candidate with `verified` / `verify_note` in place and report
    the yield. Candidates are never dropped from the record — the full batch
    stays in curation_runs; the pool is what filters (pool.pool_candidates)."""
    ok = bad = unknown = 0
    for c in candidates:
        verdict, note = check_candidate(c)
        c["verified"], c["verify_note"] = verdict, note
        if verdict is True:
            ok += 1
        elif verdict is False:
            bad += 1
            log(f"  [verify] REJECT {c.get('title')!r}: {note}")
        else:
            unknown += 1
            log(f"  [verify] UNKNOWN {c.get('title')!r}: {note}")
    total = len(candidates)
    log(f"[verify] {ok}/{total} usable"
        + (f", {bad} rejected" if bad else "")
        + (f", {unknown} uncheckable (kept)" if unknown else ""))
    return candidates
