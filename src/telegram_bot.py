"""
telegram_bot.py
~~~~~~~~~~~~~~~
Sends Kaggle competition notifications to one or more Telegram chats.

Configuration (via environment variables)
-----------------------------------------
TELEGRAM_BOT_TOKEN  – bot token from @BotFather
TELEGRAM_CHAT_ID    – comma-separated list of chat/user IDs to notify

Example TELEGRAM_CHAT_ID:
    "123456789"              → single recipient
    "123456789,987654321"    → two recipients
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

_MAX_MESSAGE_LENGTH = 4096  # Telegram hard limit


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------


def _fmt_size(size_mb: float) -> str:
    if size_mb <= 0:
        return "Unknown"
    if size_mb >= 1024:
        return f"{size_mb / 1024:.1f} GB"
    return f"{size_mb:.0f} MB"


def _fmt_deadline(competition: dict) -> str:
    days = competition.get("days_remaining", 0)
    deadline_str = competition.get("deadline", "")

    if not deadline_str:
        return "Unknown"

    try:
        dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        date_part = dt.strftime("%d %b %Y")
    except (ValueError, TypeError):
        date_part = deadline_str[:10]

    if days == 0:
        return f"ENDED ({date_part})"
    return f"{days} days remaining ({date_part})"


def _fmt_prize(competition: dict) -> str:
    reward = competition.get("reward", "")
    usd = competition.get("reward_usd", 0)
    if usd > 0:
        return f"{reward} (${usd:,})"
    return reward or "No monetary prize"


def _why_score(competition: dict) -> str:
    """Generate a short human-readable rationale."""
    reasons: list[str] = []

    if competition.get("score_relevance", 0) >= 25:
        reasons.append("highly relevant ML/DL topic")
    if competition.get("score_portfolio", 0) >= 15:
        reasons.append("strong portfolio / research value")
    if competition.get("score_prize", 0) >= 11:
        reasons.append("significant prize")
    if competition.get("score_feasibility", 0) >= 13:
        reasons.append("manageable dataset size")
    if competition.get("score_time", 0) >= 9:
        reasons.append("plenty of time to participate")
    if competition.get("score_teams", 0) == 10:
        reasons.append("healthy competition size")

    if not reasons:
        reasons = ["balanced scores across all dimensions"]

    return ", ".join(reasons).capitalize() + "."


def format_competition_message(competition: dict) -> str:
    """Render the competition dict as a Telegram-ready text message."""
    label = competition.get("score_label", "")
    total = competition.get("total_score", 0)
    name = competition.get("name", "Unknown")
    modalities = competition.get("modalities", [])
    category_str = "/".join(m.title() for m in modalities) if modalities else competition.get("category", "General ML")

    lines = [
        f"{label} NEW KAGGLE COMPETITION",
        "",
        f"🏆 {name}",
        "",
        f"⭐ Overall Score: {total}/100",
        "",
        "🧠 Category:",
        f"   {category_str}",
        "",
        "💰 Prize:",
        f"   {_fmt_prize(competition)}",
        "",
        "📦 Dataset:",
        f"   {_fmt_size(competition.get('dataset_size_mb', 0))}",
        f"   {competition.get('file_count', 0):,} files",
        f"   Types: {', '.join(competition.get('file_types', [])) or 'unknown'}",
        "",
        f"👥 Teams: {competition.get('teams', 0):,}",
        "",
        "⏰ Deadline:",
        f"   {_fmt_deadline(competition)}",
        "",
        "📊 Score breakdown:",
        f"   Relevance    {competition.get('score_relevance',  0):2d}/30",
        f"   Portfolio    {competition.get('score_portfolio',  0):2d}/20",
        f"   Prize        {competition.get('score_prize',      0):2d}/15",
        f"   Feasibility  {competition.get('score_feasibility',0):2d}/15",
        f"   Time         {competition.get('score_time',       0):2d}/10",
        f"   Competition  {competition.get('score_teams',      0):2d}/10",
        "",
        "💡 Why:",
        f"   {_why_score(competition)}",
        "",
        "🔗 Kaggle:",
        f"   {competition.get('url', '')}",
    ]

    message = "\n".join(lines)

    # Truncate safely if somehow too long
    if len(message) > _MAX_MESSAGE_LENGTH:
        message = message[: _MAX_MESSAGE_LENGTH - 3] + "..."

    return message


def format_summary_message(competitions: list[dict]) -> str:
    """Render a brief digest message when there are multiple new competitions."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = [
        f"📋 Kaggle Monitor Run — {now}",
        f"Found {len(competitions)} new competition(s) above threshold:\n",
    ]
    entries = []
    for i, c in enumerate(competitions, 1):
        entries.append(
            f"{i}. {c.get('score_label','')} {c.get('name', 'Unknown')}  "
            f"({c.get('total_score', 0)}/100)  →  {c.get('url', '')}"
        )
    return "\n".join(header + entries)


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


class TelegramBot:
    """Sends messages to one or more Telegram chats."""

    def __init__(
        self,
        token: str | None = None,
        chat_ids: list[str] | None = None,
    ) -> None:
        self._token: str = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        raw_ids = chat_ids or os.environ.get("TELEGRAM_CHAT_ID", "")
        if isinstance(raw_ids, str):
            self._chat_ids: list[str] = [
                cid.strip() for cid in raw_ids.split(",") if cid.strip()
            ]
        else:
            self._chat_ids = list(raw_ids)

        if not self._token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is not set. "
                "Set it in your .env file or as an environment variable."
            )
        if not self._chat_ids:
            raise ValueError(
                "TELEGRAM_CHAT_ID is not set. "
                "Set it in your .env file or as an environment variable."
            )

    def _send_to(self, chat_id: str, text: str) -> bool:
        """Send *text* to a single *chat_id*. Returns True on success."""
        url = _TELEGRAM_API.format(token=self._token)
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        try:
            response = requests.post(url, json=payload, timeout=15)
            if response.ok:
                logger.info("Telegram message sent to chat_id=%s", chat_id)
                return True
            else:
                logger.error(
                    "Telegram API error for chat_id=%s: %s %s",
                    chat_id,
                    response.status_code,
                    response.text,
                )
                return False
        except requests.RequestException as exc:
            logger.error("Network error sending to chat_id=%s: %s", chat_id, exc)
            return False

    def send_text(self, text: str) -> int:
        """Broadcast *text* to all configured chat IDs. Returns success count."""
        successes = sum(self._send_to(cid, text) for cid in self._chat_ids)
        logger.info("Sent to %d/%d recipients.", successes, len(self._chat_ids))
        return successes

    def send_competition(self, competition: dict) -> int:
        """Format and broadcast a single competition notification."""
        msg = format_competition_message(competition)
        return self.send_text(msg)

    def send_competitions(self, competitions: list[dict]) -> None:
        """
        Send a brief digest summary first, then one message per competition.
        """
        if not competitions:
            return
        if len(competitions) > 1:
            summary = format_summary_message(competitions)
            self.send_text(summary)
        for comp in competitions:
            self.send_competition(comp)

    def send_test(self) -> bool:
        """Send a simple connectivity test message."""
        return self.send_text("✅ Kaggle Competition Monitor is running correctly!") > 0
