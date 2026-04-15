"""Envoi de notifications utilisateur (Telegram)."""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def send_telegram(text: str) -> bool:
    """Envoie un message Telegram via le bot configuré.

    Lit `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` dans l'environnement.
    Retourne True si envoyé, False sinon (log en warning si non configuré).
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        logger.warning("Telegram not configured, skipping notification: %s", text)
        return False

    try:
        resp = requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        return False
