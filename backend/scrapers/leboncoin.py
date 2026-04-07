"""
Scraper LeBonCoin.fr pour les annonces de jeux rétro.
Utilise un profil Chrome persistant pour garder les cookies Datadome.
Le captcha n'apparaît qu'une seule fois (premier lancement).
"""

from __future__ import annotations

import logging
import re

from botasaurus.browser import browser, Driver
from botasaurus.soupify import soupify

logger = logging.getLogger(__name__)

CONSOLE_SEARCHES = {
    "snes": "super+nintendo+jeu",
    "nes": "nintendo+nes+jeu",
    "n64": "nintendo+64+jeu",
    "neo": "neo+geo+jeu",
    "gba": "game+boy+advance+jeu",
    "saturn": "sega+saturn+jeu",
}


def _extract_listing_detail(driver: Driver, url: str) -> dict | None:
    """Extrait les données d'une annonce LeBonCoin."""
    try:
        driver.get(url)
        driver.short_random_sleep()
        driver.sleep(3)

        soup = soupify(driver.page_html)
        text = soup.get_text(" ", strip=True)

        h1 = soup.select_one("h1")
        title = h1.text.strip() if h1 else ""
        if not title:
            return None

        price_match = re.search(r"(\d[\d\s]*)\s*€", text)
        if not price_match:
            return None
        price = float(price_match.group(1).replace(" ", ""))

        location = ""
        loc_match = re.search(r"(\d{5})\s+(\w[\w\s-]{2,30})", text)
        if loc_match:
            location = loc_match.group(0).strip()

        img = soup.select_one('img[src*="leboncoin"]') or soup.select_one("img[alt]")
        image_url = img.get("src", "") if img else ""

        return {
            "title": title,
            "listing_url": url,
            "image_url": image_url,
            "current_price": price,
            "buy_now_price": price,
            "currency": "EUR",
            "bid_count": 0,
            "condition": "",
            "location": location,
        }

    except Exception as e:
        logger.warning("Erreur LeBonCoin '%s': %s", url, e)
        return None


@browser(
    headless=False,
    reuse_driver=True,
    close_on_crash=True,
    output=None,
    remove_default_browser_check_argument=True,
    profile="leboncoin_session",
)
def scrape_leboncoin_console(driver: Driver, platform_slug: str):
    """
    Scrape les annonces LeBonCoin pour une console.
    Le profil persistant garde les cookies Datadome.
    Le captcha n'apparaît qu'au tout premier lancement.
    """
    search_query = CONSOLE_SEARCHES.get(platform_slug)
    if not search_query:
        return []

    driver.enable_human_mode()

    search_url = f"https://www.leboncoin.fr/recherche?text={search_query}&category=43"
    driver.get(search_url)
    driver.sleep(8)

    # Vérifier si la page a chargé (ou si captcha)
    soup = soupify(driver.page_html)
    links = [a for a in soup.select("a[href]") if "/ad/" in a.get("href", "")]

    if not links:
        # Attendre plus longtemps (captcha possible)
        logger.info("LeBonCoin: pas d'annonces, attente captcha...")
        driver.sleep(30)
        soup = soupify(driver.page_html)
        links = [a for a in soup.select("a[href]") if "/ad/" in a.get("href", "")]

    if not links:
        logger.warning("LeBonCoin %s: aucune annonce (captcha non résolu ?)", platform_slug)
        return []

    # Collecter les URLs uniques
    listing_urls = []
    seen = set()
    for a in links:
        href = a.get("href", "")
        clean = href.split("?")[0]
        if clean not in seen:
            seen.add(clean)
            full_url = f"https://www.leboncoin.fr{href}" if href.startswith("/") else href
            listing_urls.append(full_url)

    logger.info("LeBonCoin %s: %d annonces trouvées", platform_slug, len(listing_urls))

    # Visiter chaque annonce
    results = []
    for url in listing_urls:
        listing = _extract_listing_detail(driver, url)
        if listing:
            listing["platform_slug"] = platform_slug
            results.append(listing)

    return results
