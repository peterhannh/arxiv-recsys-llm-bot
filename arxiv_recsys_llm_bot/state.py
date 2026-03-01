"""State management — ensures no gap dates between runs."""

import json
from datetime import datetime, timedelta, timezone

from arxiv_recsys_llm_bot.config import STATE_FILE, log


def load_state() -> dict:
    """Load the last run state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(state: dict) -> None:
    """Persist run state to disk."""
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def get_lookback_cutoff(force_lookback_days: int | None = None) -> datetime:
    """
    Determine the cutoff date for fetching papers.

    Priority:
      1. If --lookback-days is explicitly given, use that.
      2. Otherwise read last_run_date from state.json and fetch from there.
      3. If no state exists, default to 3 days ago.
    """
    if force_lookback_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=force_lookback_days)
        log.info("Using explicit lookback: %d days (cutoff %s)", force_lookback_days, cutoff.date())
        return cutoff

    state = load_state()
    last_run = state.get("last_run_date")
    if last_run:
        cutoff = datetime.fromisoformat(last_run)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        # ArXiv publishes in daily batches (~20:00 ET / 01:00 UTC).
        # Paper timestamps reflect submission time, which can be 1-3 days
        # before announcement (especially over weekends).  Use a 48-hour
        # overlap to cover weekend gaps and boundary edge cases.
        cutoff -= timedelta(hours=48)
        log.info("Resuming from last run: %s (cutoff %s)", last_run, cutoff.isoformat())
        return cutoff

    # First run ever — default to 3 days (covers weekend gaps)
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    log.info("No previous run found. Defaulting to 3-day lookback (cutoff %s)", cutoff.date())
    return cutoff
