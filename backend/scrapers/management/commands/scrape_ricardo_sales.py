"""Scrape les annonces Ricardo TERMINÉES pour construire une cote marché réelle.

Différence avec scrape_ricardo :
- Capture les listings avec badge "Vendu/Terminé"
- Les stocke dans SaleRecord (pas Listing)
- Permet d'agréger les prix de vente effectifs → cote réelle

Usage :
    python manage.py scrape_ricardo_sales
    python manage.py scrape_ricardo_sales --platform snes
    python manage.py scrape_ricardo_sales --parallel 4
"""

import os

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand

from games.models import Game, SaleRecord
from scrapers.matching import is_alien_platform_listing, is_likely_accessory, match_listing_title
from scrapers.ricardo import (
    CONSOLE_SEARCHES,
    _collect_listings_from_results,
)
from botasaurus.browser import browser, Driver


@browser(headless=True, reuse_driver=False, close_on_crash=True, output=None, parallel=4)
def _scrape_ended(driver: Driver, platform_slug: str):
    search_query = CONSOLE_SEARCHES.get(platform_slug)
    if not search_query:
        return []
    # Ricardo a un filtre "ended=true" dans l'URL ? Sinon on scrape tout
    # et on filtre côté code sur le flag 'ended'.
    search_url = f"https://www.ricardo.ch/fr/s/{search_query}"
    results = _collect_listings_from_results(driver, search_url, include_ended=True)
    # Ne garder que les ventes terminées
    ended_results = [r for r in results if r.get("ended")]
    for r in ended_results:
        r["platform_slug"] = platform_slug
    return ended_results


class Command(BaseCommand):
    help = "Scrape les annonces Ricardo TERMINÉES pour construire une cote marché réelle."

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, help="Console(s) séparées par virgule")
        parser.add_argument("--parallel", type=int, default=4)
        parser.add_argument("--threshold", type=int, default=75)

    def handle(self, *args, **options):
        if options["platform"]:
            platforms = [p.strip().lower() for p in options["platform"].split(",")]
        else:
            platforms = list(CONSOLE_SEARCHES.keys())

        self.stdout.write(f"\nScraping ventes terminées ({len(platforms)} consoles, parallel={options['parallel']})...\n")

        # Pré-charger les jeux par console
        games_by_platform = {}
        for p in platforms:
            games_by_platform[p] = list(Game.objects.filter(machines__slug=p).distinct())

        threshold = options["threshold"]
        total_saved = 0
        total_matched = 0

        for platform in platforms:
            self.stdout.write(f"\n=== {platform.upper()} ===")
            results = _scrape_ended(platform)
            if not results:
                self.stdout.write("  Aucune vente terminée trouvée")
                continue

            self.stdout.write(f"  {len(results)} ventes terminées détectées")
            candidate_games = games_by_platform.get(platform, [])

            for r in results:
                if is_likely_accessory(r["title"]):
                    continue
                if is_alien_platform_listing(r["title"], platform):
                    continue

                game, score = match_listing_title(r["title"], candidate_games, threshold=threshold)
                if game:
                    total_matched += 1

                # Dedup via UniqueConstraint (source, listing_url)
                _, created = SaleRecord.objects.get_or_create(
                    source="ricardo",
                    listing_url=r["listing_url"],
                    defaults={
                        "game": game,
                        "platform_slug": platform,
                        "final_price": r["current_price"],
                        "currency": "CHF",
                        "condition": r.get("condition", "loose"),
                        "region": r.get("region", "PAL"),
                        "listing_title": r["title"][:500],
                    },
                )
                if created:
                    total_saved += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nTerminé : {total_saved} nouvelles ventes enregistrées, "
                f"{total_matched} matchées à un jeu"
            )
        )
