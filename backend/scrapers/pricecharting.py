"""
Scraper de prix PriceCharting.com utilisant Botasaurus @request (pas de navigateur).
Récupère les prix collector : loose, CIB, neuf, gradé, boîte seule, manuel seul.
Très rapide (~0.5s par jeu) car pas de Chrome.
"""

from __future__ import annotations

import logging
import re

from botasaurus.request import request, Request
from botasaurus.soupify import soupify

logger = logging.getLogger(__name__)


def _parse_usd(text: str) -> float | None:
    if not text:
        return None
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


# Consoles PAL sur PriceCharting (seules ces valeurs sont acceptées)
PAL_CONSOLE_NAMES = {
    "pal super nintendo", "pal nes", "pal nintendo 64",
    "pal gameboy advance", "pal sega saturn", "pal neo geo",
    "pal gameboy", "pal sega genesis",
}

# Mots-clés qui indiquent que ce n'est PAS un jeu vidéo
EXCLUDED_KEYWORDS = {
    "card", "cards", "trading", "tcg", "booster", "pokemon card",
    "magic", "yugioh", "yu-gi-oh", "figurine", "amiibo", "guide",
    "strategy guide", "manga", "comic", "soundtrack", "ost",
}


def _scrape_logic(req: Request, game_title: str):
    """Scrape un jeu sur PriceCharting via HTTP, en priorité PAL (Europe)."""
    query = game_title.replace(" ", "+")
    search_url = f"https://www.pricecharting.com/search-products?q={query}&type=videogames"

    try:
        # 1. Recherche
        resp = req.get(search_url)
        soup = soupify(resp)
        rows = soup.select("table tr")

        # Collecter tous les résultats valides
        candidates = []
        for row in rows[1:]:
            link = row.select_one("a[href*='/game/']")
            if not link:
                continue
            tds = row.select("td")
            if len(tds) < 4:
                continue
            loose_text = tds[3].get_text(strip=True)
            if not _parse_usd(loose_text):
                continue
            # Colonne "Set" = nom de la console
            console_name = tds[2].get_text(strip=True).lower() if len(tds) > 2 else ""
            href = link.get("href", "")
            url = f"https://www.pricecharting.com{href}" if href.startswith("/") else href
            title = link.get_text(strip=True)
            # Exclure les non-jeux (cartes, figurines, guides, etc.)
            title_lower = title.lower()
            console_lower = console_name.lower()
            if any(kw in title_lower or kw in console_lower for kw in EXCLUDED_KEYWORDS):
                continue
            is_pal = console_name in PAL_CONSOLE_NAMES
            candidates.append({
                "url": url,
                "title": title,
                "console": console_name,
                "is_pal": is_pal,
            })

        if not candidates:
            return None

        # PAL uniquement
        pal_candidates = [c for c in candidates if c["is_pal"]]
        if not pal_candidates:
            return None
        best = pal_candidates[0]
        product_url = best["url"]
        product_title = best["title"]

        # 2. Page produit
        resp2 = req.get(product_url)
        soup2 = soupify(resp2)

        # Les 6 premiers .price sont: loose, CIB, neuf, gradé, boîte, manuel
        price_els = soup2.select(".price")
        if len(price_els) < 3:
            return None

        loose = _parse_usd(price_els[0].get_text(strip=True))
        cib = _parse_usd(price_els[1].get_text(strip=True))
        new = _parse_usd(price_els[2].get_text(strip=True))
        graded = _parse_usd(price_els[3].get_text(strip=True)) if len(price_els) > 3 else None
        box_only = _parse_usd(price_els[4].get_text(strip=True)) if len(price_els) > 4 else None
        manual_only = _parse_usd(price_els[5].get_text(strip=True)) if len(price_els) > 5 else None

        if not loose:
            return None

        # Métadonnées
        meta = {}
        for row in soup2.select("#attribute tr"):
            tds = row.select("td")
            if len(tds) == 2:
                key = tds[0].get_text(strip=True).rstrip(":")
                val = tds[1].get_text(strip=True)
                meta[key] = val

        return {
            "price": loose,
            "cib_price": cib,
            "new_price": new,
            "graded_price": graded,
            "box_only_price": box_only,
            "manual_only_price": manual_only,
            "old_price": None,
            "discount_percent": None,
            "currency": "USD",
            "product_url": product_url,
            "product_title": product_title or "",
            "asin": meta.get("ASIN (Amazon)", ""),
            "image_url": "",
            "rating": None,
            "review_count": None,
            "availability": "",
            "category": meta.get("Genre", ""),
            "_game_title": game_title,
        }

    except Exception as e:
        logger.warning("Erreur scraping PriceCharting '%s': %s", game_title, e)
        return None


@request(output=None, max_retry=2)
def _scrape_one(req: Request, game_title: str):
    return _scrape_logic(req, game_title)


def _create_parallel_scraper(parallel: int):
    @request(output=None, parallel=parallel, max_retry=2)
    def _scrape_parallel(req: Request, game_title: str):
        return _scrape_logic(req, game_title)
    return _scrape_parallel


class PriceChartingScraper:
    """Scraper PriceCharting.com — mode @request (pas de Chrome, ultra rapide)."""

    def __init__(self, delay: float = 1.0, parallel: int = 1):
        self.delay = delay
        self.parallel = parallel

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def search_price(self, game_title: str) -> dict | None:
        import time
        time.sleep(self.delay)
        return _scrape_one(game_title)

    def search_prices_batch(self, game_titles: list[str]) -> list[dict | None]:
        if self.parallel <= 1:
            import time
            results = []
            for t in game_titles:
                time.sleep(self.delay)
                results.append(_scrape_one(t))
            return results
        fn = _create_parallel_scraper(self.parallel)
        return fn(game_titles)
