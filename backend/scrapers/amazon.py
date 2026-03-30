"""
Scraper de prix Amazon.fr utilisant Botasaurus (anti-détection avancée).
"""

from __future__ import annotations

import logging
import re

from botasaurus.browser import browser, Driver
from botasaurus.soupify import soupify

logger = logging.getLogger(__name__)


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    cleaned = text.replace("\xa0", "").replace("€", "").replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_search_result(result) -> dict | None:
    asin = result.get("data-asin", "")
    if not asin:
        return None
    title_el = (
        result.select_one("h2 a span")
        or result.select_one("h2 span")
        or result.select_one(".a-text-normal")
    )
    title = title_el.text.strip() if title_el else ""
    price_whole = result.select_one(".a-price-whole")
    if not price_whole:
        return None
    return {"asin": asin, "product_title": title}


def _parse_product_page(soup, asin: str) -> dict:
    data = {"asin": asin, "product_url": f"https://www.amazon.fr/dp/{asin}"}

    title_el = soup.select_one("#productTitle")
    data["product_title"] = title_el.text.strip() if title_el else ""

    price_el = soup.select_one(".a-price .a-offscreen")
    data["price"] = _parse_price(price_el.text) if price_el else None

    old_price_el = soup.select_one(".basisPrice .a-offscreen")
    data["old_price"] = _parse_price(old_price_el.text) if old_price_el else None

    saving_el = soup.select_one(".savingsPercentage")
    data["discount_percent"] = None
    if saving_el:
        match = re.search(r"(\d+)", saving_el.text)
        if match:
            data["discount_percent"] = int(match.group(1))

    rating_el = soup.select_one("#acrPopover")
    data["rating"] = None
    if rating_el:
        match = re.search(r"([\d,]+)", rating_el.get("title", ""))
        if match:
            data["rating"] = float(match.group(1).replace(",", "."))

    review_el = soup.select_one("#acrCustomerReviewText") or soup.select_one("#acrCustomerReviewCount")
    data["review_count"] = None
    if review_el:
        text = review_el.text.strip().lower()
        match_k = re.search(r"([\d,]+)\s*k", text)
        if match_k:
            try:
                data["review_count"] = int(float(match_k.group(1).replace(",", ".")) * 1000)
            except ValueError:
                pass
        else:
            digits = re.sub(r"[^\d]", "", text)
            try:
                data["review_count"] = int(digits) if digits else None
            except ValueError:
                pass

    avail_el = soup.select_one("#availability")
    data["availability"] = avail_el.get_text(strip=True) if avail_el else ""

    img_el = soup.select_one("#landingImage")
    data["image_url"] = ""
    if img_el:
        data["image_url"] = img_el.get("data-old-hires") or img_el.get("src", "")

    breadcrumbs = [b.text.strip() for b in soup.select("#wayfinding-breadcrumbs_feature_div a")]
    data["category"] = " > ".join(breadcrumbs)

    return data


def _scrape_logic(driver: Driver, game_title: str):
    """Logique de scraping Amazon pour un jeu."""
    query = game_title.replace(" ", "+")
    url = f"https://www.amazon.fr/s?k={query}&i=videogames"

    try:
        driver.google_get(url)
        driver.short_random_sleep()

        soup = soupify(driver.page_html)
        results = soup.select('[data-component-type="s-search-result"]')

        search_hit = None
        for r in results[:5]:
            parsed = _parse_search_result(r)
            if parsed:
                search_hit = parsed
                break

        if not search_hit:
            return None

        driver.get(f"https://www.amazon.fr/dp/{search_hit['asin']}")
        driver.short_random_sleep()

        product_soup = soupify(driver.page_html)
        data = _parse_product_page(product_soup, search_hit["asin"])

        if data["price"] is None:
            return None

        data["_game_title"] = game_title
        return data

    except Exception as e:
        logger.warning("Erreur scraping Amazon '%s': %s", game_title, e)
        return None


@browser(headless=True, reuse_driver=True, close_on_crash=True, output=None)
def _scrape_one(driver: Driver, game_title: str):
    return _scrape_logic(driver, game_title)


def _create_parallel_scraper(parallel: int):
    @browser(headless=True, reuse_driver=True, close_on_crash=True, output=None, parallel=parallel)
    def _scrape_parallel(driver: Driver, game_title: str):
        return _scrape_logic(driver, game_title)
    return _scrape_parallel


class AmazonScraper:
    """Scraper Amazon.fr avec support parallèle via Botasaurus."""

    def __init__(self, delay: float = 3.0, parallel: int = 1):
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
