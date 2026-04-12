"""
Scraper Ricardo.ch pour les enchères de jeux rétro.

Stratégie :
- `driver.google_get` pour bypasser Cloudflare sur la page de résultats.
- Extraction directe depuis la liste (pas de visite page détail → Cloudflare bloque
  les navigations internes via `driver.get`).
- URL de recherche encodée avec %20 (Ricardo traite `+` comme caractère littéral).
- Filtrage PAL strict sur le titre : rejette JP/Japan/Famicom/US/USA/NTSC.
- Titre lu depuis l'attribut `alt` de l'image, sinon fallback slug URL.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import unquote

from botasaurus.browser import browser, Driver
from botasaurus.soupify import soupify
from scrapers.matching import detect_condition

logger = logging.getLogger(__name__)

# Recherches Ricardo par plateforme (espaces URL-encodés %20, PAS +)
CONSOLE_SEARCHES = {
    "snes": "super%20nintendo%20jeu",
    "nes": "nintendo%20nes%20jeu",
    "n64": "nintendo%2064%20jeu",
    "neo": "neo%20geo%20jeu",
    "gba": "game%20boy%20advance%20jeu",
    "saturn": "sega%20saturn%20jeu",
    "ps1": "playstation%20jeu",
    "dreamcast": "dreamcast%20jeu",
}

# Filtre PAL Europe : rejette tout titre mentionnant JP/Japan/Famicom/US/USA/NTSC.
NON_PAL_TOKEN_RE = re.compile(
    r"\b("
    r"ntsc|ntscu|ntscj|"
    r"jp|jap|japan|japon|japonais|japonaise|japanese|"
    r"famicom|"
    r"us|usa|american|americain|américain|"
    r"asia|asian|asiatique|chinese|korean|coréen|coreen"
    r")\b",
    re.IGNORECASE,
)
NON_PAL_PHRASES = (
    "super famicom",
    "import us", "import usa", "import japan", "import jp",
    "version us", "version usa", "version japan", "version jp",
    "us version", "usa version", "japan version", "japanese version",
)

# Badges / alt d'images à ignorer (ne sont pas des titres)
BADGE_ALTS = {"boost", "highlight", "premium", "top", ""}


def _is_non_pal(title: str) -> bool:
    """True si le titre indique explicitement un import non-PAL (JP/US)."""
    low = title.lower()
    if any(p in low for p in NON_PAL_PHRASES):
        return True
    if NON_PAL_TOKEN_RE.search(low):
        return True
    return False


def detect_region(title: str) -> str:
    """Détecte la région à partir du titre (PAL/NTSC/JP/unknown)."""
    low = title.lower()
    # JP / Famicom
    if any(p in low for p in ("super famicom", "famicom")):
        return "JP"
    if NON_PAL_TOKEN_RE.search(low):
        # Distinguer JP vs NTSC-US
        jp_words = {"jp", "jap", "japan", "japon", "japonais", "japonaise", "japanese"}
        for w in jp_words:
            if re.search(rf"\b{w}\b", low):
                return "JP"
        return "NTSC"
    # PAL explicite
    if re.search(r"\bpal\b|\beur\b|\beurope\b|\beuropean\b", low):
        return "PAL"
    # Ricardo est suisse → PAL par défaut si pas d'indication contraire
    return "PAL"


def _title_from_slug(href: str) -> str:
    """Extrait un titre lisible du slug d'URL /fr/a/{slug}-{id}/."""
    m = re.search(r"/fr/a/(.+?)-?\d+/?$", href)
    if not m:
        return ""
    slug = m.group(1)
    # URL-decode (emojis, accents encodés)
    try:
        slug = unquote(slug)
    except Exception:
        pass
    # Remplacer tirets par espaces, virer emojis / caractères non-ASCII restants
    title = slug.replace("-", " ")
    # Supprimer emojis et caractères spéciaux (garder lettres/chiffres/espaces/ponctuation de base)
    title = re.sub(r"[^\w\s\-'.:&+()]", " ", title, flags=re.UNICODE)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _extract_listing_from_card(link_el) -> dict | None:
    """Extrait une annonce depuis son élément <a> de la liste de résultats."""
    href = link_el.get("href", "")
    if not href or "/fr/a/" not in href:
        return None

    # Normaliser URL
    listing_url = href.split("?")[0]
    if listing_url.startswith("/"):
        listing_url = f"https://www.ricardo.ch{listing_url}"

    # Titre : source unique = slug URL (déterministe, les alt img sont des badges)
    title = _title_from_slug(href)
    if not title:
        return None

    # Détection de région (PAL/NTSC/JP) — on ne rejette plus, on tag
    region = detect_region(title)

    # Image : prendre la première img non-badge
    image_url = ""
    for img in link_el.select("img"):
        alt = (img.get("alt") or "").strip().lower()
        if alt in BADGE_ALTS:
            continue
        src = img.get("src") or img.get("data-src") or ""
        if src and src.startswith("http"):
            image_url = src
            break

    # Texte du link : contient "titre prix (N enchère) prix_achat_direct date"
    text = link_el.get_text(" ", strip=True)
    # Enlever le titre du début pour parser les prix
    prices = re.findall(r"(\d+[.,]?\d*)\s*(?=\(|Achat|enchère|$)", text)
    # Fallback plus simple : tous les nombres décimaux
    all_numbers = [float(x.replace(",", ".").replace("'", "")) for x in re.findall(r"\b(\d+(?:[.,]\d{1,2})?)\b", text)]

    # Nombre d'enchères
    bid_match = re.search(r"\((\d+)\s*enchère", text, re.IGNORECASE)
    bid_count = int(bid_match.group(1)) if bid_match else 0

    # Prix courant et achat direct
    current_price = None
    buy_now_price = None

    # Pattern: "300.00 (0 enchère) 350.00 Achat direct"
    m1 = re.search(r"(\d+[.,]?\d*)\s*\(\d+\s*enchère", text, re.IGNORECASE)
    if m1:
        try:
            current_price = float(m1.group(1).replace(",", "."))
        except ValueError:
            pass
    m2 = re.search(r"(\d+[.,]?\d*)\s*Achat\s*direct", text, re.IGNORECASE)
    if m2:
        try:
            buy_now_price = float(m2.group(1).replace(",", "."))
        except ValueError:
            pass

    # Si pas d'enchère trouvée, prix = premier grand nombre (achat direct simple)
    if current_price is None and buy_now_price is not None:
        current_price = buy_now_price
    if current_price is None and all_numbers:
        # Filtrer les petits nombres (IDs, quantités)
        big = [n for n in all_numbers if n >= 5]
        if big:
            current_price = big[0]

    if current_price is None:
        return None

    return {
        "title": title,
        "listing_url": listing_url,
        "image_url": image_url,
        "current_price": current_price,
        "buy_now_price": buy_now_price,
        "bid_count": bid_count,
        "region": region,
        "condition": detect_condition(title),
    }


MAX_PAGES = 20  # garde-fou


def _collect_listings_from_results(driver: Driver, search_url: str) -> list[dict]:
    """Itère sur ?page=N jusqu'à épuisement des résultats."""
    all_results: list[dict] = []
    seen_urls: set[str] = set()

    for page in range(1, MAX_PAGES + 1):
        page_url = search_url if page == 1 else f"{search_url}?page={page}"
        driver.google_get(page_url)
        driver.short_random_sleep()
        driver.sleep(6)

        soup = soupify(driver.page_html)
        page_links = {a.get("href", "").split("?")[0] for a in soup.select('a[href*="/fr/a/"]')}

        # Stop si page vide
        if not page_links:
            logger.info("Ricardo page %d: vide, arrêt pagination", page)
            break

        # Stop si toutes les URLs sont déjà vues (page identique → fin)
        new_links = page_links - seen_urls
        if not new_links:
            logger.info("Ricardo page %d: aucun nouveau lien, arrêt pagination", page)
            break

        page_count = 0
        for link in soup.select('a[href*="/fr/a/"]'):
            href = link.get("href", "").split("?")[0]
            if href in seen_urls:
                continue
            seen_urls.add(href)
            listing = _extract_listing_from_card(link)
            if listing:
                all_results.append(listing)
                page_count += 1

        logger.info(
            "Ricardo page %d: %d nouvelles annonces PAL (total: %d)",
            page, page_count, len(all_results),
        )

    return all_results


@browser(headless=True, reuse_driver=True, close_on_crash=True, output=None)
def scrape_ricardo_console(driver: Driver, platform_slug: str):
    """Scrape toutes les annonces Ricardo pour une console (toutes pages)."""
    search_query = CONSOLE_SEARCHES.get(platform_slug)
    if not search_query:
        return []

    search_url = f"https://www.ricardo.ch/fr/s/{search_query}"
    results = _collect_listings_from_results(driver, search_url)
    logger.info("Ricardo %s: %d annonces PAL totales", platform_slug, len(results))

    # Ajout du platform_slug sur chaque annonce
    for r in results:
        r["platform_slug"] = platform_slug

    return results


# --- Recherche ciblée par titre de jeu ---

# Mots-clés console à ajouter à la query pour cibler la bonne plateforme
PLATFORM_KEYWORDS = {
    "snes": "snes",
    "nes": "nes",
    "n64": "n64",
    "gba": "gba",
    "saturn": "saturn",
    "neo": "neogeo",
    "ps1": "playstation",
    "dreamcast": "dreamcast",
}


def _build_targeted_url(game_title: str, platform_slug: str) -> str:
    """Construit l'URL de recherche ciblée pour un jeu donné."""
    # Nettoyer le titre : retirer ponctuation, sous-titres après ":"
    clean = re.sub(r"[!?'’`]", "", game_title)
    if ":" in clean:
        clean = clean.split(":", 1)[0].strip()
    # Espaces → %20
    clean = re.sub(r"\s+", " ", clean).strip()
    encoded = clean.replace(" ", "%20")
    keyword = PLATFORM_KEYWORDS.get(platform_slug, "")
    if keyword:
        encoded = f"{encoded}%20{keyword}"
    return f"https://www.ricardo.ch/fr/s/{encoded}"


def _scrape_first_page_for_targeted(driver: Driver, search_url: str) -> list[dict]:
    """Pour une recherche ciblée, on scrape uniquement la première page (résultats les plus pertinents)."""
    driver.google_get(search_url)
    driver.short_random_sleep()
    driver.sleep(5)

    soup = soupify(driver.page_html)
    results = []
    seen = set()
    for link in soup.select('a[href*="/fr/a/"]'):
        href = link.get("href", "").split("?")[0]
        if href in seen:
            continue
        seen.add(href)
        listing = _extract_listing_from_card(link)
        if listing:
            results.append(listing)
    return results


@browser(headless=True, reuse_driver=True, close_on_crash=True, output=None)
def scrape_ricardo_for_games(driver: Driver, spec: dict):
    """Recherche Ricardo ciblée pour UN jeu (botasaurus appelle 1 fois par item).

    `spec` : dict {game_id, title, platform_slug}
    Retourne : dict {game_id, platform_slug, search_url, listings}
    """
    url = _build_targeted_url(spec["title"], spec["platform_slug"])
    try:
        listings = _scrape_first_page_for_targeted(driver, url)
    except Exception as e:
        logger.warning("Ricardo targeted '%s' (%s): %s", spec["title"], spec["platform_slug"], e)
        listings = []
    for l in listings:
        l["platform_slug"] = spec["platform_slug"]
    return {
        "game_id": spec["game_id"],
        "title": spec["title"],
        "platform_slug": spec["platform_slug"],
        "search_url": url,
        "listings": listings,
    }
