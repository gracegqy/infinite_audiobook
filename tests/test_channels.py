"""Channel criteria editor (R12 / AMENDMENT_01) + the gate that makes it real:
an edited channel must demonstrably change the next curation batch's prompt.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.server import create_app
from pipeline import curate, db, worker


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "app.db"
    c = db.connect(db_path)
    app = create_app(db_path=db_path, library_dir=tmp_path / "library",
                     samples_dir=tmp_path / "samples",
                     rerender_runner=lambda sid, voice: None)
    return TestClient(app), c


# ---- criteria reach the prompt (the Phase 5 gate's mechanism) ----

def test_every_editable_field_reaches_the_prompt():
    channel = {"id": 1, "name": "x", "genre": "ghost stories", "language": "en",
               "era": "pre-1930", "extra_criteria": "no gore",
               "topics_json": json.dumps(["hauntings", "the sea"]),
               "exclusions_json": json.dumps(["body horror"])}
    p = curate.build_prompt(channel, [], batch=3)
    for expected in ("ghost stories", "pre-1930", "no gore", "hauntings",
                     "the sea", "body horror"):
        assert expected in p, expected


def test_editing_a_channel_changes_the_next_prompt():
    """TASKS Phase 5 gate: a channel edit demonstrably changes curation."""
    base = {"id": 1, "name": "x", "genre": "horror", "language": "en",
            "era": None, "extra_criteria": None, "topics_json": None,
            "exclusions_json": None}
    edited = {**base, "genre": "golden-age science fiction",
              "topics_json": json.dumps(["first contact"])}
    before, after = curate.build_prompt(base, []), curate.build_prompt(edited, [])
    assert before != after
    assert "first contact" in after and "first contact" not in before
    assert "golden-age science fiction" in after


def test_list_fields_tolerate_nulls_and_hand_typed_csv():
    assert curate.channel_list_field({"topics_json": None}, "topics_json") == []
    assert curate.channel_list_field({"topics_json": "[]"}, "topics_json") == []
    assert curate.channel_list_field({"topics_json": '["a","b"]'},
                                     "topics_json") == ["a", "b"]
    # not JSON — a human typed a comma list straight into the column
    assert curate.channel_list_field({"topics_json": "a, b"},
                                     "topics_json") == ["a", "b"]


# ---- API ----

def test_default_channel_is_listed_and_active(client):
    tc, _ = client
    body = tc.get("/api/channels").json()
    (ch,) = body["channels"]
    assert ch["name"] == "horror" and ch["is_active"] is True
    assert ch["unread"] == 0 and body["queue_depth"] == 3


def test_create_edit_roundtrip(client):
    tc, _ = client
    made = tc.post("/api/channels", json={
        "name": "scifi", "genre": "science fiction", "language": "en",
        "era": "1950s", "topics": ["first contact", "robots"],
        "exclusions": ["military"], "extra_criteria": "award winners"}).json()
    assert made["topics"] == ["first contact", "robots"]
    assert made["is_active"] is False  # creating never steals the queue

    got = tc.put(f"/api/channels/{made['id']}",
                 json={"topics": ["time travel"], "era": "1960s"}).json()
    assert got["topics"] == ["time travel"] and got["era"] == "1960s"
    assert got["genre"] == "science fiction"  # untouched fields survive


def test_duplicate_name_rejected(client):
    tc, _ = client
    assert tc.post("/api/channels", json={"name": "horror"}).status_code == 409


def test_language_without_tts_config_rejected(client):
    tc, _ = client
    r = tc.post("/api/channels", json={"name": "jp", "language": "ja"})
    assert r.status_code == 422 and "no TTS config" in r.json()["detail"]


def test_empty_name_rejected(client):
    tc, _ = client
    assert tc.post("/api/channels", json={"name": "   "}).status_code == 422


def test_activate_switches_exactly_one_channel(client):
    tc, c = client
    made = tc.post("/api/channels", json={"name": "scifi"}).json()
    assert tc.post(f"/api/channels/{made['id']}/activate").json()["is_active"]
    actives = [ch["name"] for ch in tc.get("/api/channels").json()["channels"]
               if ch["is_active"]]
    assert actives == ["scifi"]
    assert db.active_channel(c)["name"] == "scifi"


def test_activate_unknown_channel_404s(client):
    tc, _ = client
    assert tc.post("/api/channels/99/activate").status_code == 404


def test_switching_channels_leaves_other_stories_in_the_library(client):
    """DESIGN §7: other channels' unread stories stay, they just stop
    counting toward the queue."""
    tc, c = client
    c.execute(
        "INSERT INTO stories(id, channel_id, dedup_key, title, source_class, "
        "source_url, license_class, language, status) VALUES('s1',1,'k1','T',"
        "'gutenberg','https://example.org/x','pd','en','ready')")
    c.commit()
    made = tc.post("/api/channels", json={"name": "scifi"}).json()
    tc.post(f"/api/channels/{made['id']}/activate")

    assert len(tc.get("/api/stories").json()["stories"]) == 1  # still there
    assert worker.unread_count(c, made["id"]) == 0             # but not counted
    assert worker.needs_replenishment(0, 3)
