"""Spend cap and the settings-backed knobs (Entry 37).

The behaviours under test are the ones where the obvious implementation is
wrong: a rolling window computed in local time silently under-counts recent
spend (the ledger's timestamps are UTC); a cap that only guards the expensive
path leaks through the cheap one; and a knob read from `config` at a call site
ignores the setting Grace just changed.
"""
import datetime

import pytest

from pipeline import budget, config, db


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    yield c
    c.close()


UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def spend(conn, dollars, *, ago_days=0, now=NOW):
    """A ledger row `ago_days` in the past, written the way SQLite writes them
    (UTC, no timezone suffix) so the tests exercise the real parsing path."""
    ts = (now - datetime.timedelta(days=ago_days)).strftime("%Y-%m-%d %H:%M:%S")
    ch = db.active_channel(conn)["id"]
    conn.execute(
        "INSERT INTO curation_runs(channel_id, model, cost_usd, searches, "
        "candidates_json, created_at) VALUES(?,?,?,?,?,?)",
        (ch, "test-model", dollars, 0, "[]", ts))
    conn.commit()


# ---- defaults and stored values ----

def test_knobs_fall_back_to_config_when_unset(conn):
    assert db.effective_worker_interval_s(conn) == config.DEFAULT_WORKER_INTERVAL_S
    assert db.effective_spend_cap(conn) == (config.DEFAULT_SPEND_CAP_USD,
                                            config.DEFAULT_SPEND_CAP_PERIOD)


def test_stored_values_beat_the_defaults(conn):
    db.set_setting(conn, "worker_interval_s", "1800")
    db.set_setting(conn, "spend_cap_usd", "7.50")
    db.set_setting(conn, "spend_cap_period", "week")
    assert db.effective_worker_interval_s(conn) == 1800
    assert db.effective_spend_cap(conn) == (7.50, "week")


def test_interval_is_clamped_to_the_floor(conn):
    """A hand-typed 10 must not turn the loop hot."""
    db.set_setting(conn, "worker_interval_s", "10")
    assert db.effective_worker_interval_s(conn) == config.WORKER_INTERVAL_MIN_S


@pytest.mark.parametrize("junk", ["", "abc", "-5"])
def test_unparseable_knobs_degrade_to_defaults_not_crashes(conn, junk):
    """A bad row must never take down a pool build mid-run."""
    db.set_setting(conn, "worker_interval_s", junk)
    db.set_setting(conn, "spend_cap_period", junk)
    assert db.effective_worker_interval_s(conn) >= config.WORKER_INTERVAL_MIN_S
    assert db.effective_spend_cap(conn)[1] in config.SPEND_CAP_PERIOD_DAYS


# ---- the rolling window ----

def test_window_counts_recent_spend_and_drops_old(conn):
    spend(conn, 1.00, ago_days=1)
    spend(conn, 2.00, ago_days=45)     # outside a 30-day month
    assert budget.spent_in_window(conn, "month", NOW) == pytest.approx(1.00)


def test_window_is_evaluated_in_utc(conn):
    """The ledger writes UTC. A window built from local time would mis-count
    rows near the boundary — on a UTC-7 machine, by seven hours of spend."""
    spend(conn, 3.00, ago_days=0)      # 12:00 UTC today
    # A window of one day back from NOW must include a row written just now,
    # regardless of the machine's offset.
    assert budget.spent_in_window(conn, "day", NOW) == pytest.approx(3.00)


def test_period_lengths_are_distinct(conn):
    spend(conn, 5.00, ago_days=3)
    assert budget.spent_in_window(conn, "day", NOW) == 0.0
    assert budget.spent_in_window(conn, "week", NOW) == pytest.approx(5.00)


# ---- enforcement ----

def test_check_passes_under_the_cap(conn):
    db.set_setting(conn, "spend_cap_usd", "2.00")
    spend(conn, 0.50, ago_days=1)
    budget.check(conn, 0.05, NOW)      # no raise


def test_check_refuses_a_build_that_would_breach(conn):
    db.set_setting(conn, "spend_cap_usd", "2.00")
    spend(conn, 1.98, ago_days=1)
    with pytest.raises(budget.CapExceeded) as e:
        budget.check(conn, 0.05, NOW)
    # the message must carry the numbers — a bare "cap reached" leaves Grace
    # unable to decide whether to raise it
    assert "1.98" in str(e.value) and "2.00" in str(e.value)


def test_zero_cap_means_unlimited(conn):
    db.set_setting(conn, "spend_cap_usd", "0")
    spend(conn, 999.0, ago_days=1)
    budget.check(conn, 50.0, NOW)      # no raise
    assert budget.status(conn, NOW)["unlimited"] is True


def test_old_spend_stops_blocking_once_the_window_rolls(conn):
    db.set_setting(conn, "spend_cap_usd", "2.00")
    spend(conn, 2.00, ago_days=45)
    budget.check(conn, 0.05, NOW)      # no raise: the row aged out


# ---- the readout the Settings screen shows ----

def test_status_agrees_with_enforcement(conn):
    """The screen and the guard must never disagree about what was spent."""
    db.set_setting(conn, "spend_cap_usd", "2.00")
    spend(conn, 1.50, ago_days=1)
    st = budget.status(conn, NOW)
    assert st["spent_in_period"] == pytest.approx(1.50)
    assert st["remaining"] == pytest.approx(0.50)
    assert st["exhausted"] is False
    with pytest.raises(budget.CapExceeded):
        budget.check(conn, 0.60, NOW)  # 1.50 + 0.60 > 2.00, as the readout implies


def test_status_flags_exhaustion(conn):
    db.set_setting(conn, "spend_cap_usd", "1.00")
    spend(conn, 1.00, ago_days=1)
    assert budget.status(conn, NOW)["exhausted"] is True
