"""
Client eBay API pour récupérer les prix des jeux rétro.
Browse API pour les annonces en cours, avec détection de région (PAL/NTSC/JP).
"""

from __future__ import annotations

import base64
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

EBAY_APP_ID = os.environ.get("EBAY_APP_ID", "")
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID", "")
EBAY_SANDBOX = os.environ.get("EBAY_SANDBOX", "false").lower() == "true"

if EBAY_SANDBOX:
    OAUTH_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    BROWSE_URL = "https://api.sandbox.ebay.com/buy/browse/v1"
else:
    OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    BROWSE_URL = "https://api.ebay.com/buy/browse/v1"

EBAY_CATEGORY_VIDEOGAMES = "139973"

PLATFORM_FILTERS = {
    "snes": "Super Nintendo",
    "nes": "Nintendo NES",
    "n64": "Nintendo 64",
    "neo": "Neo Geo",
    "gba": "Game Boy Advance",
    "saturn": "Sega Saturn",
    "ps1": "Sony PlayStation",
    "dreamcast": "Sega Dreamcast",
}

# Patterns de détection de région dans les titres
PAL_PATTERNS = re.compile(
    r"\bPAL\b|\bPAL[ -]?(FAH|FRA|FRG|EUR|UKV|SCN|ESP|ITA|NOE|HOL|AUS)\b|\bEuropean?\b|\bEurope\b",
    re.IGNORECASE,
)
NTSC_US_PATTERNS = re.compile(
    r"\bNTSC[ -]?U\b|\bNTSC\b|\bUS\s?version\b|\b\(US\)\b|\bUSA\b",
    re.IGNORECASE,
)
JP_PATTERNS = re.compile(
    r"\bNTSC[ -]?J\b|\bJAP\b|\bJPN\b|\b\(JP\)\b|\bJapan\b|\bJapanese\b|\bSuper Famicom\b|\bFamicom\b",
    re.IGNORECASE,
)


def detect_region(title: str) -> str:
    """Détecte la région à partir du titre de l'annonce."""
    if PAL_PATTERNS.search(title):
        return "PAL"
    if JP_PATTERNS.search(title):
        return "JP"
    if NTSC_US_PATTERNS.search(title):
        return "NTSC"
    return "unknown"


_token_cache: dict[str, tuple[str, float]] = {}  # key → (token, expiry_timestamp)


def _get_oauth_token() -> str | None:
    """Obtient un token OAuth eBay, mis en cache ~1h50 (token valide 2h)."""
    import time

    if not EBAY_APP_ID or not EBAY_CERT_ID:
        logger.error("EBAY_APP_ID ou EBAY_CERT_ID non configuré")
        return None

    cache_key = EBAY_APP_ID
    now = time.time()
    if cache_key in _token_cache:
        token, expiry = _token_cache[cache_key]
        if now < expiry:
            return token

    credentials = base64.b64encode(f"{EBAY_APP_ID}:{EBAY_CERT_ID}".encode()).decode()
    resp = requests.post(
        OAUTH_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {credentials}",
        },
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        logger.error("Erreur OAuth eBay: %s %s", resp.status_code, resp.text[:200])
        return None

    data = resp.json()
    token = data.get("access_token")
    expires_in = data.get("expires_in", 7200)  # 2h par défaut
    _token_cache[cache_key] = (token, now + expires_in - 600)  # marge 10 min
    logger.info("eBay OAuth token obtenu (expire dans %ds)", expires_in)
    return token


def search_ebay(game_title: str, platform_slug: str = "", limit: int = 20, pal_only: bool = True) -> list[dict]:
    """
    Recherche un jeu sur eBay.fr et retourne les annonces.
    Filtre par région PAL si pal_only=True.
    """
    token = _get_oauth_token()
    if not token:
        return []

    platform_name = PLATFORM_FILTERS.get(platform_slug, "")
    query = f"{game_title} {platform_name}".strip()
    if pal_only:
        query += " PAL"

    try:
        resp = requests.get(
            f"{BROWSE_URL}/item_summary/search",
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR",
            },
            params={
                "q": query,
                "category_ids": EBAY_CATEGORY_VIDEOGAMES,
                "filter": "conditions:{USED|VERY_GOOD|GOOD|ACCEPTABLE|UNSPECIFIED}",
                "sort": "price",
                "limit": limit,
            },
            timeout=15,
        )

        if resp.status_code != 200:
            logger.warning("eBay search error: %s", resp.status_code)
            return []

        data = resp.json()
        items = data.get("itemSummaries", [])

        results = []
        for item in items:
            price_info = item.get("price", {})
            price_val = price_info.get("value")
            if not price_val:
                continue

            title = item.get("title", "")
            region = detect_region(title)
            condition = item.get("condition", "")
            location = item.get("itemLocation", {}).get("country", "")

            results.append({
                "title": title,
                "price": float(price_val),
                "currency": price_info.get("currency", "EUR"),
                "condition": condition,
                "region": region,
                "country": location,
                "listing_url": item.get("itemWebUrl", ""),
                "image_url": item.get("image", {}).get("imageUrl", ""),
                "item_id": item.get("itemId", ""),
                "buying_options": item.get("buyingOptions", []),
                "bid_count": item.get("bidCount", 0),
            })

        return results

    except Exception as e:
        logger.warning("Erreur eBay search '%s': %s", game_title, e)
        return []


class EbayScraper:
    """Scraper eBay API — pas de navigateur, API REST directe."""

    def __init__(self, delay: float = 0.5, parallel: int = 1):
        self.delay = delay
        self.parallel = parallel
        self._load_env()

    def _load_env(self):
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        os.environ.setdefault(key.strip(), val.strip())
            global EBAY_APP_ID, EBAY_CERT_ID, EBAY_SANDBOX
            EBAY_APP_ID = os.environ.get("EBAY_APP_ID", "")
            EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID", "")
            EBAY_SANDBOX = os.environ.get("EBAY_SANDBOX", "false").lower() == "true"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def search_price(self, game_title: str, platform_slug: str = "") -> dict | None:
        """Cherche un jeu sur eBay. Retourne le moins cher PAL, puis NTSC, puis JP."""
        import time
        time.sleep(self.delay)

        items = search_ebay(game_title, platform_slug, limit=20, pal_only=False)

        if not items:
            return None

        # Séparer par région
        pal_items = [i for i in items if i["region"] == "PAL"]
        ntsc_items = [i for i in items if i["region"] == "NTSC"]
        jp_items = [i for i in items if i["region"] == "JP"]
        unknown_items = [i for i in items if i["region"] == "unknown"]

        # Priorité : PAL > NTSC > unknown > JP
        best_items = pal_items or ntsc_items or unknown_items or jp_items
        best_items.sort(key=lambda x: x["price"])
        best = best_items[0]

        # Stats
        all_prices = [i["price"] for i in items]
        avg_price = sum(all_prices) / len(all_prices)

        region_summary = []
        if pal_items:
            region_summary.append(f"{len(pal_items)} PAL")
        if ntsc_items:
            region_summary.append(f"{len(ntsc_items)} NTSC")
        if jp_items:
            region_summary.append(f"{len(jp_items)} JP")
        if unknown_items:
            region_summary.append(f"{len(unknown_items)} autres")

        return {
            "price": best["price"],
            "old_price": round(avg_price, 2) if len(items) > 1 else None,
            "discount_percent": None,
            "currency": best["currency"],
            "product_url": best["listing_url"],
            "product_title": best["title"],
            "asin": "",
            "image_url": best.get("image_url", ""),
            "rating": None,
            "review_count": len(items),
            "availability": f"{len(items)} annonces ({', '.join(region_summary)}), {best['condition']}",
            "category": f"Region: {best['region']}",
        }

    def search_prices_batch(self, game_titles: list[str]) -> list[dict | None]:
        import time
        results = []
        for t in game_titles:
            time.sleep(self.delay)
            results.append(self.search_price(t))
        return results
