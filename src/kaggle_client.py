"""
kaggle_client.py
~~~~~~~~~~~~~~~~
Wraps the Kaggle API and returns normalized competition dicts.

Every other module works with the Competition dict shape – never raw API objects.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from kaggle.api.kaggle_api_extended import KaggleApi  # type: ignore

logger = logging.getLogger(__name__)


def _setup_kaggle_auth() -> None:
    """
    Support both Kaggle token formats:

    New format (KGAT_...):  Set KAGGLE_API_TOKEN env var.
    Old format:             Set KAGGLE_USERNAME + KAGGLE_KEY env vars,
                            or place kaggle.json at ~/.kaggle/kaggle.json.

    The new-style token is detected by the 'KGAT_' prefix.
    """
    api_token = os.environ.get("KAGGLE_API_TOKEN", "")
    if api_token.startswith("KGAT_"):
        # New-style token — the kaggle library reads KAGGLE_API_TOKEN natively
        logger.info("Using new-style KAGGLE_API_TOKEN for authentication.")
    elif os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        logger.info("Using KAGGLE_USERNAME + KAGGLE_KEY for authentication.")
    else:
        logger.warning(
            "No Kaggle credentials found in environment. "
            "Set KAGGLE_API_TOKEN (new-style) or KAGGLE_USERNAME + KAGGLE_KEY (old-style)."
        )


# ---------------------------------------------------------------------------
# Competition dict shape (V1)
# ---------------------------------------------------------------------------
# {
#     "id":               str   – slugified competition ref, e.g. "titanic"
#     "name":             str   – human-readable title
#     "url":              str   – full Kaggle URL
#     "description":      str   – short description / subtitle
#     "deadline":         str   – ISO-8601 string  (UTC)
#     "days_remaining":   int   – calendar days until deadline (0 if past)
#     "reward":           str   – prize string, e.g. "$50,000" or "Knowledge"
#     "reward_usd":       int   – parsed USD amount (0 for non-cash)
#     "teams":            int   – number of participating teams
#     "category":         str   – Kaggle category tag
#     "evaluation_metric":str   – evaluation metric name
#     "dataset_size_mb":  float – total dataset size (populated later)
#     "file_count":       int   – number of dataset files   (populated later)
#     "file_types":       list  – unique file extensions    (populated later)
# }
# ---------------------------------------------------------------------------


def _parse_reward_usd(reward_str: str) -> int:
    """Extract integer USD value from Kaggle prize strings."""
    if not reward_str:
        return 0
    cleaned = reward_str.replace(",", "").replace("$", "").replace(" ", "")
    # Handle formats like "$50,000" or "50000" or "Knowledge"
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    return int(digits) if digits else 0


def _days_remaining(deadline_str: str) -> int:
    """Return calendar days until *deadline_str* (ISO-8601, UTC). 0 if past."""
    if not deadline_str:
        return 0
    try:
        # Handle both naive ('2026-11-02T23:59:00') and aware ('...+00:00') strings
        dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            # Kaggle returns naive datetimes - treat as UTC
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = dt - now
        return max(0, delta.days)
    except (ValueError, TypeError):
        return 0


def _days_remaining_from_dt(deadline_dt: Any) -> int:
    """Compute days remaining directly from a datetime object."""
    if deadline_dt is None:
        return 0
    try:
        if deadline_dt.tzinfo is None:
            deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = deadline_dt - now
        return max(0, delta.days)
    except (AttributeError, TypeError):
        return 0


def _normalize(raw: Any) -> dict:
    """Convert a raw Kaggle API competition object into our standard dict."""
    ref: str = getattr(raw, "ref", "") or ""
    title: str = getattr(raw, "title", "") or ""
    deadline_raw = getattr(raw, "deadline", None)
    # isoformat() on a naive datetime gives no timezone — store with explicit UTC marker
    deadline_str = (deadline_raw.isoformat() + "+00:00") if deadline_raw else ""
    reward: str = str(getattr(raw, "reward", "") or "")
    description: str = str(getattr(raw, "description", "") or "")
    teams: int = int(getattr(raw, "teamCount", 0) or 0)
    category: str = str(getattr(raw, "category", "") or "")
    evaluation_metric: str = str(getattr(raw, "evaluationMetric", "") or "")

    return {
        "id": ref,
        "name": title,
        "url": f"https://www.kaggle.com/competitions/{ref}",
        "description": description,
        "deadline": deadline_str,
        "days_remaining": _days_remaining_from_dt(deadline_raw),
        "reward": reward,
        "reward_usd": _parse_reward_usd(reward),
        "teams": teams,
        "category": category,
        "evaluation_metric": evaluation_metric,
        # Populated by dataset_analyzer.py
        "dataset_size_mb": 0.0,
        "file_count": 0,
        "file_types": [],
    }


class KaggleClient:
    """Thin wrapper around KaggleApi for competition listing."""

    def __init__(self) -> None:
        _setup_kaggle_auth()
        self._api = KaggleApi()
        self._api.authenticate()
        logger.info("Kaggle API authenticated successfully.")


    def fetch_competitions(
        self,
        page: int = 1,
        page_size: int = 100,
        sort_by: str = "latestDeadline",
        category: str = "all",
        group: str = "general",
        search: str = "",
    ) -> list[dict]:
        """
        Fetch a page of active competitions.

        Parameters
        ----------
        page:      API page number (1-indexed).
        page_size: Results per page (max 100 per Kaggle API).
        sort_by:   One of 'latestDeadline', 'prize', 'numberOfTeams', etc.
        category:  Filter by Kaggle category; use 'all' for no filter.
        group:     'general' = active only, 'entered' = entered, 'inClass' = course.
        search:    Optional full-text search string.

        Returns
        -------
        List of normalized competition dicts.
        """
        logger.info(
            "Fetching competitions: page=%d sort_by=%s category=%s group=%s search=%r",
            page,
            sort_by,
            category,
            group,
            search,
        )

        raw_list = self._api.competitions_list(
            page=page,
            search=search,
            sort_by=sort_by,
            category=category,
            group=group,
        )

        competitions = [_normalize(c) for c in raw_list]
        logger.info("Fetched %d competitions.", len(competitions))
        return competitions

    def fetch_all_active(self, max_pages: int = 5, group: str = "general") -> list[dict]:
        """
        Walk multiple pages and return all active competitions.

        Stops early when a page returns fewer results than expected
        (signals last page).

        group='general' filters to active competitions only.
        """
        all_comps: list[dict] = []
        for page_num in range(1, max_pages + 1):
            page = self.fetch_competitions(page=page_num, group=group)
            if not page:
                logger.info("Page %d empty - stopping pagination.", page_num)
                break
            all_comps.extend(page)
            logger.info("Accumulated %d competitions so far.", len(all_comps))
            if len(page) < 100:
                # Last page (Kaggle returns < 100 on the final page)
                break

        return all_comps
