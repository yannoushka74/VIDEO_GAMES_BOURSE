"""
Cache de taux de change via Frankfurter.app (gratuit, sans clé API).
Refresh toutes les 24h.
"""

import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, float]] = {}  # key → (rate, timestamp)
CACHE_TTL = 86400  # 24h


def get_rate(from_currency: str = "USD", to_currency: str = "CHF") -> Optional[float]:
    """Retourne le taux de conversion from→to, mis en cache 24h."""
    key = f"{from_currency}_{to_currency}"
    now = time.time()

    if key in _cache:
        rate, ts = _cache[key]
        if now - ts < CACHE_TTL:
            return rate

    try:
        resp = requests.get(
            f"https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}",
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        rate = data["rates"][to_currency]
        _cache[key] = (rate, now)
        logger.info("Exchange rate %s→%s: %.5f", from_currency, to_currency, rate)
        return rate
    except Exception as e:
        logger.warning("Exchange rate fetch failed (%s→%s): %s", from_currency, to_currency, e)
        # Fallback hard-codé si API down
        fallbacks = {
            "USD_CHF": 0.79,
            "USD_EUR": 0.86,
            "CHF_USD": 1.27,
            "CHF_EUR": 1.09,
            "EUR_CHF": 0.92,
            "EUR_USD": 1.17,
        }
        return fallbacks.get(key)


def usd_to_chf(usd_amount: float) -> float:
    """Convertit USD → CHF avec le taux du jour."""
    rate = get_rate("USD", "CHF") or 0.79
    return round(usd_amount * rate, 2)


def chf_to_usd(chf_amount: float) -> float:
    """Convertit CHF → USD avec le taux du jour."""
    rate = get_rate("USD", "CHF") or 0.79
    return round(chf_amount / rate, 2)


def chf_to_eur(chf_amount: float) -> float:
    """Convertit CHF → EUR avec le taux du jour."""
    rate = get_rate("CHF", "EUR") or 1.09
    return round(chf_amount * rate, 2)
