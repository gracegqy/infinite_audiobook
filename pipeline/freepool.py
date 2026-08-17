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

    # Both modes now assemble the same wide shortlist. free_llm needs it so the
    # pick has something to choose between; free needs it because verification
    # walks down the list until the batch is full (Entry 43), and a list exactly
    # `limit` long leaves nowhere to walk — a channel where half the candidates
    # are collections would return half a pool and no way to do better. The
    # modes still differ in the one thing that matters: who picks.
    want = config.free_shortlist_size(limit)
    candidates = sources.gather(conn, channel, known, want, log=log)
    if not candidates:
        log("[freepool] no candidates — sources cover this channel but returned "
            "nothing (everything may already be in the library).")

    # Verify BEFORE the pick, and fill to a target (Entry 43). Both halves
    # changed. Before: the model chose from unverified metadata and the free
    # verifier ran over its picks afterwards, so a collection volume cost a
    # spare — and once the spares were gone, a pool slot. But nothing in the
    # shortlist says how LONG a text is, so the model cannot avoid that trap
    # any better than the ranking can: the answer only exists in the fetched
    # text. Verifying first means the model chooses among texts already known
    # to be usable, and its judgement goes on what it can actually judge.
    rejected: list[dict] = []
    if verify_refs and candidates:
        need = limit + config.SELECTION_SPARES if use_llm else limit
        log(f"[freepool] verifying references until {need} pass "
            f"({len(candidates)} available, no API cost)…")
        examined = verify.fill(candidates, need, log=log)
        candidates = [c for c in examined if c.get("verified") is not False]
        # kept in the ledger record, never offered onward: the rejections are
        # the evidence for why a thin build was thin (Entry 25's rule).
        rejected = [c for c in examined if c.get("verified") is False]

    run_id = None
    if use_llm and len(candidates) > limit:
        candidates, run_id = curate.run_selection(conn, channel, candidates,
                                                  limit, log=log)
        # every pick is already verified, so spares are pure surplus now
        candidates = candidates[:limit]
    elif use_llm and candidates:
        # Nothing to choose: the batch would take every verified candidate
        # whatever the model said. Paying to rank a list that cannot be cut is
        # the same class of waste as the empty-list call below — and a thin
        # channel is exactly where it would happen, so exactly where a silent
        # charge would be least expected.
        log(f"[freepool] {len(candidates)} verified candidates for a batch of "
            f"{limit} — taking them all, no selection call to pay for.")
    elif use_llm:
        log("[freepool] skipping the selection call — nothing to choose from, "
            "so it would cost money to pick from an empty list.")

    payload = json.dumps(candidates + rejected, ensure_ascii=False)
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
