"""Catalog curation mode (Entry 29): $0 pool builds from Gutenberg's own catalog.

The selection logic is pure over catalog rows, so it is tested directly — no
network, no 5 MB download. What matters most here is the COLLECTION filter: the
length gate alone let four-story collections through on the first real run, so
these tests pin the title-pattern rejection that fixed it.
"""
import pytest
from fastapi.testclient import TestClient

from app.server import create_app
from pipeline import catalog, db, sources


def row(text_id, title, subjects="Horror tales", shelves="Category: Short Stories",
        authors="Poe, Edgar Allan, 1809-1849", language="en", typ="Text"):
    return {"Text#": str(text_id), "Type": typ, "Issued": "2000-01-01",
            "Title": title, "Language": language, "Authors": authors,
            "Subjects": subjects, "LoCC": "PS", "Bookshelves": shelves}


@pytest.fixture()
def conn(tmp_path):
    return db.connect(tmp_path / "app.db")


# ---- collection detection (the fix that mattered) ----

@pytest.mark.parametrize("title", [
    "The Works of Edgar Allan Poe — Volume 2",
    "Complete Works of Poe",
    "First Project Gutenberg Collection of Edgar Allan Poe",
    "Present at a Hanging and Other Ghost Stories",
    "Ghost Stories of an Antiquary",
    "Knock, Knock, Knock and Other Stories",
    "Selected Tales",
    "Can Such Things Be? Tales",
])
def test_collection_titles_rejected(title):
    assert catalog.looks_like_collection(title), title


@pytest.mark.parametrize("title", [
    "The Fall of the House of Usher",
    "The Golgotha Dancers",
    "The Secret of Kralitz",
    "Tiger Cat",
    "An Occurrence at Owl Creek Bridge",
])
def test_single_story_titles_kept(title):
    assert not catalog.looks_like_collection(title), title


# ---- keyword mapping ----

def test_genre_synonyms_expand_horror():
    kw = catalog.genre_keywords("horror", [])
    # the catalog files 85 records under "Ghost stories" and 67 under "Gothic
    # fiction" that a bare "horror" match would miss
    assert "ghost" in kw and "gothic" in kw and "supernatural" in kw


def test_unknown_genre_passes_through_verbatim():
    assert catalog.genre_keywords("nautical", ["shipwreck"]) == ["nautical", "shipwreck"]


def test_no_keywords_matches_nothing():
    """An empty keyword list must return nothing, not the whole 79k catalog."""
    assert not catalog.matches(row(1, "X"), [], [])


def test_exclusions_win_over_keywords():
    r = row(1, "X", subjects="Horror tales; Body horror")
    assert catalog.matches(r, ["horror"], [])
    assert not catalog.matches(r, ["horror"], ["body horror"])


# ---- selection ----

def _channel(conn):
    return db.active_channel(conn)


def test_select_ranks_curated_shelves_first(conn):
    rows = [
        row(10, "Plain Story", shelves="Category: Fiction"),
        row(11, "Curated Story",
            shelves="Horror; Category: Short Stories; Category: Classics of Literature"),
    ]
    picked = catalog.select(rows, _channel(conn), [], limit=2)
    assert picked[0]["title"] == "Curated Story"


def test_select_skips_wrong_language_and_non_text(conn):
    rows = [
        row(21, "French Story", language="fr"),
        row(22, "An Audio Thing", typ="Sound"),
        row(23, "Good Story"),
    ]
    assert [c["title"] for c in catalog.select(rows, _channel(conn), [], limit=9)] \
        == ["Good Story"]


def test_novel_shelf_demotes_but_no_longer_excludes(conn):
    """Entry 43: excluding on `Category: Novels` threw away 11 of the 16 usable
    French sci-fi candidates — Gutenberg files novellas and single stories there
    outside English. It now ranks last, and the length gate (which reads the
    text) decides. A ranked-last record is still reachable when the top runs
    out, which is the whole difference."""
    rows = [row(20, "Shelved As A Novel", shelves="Category: Novels"),
            row(23, "Good Story")]
    assert [c["title"] for c in catalog.select(rows, _channel(conn), [], limit=9)] \
        == ["Good Story", "Shelved As A Novel"]


# ---- collection detection outside English (Entry 43) ----

@pytest.mark.parametrize("title", [
    "Contes bruns",
    "Histoires extraordinaires",
    "Nouvelles histoires extraordinaires",
    "Les fleurs animées - Tome 1",
    "La Mort de la Terre, roman, suivi de contes",
    "Vingt mille Lieues Sous Les Mers — Complete",
])
def test_french_collection_titles_rejected(title):
    assert catalog.looks_like_collection(title, "fr"), title


@pytest.mark.parametrize("title", [
    "Micromégas",
    "Les Xipéhuz",
    "Dans l'abîme",
    "La mandragore",
    "L'élixir de vie: Conte magique",      # singular Conte = one story
    "Histoire du véritable Gribouille",    # singular Histoire, likewise
])
def test_french_single_story_titles_kept(title):
    assert not catalog.looks_like_collection(title, "fr"), title


def test_markers_are_scoped_to_the_channel_language():
    """The French markers must not leak into an English channel, where
    "Nouvelles" is not a word and "Stories" already has its own rule."""
    assert not catalog.looks_like_collection("Contes bruns", "en")
    assert catalog.looks_like_collection("Contes bruns", "fr")


def test_unknown_language_still_gets_the_shared_markers():
    """An unlisted language loses its own markers, not all of them."""
    assert catalog.looks_like_collection("Antologia — Volume 2", "pt")
    assert not catalog.looks_like_collection("Uma História", "pt")


def test_select_excludes_known_titles(conn):
    rows = [row(30, "Already Read"), row(31, "Fresh One")]
    picked = catalog.select(rows, _channel(conn), ["already read"], limit=9)
    assert [c["title"] for c in picked] == ["Fresh One"]


def test_candidate_shape_matches_the_llm_path(conn):
    """pool/verify/worker must not care which mode produced a candidate."""
    (c,) = catalog.select([row(40, "The Tell-Tale Something")],
                          _channel(conn), [], limit=1)
    assert c["source_class"] == "gutenberg"
    assert c["source_ref"] == "40"          # the id is a FIELD, never guessed
    assert c["license_class"] == "pd"
    assert c["author"] == "Edgar Allan Poe"  # "Poe, Edgar Allan, 1809-1849"
    assert c["year"] is None                # Issued is a posting date, not pub year
    assert any("bookshelves" in e.lower() for e in c["evidence"])
    assert c["unverified"], "the weaker reputation basis must be stated"


def test_author_parsing_handles_missing_and_odd_names(conn):
    assert catalog.author_of({"Authors": ""}) is None
    assert catalog.author_of({"Authors": "Bierce, Ambrose, 1842-1914"}) == "Ambrose Bierce"
    assert catalog.author_of({"Authors": "Anonymous"}) == "Anonymous"


# ---- the mode setting ----

def test_mode_defaults_to_llm_so_nothing_changes_silently(conn):
    assert db.effective_curation_mode(conn) == "llm"


def test_mode_roundtrips_and_rejects_garbage(conn):
    db.set_setting(conn, "curation_mode", "free")
    assert db.effective_curation_mode(conn) == "free"
    db.set_setting(conn, "curation_mode", "nonsense")
    assert db.effective_curation_mode(conn) == "llm"  # falls back, never crashes


def test_catalog_mode_name_still_resolves(conn):
    """Entry 32 renamed `catalog` → `free` (it is no longer Gutenberg-only). A
    stored setting from before the rename must keep meaning the same thing, not
    silently fall back to the PAID default."""
    db.set_setting(conn, "curation_mode", "catalog")
    assert db.effective_curation_mode(conn) == "free"


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "app.db"
    db.connect(db_path)
    app = create_app(db_path=db_path, library_dir=tmp_path / "lib",
                     samples_dir=tmp_path / "s",
                     rerender_runner=lambda sid, voice: None)
    return TestClient(app)


def test_settings_exposes_and_accepts_mode(client):
    body = client.get("/api/settings").json()
    assert body["curation_mode"] == "llm"
    assert set(body["curation_mode_options"]) == {"free", "free_llm", "llm"}
    assert client.put("/api/settings",
                      json={"curation_mode": "free"}).json()["curation_mode"] \
        == "free"


def test_settings_describes_every_mode_and_its_free_sources(client):
    """The UI renders whatever this returns, so a mode missing a label or a
    cost would ship as a blank dropdown entry (the Entry-30 symptom)."""
    body = client.get("/api/settings").json()
    modes = {m["mode"]: m for m in body["curation_modes"]}
    assert set(modes) == set(body["curation_mode_options"])
    for m in modes.values():
        assert m["label"] and m["description"]
        assert "$" in m["label"]  # every mode states its cost up front
    # free modes carry per-source coverage for the ACTIVE channel; llm does not
    assert modes["free"]["sources"] and modes["free_llm"]["sources"]
    assert "sources" not in modes["llm"]
    names = {s["name"] for s in modes["free"]["sources"]}
    assert names == {s.name for s in sources.REGISTRY}
    for s in modes["free"]["sources"]:
        assert s["reason"], "a source must explain coverage either way"


def test_settings_rejects_unknown_mode(client):
    r = client.put("/api/settings", json={"curation_mode": "free-lunch"})
    assert r.status_code == 422 and "curation_mode" in r.json()["detail"]


# ---- pause-turn cap (Entry 29): an unbounded paid loop is a cost bug ----

def test_pause_turn_loop_is_capped_and_still_records_spend(conn, monkeypatch):
    """The loop was `while True:` with the ledger written only after it exited,
    so a model that kept pausing spent money invisibly. Cap + record both."""
    from pipeline import config, curate

    calls = {"n": 0}

    class FakeUsage:
        input_tokens = 100
        output_tokens = 50
        cache_read_input_tokens = 900
        cache_creation_input_tokens = 10
        server_tool_use = type("S", (), {"web_search_requests": 1})()

    class FakeMsg:
        stop_reason = "pause_turn"          # never stops pausing
        usage = FakeUsage()
        content = [type("B", (), {"type": "text", "text": "still working"})()]

    class FakeStream:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get_final_message(self):
            calls["n"] += 1
            return FakeMsg()

    monkeypatch.setattr(config, "CURATION_MAX_TURNS", 4)
    monkeypatch.setattr(curate.config, "anthropic_client",
                        lambda: type("C", (), {"messages": type("M", (), {
                            "stream": staticmethod(lambda **kw: FakeStream())})()})())
    monkeypatch.setattr(curate.verify, "annotate", lambda c, log=print: c)

    with pytest.raises(ValueError):        # never yields JSON
        curate.run_curation(conn, batch=2)

    assert calls["n"] == 4, "loop must stop at the cap, not run forever"
    row = conn.execute("SELECT cost_usd, searches, output_tokens, "
                       "cache_read_tokens FROM curation_runs "
                       "ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None, "an aborted run must still leave a ledger row"
    assert row["searches"] == 4 and row["output_tokens"] == 200
    assert row["cache_read_tokens"] == 3600
    assert row["cost_usd"] > 0, "spend must never look free"


def test_settings_renders_without_an_active_channel(client, tmp_path):
    """Settings is where you go to fix a broken install, so it must not 500 when
    channel state is bad — coverage degrades, the screen survives."""
    import sqlite3
    c = sqlite3.connect(tmp_path / "app.db")
    c.execute("UPDATE channels SET is_active=0")
    c.commit(); c.close()
    body = client.get("/api/settings").json()
    assert {m["mode"] for m in body["curation_modes"]} == set(db.CURATION_MODES)
    assert all(m["label"] and m["description"] for m in body["curation_modes"])
