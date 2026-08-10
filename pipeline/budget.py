"""Spend cap (Entry 37, Grace's proposal (ii)).

An honest LOCAL cap: it sums what THIS APP has recorded spending in the
`curation_runs` ledger over a rolling window and refuses a build that would
carry the window past the cap. Two things it deliberately is not:

  - It is NOT the Anthropic account balance. Nothing here can see that, so
    "replenish credits" is unanswerable from inside the app and a
    credit-exhausted API error stays a separate condition (Entry 35).
  - It is NOT an auto-refill gate. AMENDMENT_04 A is still binding: paid pool
    builds are Grace-initiated only. The cap constrains HOW MUCH a build she
    started may spend; it never authorises one she did not.

The cap and its period live in `settings`, never in code — see
db.effective_spend_cap. `now` is a parameter everywhere (CLAUDE.md: time-
dependent behavior takes the clock as an argument).
"""
import datetime

from . import config, db


class CapExceeded(Exception):
    """A paid call would carry the rolling window past the cap. Carries the
    numbers so the caller can explain itself without recomputing them."""

    def __init__(self, spent: float, estimate: float, cap: float, period: str):
        self.spent, self.estimate = spent, estimate
        self.cap, self.period = cap, period
        room = max(0.0, cap - spent)
        super().__init__(
            f"spend cap reached: ${spent:.4f} already spent in the last "
            f"{period}, cap is ${cap:.2f} (${room:.4f} left) and this build "
            f"estimates ${estimate:.4f}. Raise or clear the cap in Settings, "
            f"or wait for the window to roll.")


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def window_start(period: str, now: datetime.datetime | None = None
                 ) -> datetime.datetime:
    """Start of the rolling window. Rolling, not calendar-aligned, so "have I
    room to build a pool?" never depends on the day of the month."""
    now = now or _utcnow()
    days = config.SPEND_CAP_PERIOD_DAYS.get(
        period, config.SPEND_CAP_PERIOD_DAYS[config.DEFAULT_SPEND_CAP_PERIOD])
    return now - datetime.timedelta(days=days)


def spent_in_window(conn, period: str, now: datetime.datetime | None = None
                    ) -> float:
    """Total recorded curation spend inside the window.

    `curation_runs.created_at` is written by SQLite's CURRENT_TIMESTAMP, which
    is UTC — so the comparison is done in UTC. Getting this wrong would shift
    the window by the local offset and silently under-count recent spend.
    """
    start = window_start(period, now).strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) AS total FROM curation_runs "
        "WHERE created_at >= ?", (start,)).fetchone()
    return float(row["total"] if hasattr(row, "keys") else row[0])


def status(conn, now: datetime.datetime | None = None) -> dict:
    """What the Settings screen shows. Computed in one place so the readout and
    the enforcement can never disagree about how much has been spent."""
    cap, period = db.effective_spend_cap(conn)
    spent = spent_in_window(conn, period, now)
    unlimited = cap <= config.SPEND_CAP_UNLIMITED
    return {
        "spend_cap_usd": cap,
        "spend_cap_period": period,
        "spend_cap_period_options": sorted(config.SPEND_CAP_PERIOD_DAYS),
        "spent_in_period": round(spent, 4),
        "remaining": None if unlimited else round(max(0.0, cap - spent), 4),
        "unlimited": unlimited,
        "exhausted": (not unlimited) and spent >= cap,
    }


def check(conn, estimate_usd: float, now: datetime.datetime | None = None):
    """Raise CapExceeded if a build estimated at `estimate_usd` would breach the
    cap. Called before every paid CURATION path — including free_llm, which is
    cheap but not free ($0.0512 measured at batch 40, Entry 37). A guard that
    only covers the expensive path is how a cheap path becomes the leak.

    It does NOT cover every paid path in the project, and this docstring used to
    claim it did (audit 2026-08-07, CLAIM-1). Tag-at-ingest and the OpenAI TTS
    fallback both spend on the worker's path without passing through here or
    through the `curation_runs` ledger, so `status()` understates true spend by
    a small, unmeasured amount. Whether they should be brought inside is Grace's
    open call, not an oversight to quietly fix.
    """
    cap, period = db.effective_spend_cap(conn)
    if cap <= config.SPEND_CAP_UNLIMITED:
        return
    spent = spent_in_window(conn, period, now)
    if spent + max(0.0, estimate_usd) > cap:
        raise CapExceeded(spent, estimate_usd, cap, period)
