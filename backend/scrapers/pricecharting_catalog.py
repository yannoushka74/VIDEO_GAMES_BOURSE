"""Scrape le catalogue PriceCharting par console (pages liste).

Chaque page console liste ~150 jeux avec loose/CIB/new prices.
URL pattern : https://www.pricecharting.com/console/{slug}?cursor={offset}

Usage interne via le management command `import_pricecharting`.
Pas de dépendance botasaurus — utilise requests + BeautifulSoup.
"""

from __future__ import annotations

import logging
import time
from typing import Iterator

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PAL_CONSOLES = {
    "neo": "neo-geo-aes",  # Pas de page PAL sur PriceCharting pour Neo Geo
    "nes": "pal-nes",
    "snes": "pal-super-nintendo",
    "gba": "pal-gameboy-advance",
    "saturn": "pal-sega-saturn",
    "n64": "pal-nintendo-64",
    "ps1": "pal-playstation",
    "dreamcast": "pal-sega-dreamcast",
}

PAGE_SIZE = 150

EXCLUDED_KEYWORDS = {
    "card", "cards", "trading", "tcg", "booster", "pokemon card",
    "magic", "yugioh", "yu-gi-oh", "figurine", "amiibo", "guide",
    "strategy guide", "manga", "comic", "soundtrack", "ost",
    # Accessoires / câbles / hardware
    "cable", "adapter", "controller", "pad", "rf modulator",
    "game genie", "game shark", "action replay", "gameshark",
    "cleaning kit", "converter", "memory card",
    # Consoles / systèmes (pas des jeux)
    "console", "system", "konsole",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def _parse_usd(text: str) -> float | None:
    if not text:
        return None
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def _is_excluded(title: str) -> bool:
    lower = title.lower()
    return any(kw in lower for kw in EXCLUDED_KEYWORDS)


def _fetch_page(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def scrape_console_catalog(
    platform_slug: str,
    delay: float = 1.5,
) -> Iterator[dict]:
    """Yield tous les jeux d'une console PAL depuis PriceCharting.

    Chaque item contient :
      - title: str
      - product_url: str (URL absolue PriceCharting)
      - product_id: str (data-product attribute)
      - platform_slug: str
      - pc_console_slug: str (ex: "pal-super-nintendo")
      - loose_price: float|None (USD)
      - cib_price: float|None (USD)
      - new_price: float|None (USD)
      - image_url: str
    """
    pc_slug = PAL_CONSOLES.get(platform_slug)
    if not pc_slug:
        logger.error("Platform slug '%s' not in PAL_CONSOLES", platform_slug)
        return

    cursor = 0
    page_num = 0

    while True:
        url = f"https://www.pricecharting.com/console/{pc_slug}"
        if cursor > 0:
            url += f"?cursor={cursor}"

        page_num += 1
        logger.info("Fetching %s page %d (cursor=%d)", pc_slug, page_num, cursor)

        try:
            soup = _fetch_page(url)
        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            break

        table = soup.select_one("table#games_table")
        if not table:
            logger.warning("No games_table found at %s", url)
            break

        rows = table.select("tr[data-product]")
        if not rows:
            break

        for row in rows:
            product_id = row.get("data-product", "")
            title_td = row.select_one("td.title a")
            if not title_td:
                continue

            title = title_td.get_text(strip=True)
            if _is_excluded(title):
                continue

            href = title_td.get("href", "")
            product_url = f"https://www.pricecharting.com{href}" if href.startswith("/") else href

            loose_el = row.select_one("td.used_price span.js-price")
            cib_el = row.select_one("td.cib_price span.js-price")
            new_el = row.select_one("td.new_price span.js-price")

            loose = _parse_usd(loose_el.get_text(strip=True)) if loose_el else None
            cib = _parse_usd(cib_el.get_text(strip=True)) if cib_el else None
            new = _parse_usd(new_el.get_text(strip=True)) if new_el else None

            img_el = row.select_one("td.image img")
            image_url = img_el.get("src", "") if img_el else ""

            yield {
                "title": title,
                "product_url": product_url,
                "product_id": product_id,
                "platform_slug": platform_slug,
                "pc_console_slug": pc_slug,
                "loose_price": loose,
                "cib_price": cib,
                "new_price": new,
                "image_url": image_url,
            }

        if len(rows) < PAGE_SIZE:
            break

        cursor += PAGE_SIZE
        time.sleep(delay)
