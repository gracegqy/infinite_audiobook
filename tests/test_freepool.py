"""free / free_llm pool builds (Entry 32).

The properties worth pinning are the ones that keep this mode honest:
  - the model picks INDICES, so it cannot introduce a story or a reference
  - an out-of-range index is dropped, not trusted
  - a failed pick still writes a ledger row (the Entry-29 lesson: spend must
    never be invisible) and degrades visibly rather than silently
  - one build writes ONE ledger row, whichever path it took

No network and no API key: the model call and the sources are both faked.
"""
import json
import types

import pytest

from pipeline import config, curate, db, freepool, sources


@pytest.fixture()
def conn(tmp_path):
    return db.connect(tmp_path / "app.db")


def fake_response(text, in_tok=4000, out_tok=500):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="text", text=text)],
        usage=types.SimpleNamespace(
            input_tokens=in_tok, output_tokens=out_tok,
            cache_read_input_tokens=0, cache_creation_input_tokens=0))


def patch_model(monkeypatch, text, capture=None):
    def create(**kwargs):
        if capture is not None:
            capture.update(kwargs)
        return fake_response(text)
    monkeypatch.setattr(config, "anthropic_client", lambda: types.SimpleNamespace(
        messages=types.SimpleNamespace(create=create)))


def cands(n):
    return [{"title": f"Story {i}", "source_class": "creepypasta",
             "source_ref": f"Story {i}", "license_class": "modern_private",
             "evidence": ["Creepypasta Wiki editorial category: PotM"],
             "unverified": []} for i in range(n)]


# ---- the selection prompt and parser ----

def test_selection_prompt_carries_every_channel_field(conn):
    """R12 / the Phase 5 gate: a channel edit that did not reach the prompt
    would make the channel editor a lie. free_llm has its own prompt, so the
    guarantee has to be re-proved here."""
    ch = dict(db.active_channel(conn))
    ch.update(genre="weird fiction", topics_json=json.dumps(["hauntings"]),
              era="19th-century", exclusions_json=json.dumps(["gore"]),
              extra_criteria="quiet dread only")
    p = curate.build_selection_prompt(ch, cands(3), 2)
    for token in ("weird fiction", "hauntings", "19th-century", "gore",
                  "quiet dread only"):
        assert token in p


def test_selection_prompt_lists_candidates_with_indices(conn):
    p = curate.build_selection_prompt(dict(db.active_channel(conn)), cands(3), 2)
    assert "[0] Story 0" in p and "[2] Story 2" in p


def test_balance_clause_appears_only_with_a_real_mix(conn):
    ch = dict(db.active_channel(conn))
    mixed = cands(2) + [{"title": "Classic", "source_class": "gutenberg",
                         "source_ref": "42", "license_class": "pd",
                         "evidence": [], "unverified": []}]
    assert "BALANCE" in curate.build_selection_prompt(ch, mixed, 2)
    assert "BALANCE" not in curate.build_selection_prompt(ch, cands(2), 2)


def test_parse_selection_drops_indices_that_were_never_offered():
    """The one way this mode could still point at something nonexistent."""
    picks = curate.parse_selection(
        '[{"i": 1, "why": "good"}, {"i": 99, "why": "invented"}, '
        '{"i": -1, "why": "negative"}, {"i": 1, "why": "duplicate"}]', 3, 5)
    assert picks == [(1, "good")]


def test_parse_selection_raises_on_prose():
    with pytest.raises(ValueError, match="prose"):
        curate.parse_selection("I could not choose.", 3, 2)


# ---- run_selection ----

def test_selection_returns_pipeline_candidates_not_model_text(conn, monkeypatch):
    """Every field except the rationale comes from the source adapter, so a
    model that hallucinates a title cannot get it into the pool."""
    patch_model(monkeypatch, '[{"i": 2, "why": "the strongest premise"}]')
    chosen, run_id = curate.run_selection(conn, db.active_channel(conn),
                                          cands(5), 1, log=lambda *a: None)
    assert [c["title"] for c in chosen] == ["Story 2"]
    assert chosen[0]["source_ref"] == "Story 2"
    assert chosen[0]["selection_note"] == "the strongest premise"


def test_selection_sends_no_web_search_tool(conn, monkeypatch):
    """Search is ~half the paid path's bill and the entire reason this mode is
    cheap. A tool sneaking back in would be a silent cost regression."""
    seen = {}
    patch_model(monkeypatch, '[{"i": 0, "why": "x"}]', capture=seen)
    curate.run_selection(conn, db.active_channel(conn), cands(3), 1,
                         log=lambda *a: None)
    assert "tools" not in seen
    assert seen["output_config"] == {"effort": config.SELECTION_EFFORT}


def test_failed_selection_still_records_spend_and_says_so(conn, monkeypatch):
    """Entry 29's lesson, re-applied: an unparseable response is not a free
    response. It must leave a priced ledger row AND mark the candidates as
    un-judged rather than passing source order off as a pick."""
    patch_model(monkeypatch, "I would rather not choose.")
    chosen, run_id = curate.run_selection(conn, db.active_channel(conn),
                                          cands(4), 2, log=lambda *a: None)
    row = conn.execute("SELECT * FROM curation_runs WHERE id=?", (run_id,)).fetchone()
    assert row["cost_usd"] > 0
    # The fallback supplies spares too, exactly like a successful pick — the
    # verifier still needs replacements, and build_pool trims either way.
    assert len(chosen) == min(4, 2 + config.SELECTION_SPARES)
    assert all(any("selection failed" in u for u in c["unverified"])
               for c in chosen)


def test_selection_cost_excludes_search_fees(conn, monkeypatch):
    patch_model(monkeypatch, '[{"i": 0, "why": "x"}]')
    _, run_id = curate.run_selection(conn, db.active_channel(conn), cands(3), 1,
                                     log=lambda *a: None)
    row = conn.execute("SELECT * FROM curation_runs WHERE id=?", (run_id,)).fetchone()
    price_in, price_out = config.model_pricing(row["model"])
    assert row["searches"] == 0
    assert row["cost_usd"] == pytest.approx(
        4000 / 1e6 * price_in + 500 / 1e6 * price_out, abs=1e-4)


# ---- build_pool ----

def patch_sources(monkeypatch, produced):
    monkeypatch.setattr(sources, "gather",
                        lambda conn, ch, known, limit, log=print: produced[:limit])


def test_free_mode_makes_no_model_call_and_logs_zero_cost(conn, monkeypatch):
    patch_sources(monkeypatch, cands(10))
    monkeypatch.setattr(config, "anthropic_client", lambda: pytest.fail(
        "free mode must never call the model"))
    monkeypatch.setattr("pipeline.verify.annotate", lambda c, log=print: c)
    out = freepool.build_pool(conn, limit=4, use_llm=False, log=lambda *a: None)
    assert len(out) == 4
    row = conn.execute("SELECT * FROM curation_runs ORDER BY id DESC").fetchone()
    assert row["cost_usd"] == 0 and row["model"] == freepool.LEDGER_MODEL_FREE


def test_free_llm_shortlist_is_wider_than_the_batch(conn, monkeypatch):
    """The pick needs something to choose between; a shortlist equal to the
    batch would make the model a formality that still costs money."""
    asked = {}
    monkeypatch.setattr(sources, "gather",
                        lambda conn, ch, known, limit, log=print: (
                            asked.update(limit=limit) or cands(limit)))
    patch_model(monkeypatch, json.dumps([{"i": i, "why": "x"} for i in range(4)]))
    monkeypatch.setattr("pipeline.verify.annotate", lambda c, log=print: c)
    freepool.build_pool(conn, limit=4, use_llm=True, log=lambda *a: None)
    assert asked["limit"] == config.free_shortlist_size(4) > 4


def test_one_build_writes_exactly_one_ledger_row(conn, monkeypatch):
    """free_llm prices its row in run_selection and then fills in the
    candidates. A second row would double-count the spend in R11."""
    patch_sources(monkeypatch, cands(30))
    patch_model(monkeypatch, json.dumps([{"i": i, "why": "x"} for i in range(3)]))
    monkeypatch.setattr("pipeline.verify.annotate", lambda c, log=print: c)
    freepool.build_pool(conn, limit=3, use_llm=True, log=lambda *a: None)
    rows = conn.execute("SELECT * FROM curation_runs").fetchall()
    assert len(rows) == 1
    stored = json.loads(rows[0]["candidates_json"])
    assert isinstance(stored, list) and len(stored) == 3
    assert rows[0]["cost_usd"] > 0


def test_empty_source_result_does_not_buy_a_selection_call(conn, monkeypatch):
    patch_sources(monkeypatch, [])
    monkeypatch.setattr(config, "anthropic_client", lambda: pytest.fail(
        "must not pay to pick from an empty list"))
    out = freepool.build_pool(conn, limit=4, use_llm=True, log=lambda *a: None)
    assert out == []
    row = conn.execute("SELECT * FROM curation_runs ORDER BY id DESC").fetchone()
    assert row["cost_usd"] == 0


def test_uncovered_channel_raises_instead_of_falling_back_to_paid(conn, monkeypatch):
    monkeypatch.setattr(sources, "gather", lambda *a, **k: (_ for _ in ()).throw(
        sources.NoFreeSource("nothing covers this channel")))
    monkeypatch.setattr(config, "anthropic_client", lambda: pytest.fail(
        "an uncovered channel must never silently start a PAID run"))
    with pytest.raises(sources.NoFreeSource):
        freepool.build_pool(conn, limit=4, use_llm=True, log=lambda *a: None)


# ---- balance is enforced in code, not requested in the prompt (Entry 32) ----

def q(cls, n=1):
    return [{"title": f"{cls}-{i}", "source_class": cls} for i in range(n)]


def test_quotas_rebalance_a_lopsided_ranking():
    """The first real free_llm run returned 9 gutenberg / 3 creepypasta off a
    36/36 shortlist. The model ranks; the code holds the ratio."""
    ranked = q("gutenberg", 9) + q("creepypasta", 3)
    out = curate.apply_class_quotas(ranked, 6)
    assert [c["source_class"] for c in out[:6]] == \
        ["gutenberg", "creepypasta"] * 3


def test_quotas_preserve_rank_within_a_class():
    out = curate.apply_class_quotas(q("gutenberg", 4) + q("creepypasta", 4), 4)
    assert [c["title"] for c in out[:4]] == \
        ["gutenberg-0", "creepypasta-0", "gutenberg-1", "creepypasta-1"]


def test_quotas_never_discard_anything():
    ranked = q("gutenberg", 9) + q("creepypasta", 3)
    out = curate.apply_class_quotas(ranked, 6)
    assert sorted(c["title"] for c in out) == sorted(c["title"] for c in ranked)


def test_a_class_with_too_few_picks_yields_its_places():
    """Balance must not mean starving the batch — one creepypasta and nine
    classics should still fill six slots."""
    out = curate.apply_class_quotas(q("gutenberg", 9) + q("creepypasta", 1), 6)
    assert len(out[:6]) == 6
    assert sum(1 for c in out[:6] if c["source_class"] == "creepypasta") == 1


def test_quotas_are_a_noop_for_a_single_class_channel():
    ranked = q("gutenberg", 5)
    assert curate.apply_class_quotas(ranked, 3) == ranked


def test_rejected_picks_are_replaced_from_spares(conn, monkeypatch):
    """A Gutenberg collection volume must cost a spare, not a pool slot."""
    shortlist = cands(30)
    patch_sources(monkeypatch, shortlist)
    patch_model(monkeypatch, json.dumps(
        [{"i": i, "why": "x"} for i in range(9)]))

    def annotate(candidates, log=print):
        for n, c in enumerate(candidates):
            c["verified"] = n not in (0, 1)   # first two are collections
        return candidates
    monkeypatch.setattr("pipeline.verify.annotate", annotate)

    out = freepool.build_pool(conn, limit=3, use_llm=True, log=lambda *a: None)
    assert len(out) == 3
    assert all(c["verified"] is not False for c in out)


def test_selection_asks_for_spares_beyond_the_batch(conn, monkeypatch):
    seen = {}
    patch_model(monkeypatch, '[{"i": 0, "why": "x"}]', capture=seen)
    curate.run_selection(conn, db.active_channel(conn), cands(30), 4,
                         log=lambda *a: None)
    prompt = seen["messages"][0]["content"]
    assert f"array of {4 + config.SELECTION_SPARES} objects" in prompt


# ---- spend guard (Entry 33) ----

def test_estimate_scales_with_batch_and_names_the_fees():
    small, how_small = curate.estimate_cost("claude-sonnet-5", 8)
    big, _ = curate.estimate_cost("claude-sonnet-5", 40)
    assert big > small
    assert "searches" in how_small and "fees" in how_small
    # search fees are exact, so they must be a floor on the estimate
    assert big >= config.curation_search_budget(40) * config.WEB_SEARCH_COST


def test_small_paid_build_needs_no_approval():
    assert curate.confirm_spend("claude-sonnet-5", 4, approved=False,
                                log=lambda *a: None)


def test_big_paid_build_is_blocked_without_yes_spend():
    """The coded POOL_BATCH_SIZE lands here: --build-pool opts into spending,
    not into $2."""
    assert curate.estimate_cost("claude-sonnet-5", config.POOL_BATCH_SIZE)[0] \
        > config.CURATION_SPEND_CONFIRM_USD
    assert not curate.confirm_spend("claude-sonnet-5", config.POOL_BATCH_SIZE,
                                    approved=False, log=lambda *a: None)
    assert curate.confirm_spend("claude-sonnet-5", config.POOL_BATCH_SIZE,
                                approved=True, log=lambda *a: None)


def test_the_estimate_is_printed_even_when_it_passes():
    lines = []
    curate.confirm_spend("claude-sonnet-5", 4, approved=False, log=lines.append)
    assert any("estimated cost" in ln for ln in lines)


def test_run_story_refuses_a_big_paid_build_without_the_flag(conn, monkeypatch):
    """End-to-end: the guard must stop the CALL, not just return False."""
    from pipeline import run_story
    monkeypatch.setattr(db, "connect", lambda *a, **k: conn)
    db.set_setting(conn, "curation_mode", "llm")
    monkeypatch.setattr(curate, "run_curation", lambda *a, **k: pytest.fail(
        "a paid batch must not start without --yes-spend"))
    assert run_story.main(["--build-pool"]) == 3
