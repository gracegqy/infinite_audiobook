"""Candidate verification before the pool (Entry 25).

The distinction under test: a DEFINITE rejection (stub page, collection volume,
no usable ref) excludes a candidate; a TRANSIENT failure (network down) must
not — a flaky moment should never discard a good story permanently.
"""
import json
import urllib.error

import pytest

from pipeline import db, fetch, ingest, pool, verify


@pytest.fixture()
def conn(tmp_path):
    return db.connect(tmp_path / "app.db")


def cand(**kw):
    base = {"title": "T", "source_class": "gutenberg", "source_ref": "42",
            "license_class": "pd", "language": "en", "evidence": []}
    return {**base, **kw}


def test_good_candidate_verifies(monkeypatch):
    monkeypatch.setattr(ingest, "_fetch_clean",
                        lambda c: (["a", "b"], "a\n\nb", "https://example.org/x"))
    ok, note = verify.check_candidate(cand())
    assert ok is True and "2 paragraphs" in note


def test_collection_volume_is_a_definite_reject(monkeypatch):
    monkeypatch.setattr(ingest, "_fetch_clean", lambda c: (_ for _ in ()).throw(
        fetch.FetchError("cleaned text too long (398549 chars > 120000)")))
    ok, note = verify.check_candidate(cand(source_ref="8492"))
    assert ok is False and "too long" in note


def test_stub_wiki_page_is_a_definite_reject(monkeypatch):
    monkeypatch.setattr(ingest, "_fetch_clean", lambda c: (_ for _ in ()).throw(
        fetch.FetchError("cleaned text too short (0 chars) — empty/deleted page?")))
    ok, _ = verify.check_candidate(
        cand(source_class="creepypasta", source_ref="Ted the Caver"))
    assert ok is False


def test_unusable_reference_is_rejected_without_fetching(monkeypatch):
    monkeypatch.setattr(ingest, "_fetch_clean", lambda c: pytest.fail("fetched!"))
    ok, note = verify.check_candidate(cand(source_ref="unknown"))
    assert ok is False and "unusable source_ref" in note


def test_source_class_without_a_fetcher_is_rejected(monkeypatch):
    monkeypatch.setattr(ingest, "_fetch_clean", lambda c: pytest.fail("fetched!"))
    ok, note = verify.check_candidate(cand(source_class="reddit", source_ref="x"))
    assert ok is False and "no fetcher" in note


def test_network_failure_is_unknown_not_a_rejection(monkeypatch):
    monkeypatch.setattr(ingest, "_fetch_clean", lambda c: (_ for _ in ()).throw(
        urllib.error.URLError("connection refused")))
    ok, note = verify.check_candidate(cand())
    assert ok is None and "could not check now" in note


def test_wrapped_network_failure_is_also_unknown(monkeypatch):
    """FetchError wraps URLError — the cause decides, not the wrapper type."""
    def boom(c):
        try:
            raise urllib.error.URLError("timed out")
        except urllib.error.URLError as e:
            raise fetch.FetchError("fetch failed") from e
    monkeypatch.setattr(ingest, "_fetch_clean", boom)
    ok, _ = verify.check_candidate(cand())
    assert ok is None


def test_annotate_stamps_and_counts(monkeypatch):
    verdicts = iter([(True, "ok"), (False, "stub"), (None, "offline")])
    monkeypatch.setattr(verify, "check_candidate", lambda c: next(verdicts))
    logs = []
    out = verify.annotate([cand(title="a"), cand(title="b"), cand(title="c")],
                          log=logs.append)
    assert [c["verified"] for c in out] == [True, False, None]
    assert any("1/3 usable" in m for m in logs)


# ---- fill: verify until the pool is full (Entry 43) ----

def _verdicts(monkeypatch, by_title):
    monkeypatch.setattr(verify, "check_candidate",
                        lambda c: by_title[c["title"]])


def test_fill_stops_as_soon_as_the_batch_is_full(monkeypatch):
    """The horror channel's candidates nearly all verify, so this must not turn
    a cheap build into 40 pointless fetches."""
    checked = []
    monkeypatch.setattr(verify, "check_candidate",
                        lambda c: (checked.append(c["title"]), (True, "ok"))[1])
    out = verify.fill([cand(title=f"S{i}") for i in range(10)], 3,
                      log=lambda *a: None)
    assert checked == ["S0", "S1", "S2"]
    assert [c["title"] for c in out] == ["S0", "S1", "S2"]


def test_fill_walks_past_rejections_to_fill_the_batch(monkeypatch):
    """The French sci-fi case: 16 usable among 104, ranked below the novels."""
    _verdicts(monkeypatch, {"a": (False, "too long"), "b": (False, "too long"),
                            "c": (True, "ok"), "d": (True, "ok")})
    out = verify.fill([cand(title=t) for t in "abcd"], 2, log=lambda *a: None)
    assert [c["title"] for c in out] == ["a", "b", "c", "d"]
    assert [c["verified"] for c in out] == [False, False, True, True]


def test_fill_drops_the_tail_it_never_examined(monkeypatch):
    """An unchecked candidate must not reach the pool wearing no verdict —
    that is the pre-Entry-25 behaviour the verifier exists to end."""
    _verdicts(monkeypatch, {"a": (True, "ok"), "b": (True, "ok"),
                            "c": (True, "ok")})
    out = verify.fill([cand(title=t) for t in "abc"], 1, log=lambda *a: None)
    assert [c["title"] for c in out] == ["a"]
    assert all("verified" in c for c in out)


def test_fill_counts_an_uncheckable_candidate_toward_the_batch(monkeypatch):
    """Same rule as everywhere else: a flaky moment is not a verdict, so an
    unknown is kept — and kept means it fills a slot."""
    _verdicts(monkeypatch, {"a": (None, "could not check now"),
                            "b": (True, "ok")})
    out = verify.fill([cand(title="a"), cand(title="b")], 1,
                      log=lambda *a: None)
    assert [c["title"] for c in out] == ["a"]
    assert out[0]["verified"] is None


def test_fill_says_so_when_the_source_runs_out(monkeypatch):
    _verdicts(monkeypatch, {"a": (True, "ok"), "b": (False, "too long")})
    logs = []
    verify.fill([cand(title="a"), cand(title="b")], 5, log=logs.append)
    assert any("1/5 usable" in m and "exhausted" in m for m in logs)


def test_fill_reports_progress_after_every_candidate(monkeypatch):
    """The bar on the phone is driven from here — one event per candidate, with
    the running usable count, so a walk that rejects 20 in a row still visibly
    moves (Entry 43)."""
    _verdicts(monkeypatch, {"a": (False, "too long"), "b": (True, "ok"),
                            "c": (True, "ok")})
    seen = []
    verify.fill([cand(title=t) for t in "abc"], 2, log=lambda *a: None,
                on_progress=lambda checked, usable: seen.append((checked, usable)))
    assert seen == [(1, 0), (2, 1), (3, 2)]


def test_fill_stops_when_told_to_and_keeps_what_it_verified(monkeypatch):
    """Cancel is checked BEFORE each fetch, so pressing stop does not buy one
    more HTTP round trip. What was already verified is returned — those
    verdicts are no less true for the build being stopped."""
    checked = []
    monkeypatch.setattr(verify, "check_candidate",
                        lambda c: (checked.append(c["title"]), (True, "ok"))[1])
    out = verify.fill([cand(title=f"S{i}") for i in range(5)], 5,
                      log=lambda *a: None,
                      should_abort=lambda: len(checked) >= 2)
    assert checked == ["S0", "S1"]
    assert [c["title"] for c in out] == ["S0", "S1"]


# ---- the pool honors the verdicts ----

def _run(conn, candidates):
    conn.execute("INSERT INTO curation_runs(channel_id, model, candidates_json) "
                 "VALUES(1,'m',?)", (json.dumps(candidates),))
    conn.commit()


def test_pool_skips_rejected_but_keeps_uncheckable(conn):
    _run(conn, [
        cand(title="Good", source_ref="1", verified=True),
        cand(title="Stub", source_ref="2", verified=False),
        cand(title="Offline", source_ref="3", verified=None),
        cand(title="Legacy", source_ref="4"),  # pre-Entry-25 rows have no field
    ])
    titles = [c["title"] for c in pool.pool_candidates(conn)]
    assert titles == ["Good", "Offline", "Legacy"]
