"""Pool builds over the free source registry — `free` ($0) and `free_llm` (~$0.03).

Both modes assemble candidates from every source in pipeline/sources.py that
covers the active channel. They differ only in who picks:

  free      — source order (interleaved across sources). No model call at all.
  free_llm  — one zero-search model call chooses from the assembled shortlist.

What makes this cheap is not a discount: it is that the two things the paid path
bought searches for — a correct `source_ref` and a reputation claim — are
already carried by the sources as fields. There is nothing left to verify, so
there is nothing left to pay for.

Both write the same `curation_runs` row shape as the paid path, so the R11
ledger accounts for every build and pool/verify/worker cannot tell the paths
apart (the property catalog mode established in Entry 29).
"""
import json

from . import config, curate, db, sources, verify

LEDGER_MODEL_FREE = "free-sources"  # not a model; recorded so cost is auditable


def build_pool(conn, channel=None, limit: int = config.POOL_BATCH_SIZE,
               use_llm: bool = False, verify_refs: bool = True,
               log=print) -> list[dict]:
    """One free-source pool build. Raises sources.NoFreeSource when nothing
    covers the channel — never falls back to the paid path, which would be a
    silent spend (AMENDMENT_04 A)."""
    channel = channel or db.active_channel(conn)
    known = db.known_titles(conn)

    # free_llm looks at a wider shortlist than it returns, so the pick has
    # something to choose between; free takes exactly what it needs.
    want = config.free_shortlist_size(limit) if use_llm else limit
    candidates = sources.gather(conn, channel, known, want, log=log)
    if not candidates:
        log("[freepool] no candidates — sources cover this channel but returned "
            "nothing (everything may already be in the library).")

    run_id = None
    if use_llm and candidates:
        candidates, run_id = curate.run_selection(conn, channel, candidates,
                                                  limit, log=log)
    elif use_llm:
        log("[freepool] skipping the selection call — nothing to choose from, "
            "so it would cost money to pick from an empty list.")

    if verify_refs and candidates:
        log(f"[freepool] verifying {len(candidates)} references (no API cost)…")
        candidates = verify.annotate(candidates, log=log)
        if use_llm:
            # The model ranked `limit` + spares; drop what the free verifier
            # rejected and keep the best `limit` that survive, so a Gutenberg
            # collection volume costs a spare rather than a slot in the pool.
            kept = [c for c in candidates if c.get("verified") is not False]
            dropped = len(candidates) - len(kept)
            candidates = kept[:limit]
            if dropped:
                log(f"[freepool] {dropped} rejected pick(s) replaced from spares")

    payload = json.dumps(candidates, ensure_ascii=False)
    if run_id is None:
        # free mode (or an empty free_llm build): its own $0 ledger row.
        db.record_curation_run(conn, channel["id"], LEDGER_MODEL_FREE, 0.0, 0,
                               payload)
    else:
        # free_llm already wrote a priced row in run_selection; fill in the
        # candidates it produced rather than writing a second row for one build.
        db.update_curation_candidates(conn, run_id, payload)

    usable = sum(1 for c in candidates if c.get("verified") is not False)
    by_class: dict[str, int] = {}
    for c in candidates:
        by_class[c.get("source_class") or "?"] = \
            by_class.get(c.get("source_class") or "?", 0) + 1
    mix = ", ".join(f"{n} {k}" for k, n in sorted(by_class.items())) or "none"
    log(f"[freepool] {len(candidates)} candidates ({usable} usable) — {mix}")
    return candidates
