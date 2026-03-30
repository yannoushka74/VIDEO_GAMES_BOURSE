"""
Scraper Ricardo.ch pour les enchères de jeux rétro.
Parcourt les résultats de recherche par console et extrait les annonces.
"""

from __future__ import annotations

import json
import logging
import re

from botasaurus.browser import browser, Driver
from botasaurus.soupify import soupify

logger = logging.getLogger(__name__)

# Recherches Ricardo par plateforme
CONSOLE_SEARCHES = {
    "snes": "super+nintendo+jeu",
    "nes": "nintendo+NES+jeu",
    "n64": "nintendo+64+jeu",
    "neo": "neo+geo+jeu",
    "gba": "game+boy+advance+jeu",
    "saturn": "sega+saturn+jeu",
}


def _extract_listing_from_page(driver: Driver, url: str) -> dict | None:
    """Extrait les données d'une annonce Ricardo."""
    try:
        driver.get(url)
        driver.short_random_sleep()
        driver.sleep(3)

        soup = soupify(driver.page_html)
        text = soup.get_text(" ", strip=True)

        # Titre
        h1 = soup.select_one("h1")
        title = h1.text.strip() if h1 else ""
        if not title:
            return None

        # Prix depuis le texte
        chf_prices = re.findall(r"CHF\s*([\d']+[.,]?\d*)", text)
        current_price = None
        buy_now_price = None

        if chf_prices:
            # Premier prix = enchère actuelle ou prix de départ
            try:
                current_price = float(chf_prices[0].replace("'", "").replace(",", "."))
            except ValueError:
                pass

        # Achat direct
        achat_match = re.search(r"Achat\s*direct[^C]*CHF\s*([\d']+[.,]?\d*)", text, re.IGNORECASE)
        if not achat_match:
            achat_match = re.search(r"([\d']+[.,]?\d*)\s*Achat\s*direct", text, re.IGNORECASE)
        if achat_match:
            try:
                buy_now_price = float(achat_match.group(1).replace("'", "").replace(",", "."))
            except ValueError:
                pass

        # Nombre d'enchères
        bid_match = re.search(r"Enchères\s*\((\d+)\)", text, re.IGNORECASE)
        if not bid_match:
            bid_match = re.search(r"(\d+)\s*enchère", text, re.IGNORECASE)
        bid_count = int(bid_match.group(1)) if bid_match else 0

        # Date de fin
        ends_at = None
        end_match = re.search(
            r"(\w+ \d+ \w+ \d{4})[^0-9]*(\d{2}:\d{2})",
            text,
        )
        if end_match:
            from django.utils.dateparse import parse_datetime
            import locale
            date_str = f"{end_match.group(1)} {end_match.group(2)}"
            ends_at = date_str  # On stocke en texte, le parsing sera fait plus tard

        # Image
        img = soup.select_one('img[src*="ricardo"], img[src*="images"]')
        image_url = ""
        if img:
            src = img.get("src", "")
            if "ricardo" in src or "images" in src:
                image_url = src

        if current_price is None:
            return None

        return {
            "title": title,
            "listing_url": url,
            "image_url": image_url,
            "current_price": current_price,
            "buy_now_price": buy_now_price,
            "bid_count": bid_count,
            "ends_at_text": ends_at,
        }

    except Exception as e:
        logger.warning("Erreur scraping Ricardo '%s': %s", url, e)
        return None


def _collect_listing_urls(driver: Driver, search_url: str) -> list[str]:
    """Parcourt toutes les pages de résultats et collecte les URLs d'annonces."""
    all_links = []
    seen = set()
    page = 1

    driver.google_get(search_url)
    driver.short_random_sleep()
    driver.sleep(5)

    while True:
        soup = soupify(driver.page_html)

        # Extraire les URLs des annonces sur cette page
        page_links = []
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "/fr/a/" in href:
                full_url = f"https://www.ricardo.ch{href}" if href.startswith("/") else href
                # Normaliser l'URL (enlever les query params)
                clean_url = full_url.split("?")[0]
                if clean_url not in seen:
                    seen.add(clean_url)
                    page_links.append(full_url)

        all_links.extend(page_links)
        logger.info("Ricardo page %d: %d nouvelles annonces (total: %d)", page, len(page_links), len(all_links))

        if not page_links:
            break

        # Chercher le bouton "page suivante"
        next_btn = None
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True).lower()
            # Bouton suivant: soit aria-label, soit texte, soit icône >
            aria = a.get("aria-label", "").lower()
            if "next" in aria or "suivant" in aria or "nächste" in aria:
                next_btn = href
                break
            if text in (">", "›", "suivant", "next", "weiter"):
                next_btn = href
                break

        if not next_btn:
            # Essayer de trouver le lien de page suivante par numéro
            current_page_param = f"page={page}"
            next_page_param = f"page={page + 1}"
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if next_page_param in href:
                    next_btn = href
                    break

        if not next_btn:
            break

        # Naviguer vers la page suivante
        next_url = f"https://www.ricardo.ch{next_btn}" if next_btn.startswith("/") else next_btn
        driver.get(next_url)
        driver.short_random_sleep()
        driver.sleep(4)
        page += 1

        # Sécurité: max 20 pages
        if page > 20:
            break

    return all_links


@browser(headless=True, reuse_driver=True, close_on_crash=True, output=None)
def scrape_ricardo_console(driver: Driver, platform_slug: str):
    """Scrape toutes les annonces Ricardo pour une console (toutes les pages)."""
    search_query = CONSOLE_SEARCHES.get(platform_slug)
    if not search_query:
        return []

    search_url = f"https://www.ricardo.ch/fr/s/{search_query}"

    # 1. Collecter toutes les URLs d'annonces (pagination)
    listing_links = _collect_listing_urls(driver, search_url)
    logger.info("Ricardo %s: %d annonces totales", platform_slug, len(listing_links))

    # 2. Visiter chaque annonce
    results = []
    for url in listing_links:
        listing = _extract_listing_from_page(driver, url)
        if listing:
            listing["platform_slug"] = platform_slug
            results.append(listing)

    return results
