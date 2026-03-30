"""
Scraper de prix Galaxus.ch utilisant Botasaurus (anti-détection avancée).
"""

from __future__ import annotations

import logging
import re

from botasaurus.browser import browser, Driver
from botasaurus.soupify import soupify

logger = logging.getLogger(__name__)


def _extract_price(text: str) -> float | None:
    prices = re.findall(r"(\d{1,4}[.,]\d{2})", text)
    for p in prices:
        try:
            val = float(p.replace(",", "."))
            if 1 < val < 1000:
                return val
        except ValueError:
            continue
    return None


def _scrape_logic(driver: Driver, game_title: str):
    """Logique de scraping Galaxus pour un jeu."""
    query = game_title.replace(" ", "+")
    search_url = f"https://www.galaxus.ch/fr/search?q={query}"

    try:
        driver.google_get(search_url)
        driver.short_random_sleep()
        driver.sleep(2)

        soup = soupify(driver.page_html)

        product_links = [
            a for a in soup.select("a[href]")
            if "/product/" in a.get("href", "")
        ]

        if not product_links:
            return None

        href = product_links[0]["href"]
        product_url = f"https://www.galaxus.ch{href}" if href.startswith("/") else href

        driver.get(product_url)
        driver.short_random_sleep()
        driver.sleep(3)

        product_soup = soupify(driver.page_html)
        text = product_soup.get_text(" ", strip=True)

        h1 = product_soup.select_one("h1")
        product_title = h1.text.strip() if h1 else ""

        price = _extract_price(text)
        if price is None:
            return None

        img = product_soup.select_one('img[src*="productimages"]') or product_soup.select_one("picture img")
        image_url = img.get("src", "") if img else ""

        rating = None
        rating_match = re.search(r"(\d[.,]\d)\s*/\s*5", text)
        if rating_match:
            rating = float(rating_match.group(1).replace(",", "."))

        review_count = None
        review_match = re.search(r"(\d+)\s*(?:évaluation|avis|bewertung|rating)", text, re.IGNORECASE)
        if review_match:
            review_count = int(review_match.group(1))

        availability = ""
        for keyword in ["En stock", "Disponible", "Livraison", "Livrable", "Épuisé"]:
            idx = text.find(keyword)
            if idx >= 0:
                availability = text[idx:idx + 50].split(".")[0].strip()
                break

        result = {
            "price": price,
            "old_price": None,
            "discount_percent": None,
            "currency": "CHF",
            "product_url": product_url,
            "product_title": product_title,
            "asin": "",
            "image_url": image_url,
            "rating": rating,
            "review_count": review_count,
            "availability": availability,
            "category": "",
            "_game_title": game_title,
        }
        return result

    except Exception as e:
        logger.warning("Erreur scraping Galaxus '%s': %s", game_title, e)
        return None


@browser(headless=True, reuse_driver=True, close_on_crash=True, output=None)
def _scrape_one(driver: Driver, game_title: str):
    return _scrape_logic(driver, game_title)


def _create_parallel_scraper(parallel: int):
    @browser(headless=True, reuse_driver=True, close_on_crash=True, output=None, parallel=parallel)
    def _scrape_parallel(driver: Driver, game_title: str):
        return _scrape_logic(driver, game_title)
    return _scrape_parallel


class GalaxusScraper:
    """Scraper Galaxus.ch avec support parallèle via Botasaurus."""

    def __init__(self, delay: float = 4.0, parallel: int = 1):
        self.delay = delay
        self.parallel = parallel

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def search_price(self, game_title: str) -> dict | None:
        return _scrape_one(game_title)

    def search_prices_batch(self, game_titles: list[str]) -> list[dict | None]:
        """Scrape plusieurs jeux en parallèle."""
        if self.parallel <= 1:
            return [_scrape_one(t) for t in game_titles]
        fn = _create_parallel_scraper(self.parallel)
        return fn(game_titles)
