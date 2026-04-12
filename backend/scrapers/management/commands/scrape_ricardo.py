"""
Scrape les enchères Ricardo.ch pour les jeux rétro.
Usage:
  python manage.py scrape_ricardo                    # toutes les consoles
  python manage.py scrape_ricardo --platform snes    # SNES uniquement
  python manage.py scrape_ricardo --platform nes,n64 # NES + N64
"""

import os

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand

from games.models import Game, Listing
from scrapers.matching import match_listing_title
from scrapers.ricardo import scrape_ricardo_console, CONSOLE_SEARCHES


class Command(BaseCommand):
    help = "Scrape les enchères Ricardo.ch par console"

    def add_arguments(self, parser):
        parser.add_argument(
            "--platform",
            type=str,
            help=f"Console(s) : {', '.join(CONSOLE_SEARCHES.keys())} (séparées par virgule)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Supprimer les anciennes annonces Ricardo avant import",
        )

    def handle(self, *args, **options):
        if options["platform"]:
            platforms = [p.strip().lower() for p in options["platform"].split(",")]
        else:
            platforms = list(CONSOLE_SEARCHES.keys())

        if options["clear"]:
            # Ne supprime que les annonces des plateformes ciblées par ce run
            # (sinon un run multi-console séquentiel s'efface lui-même)
            deleted = Listing.objects.filter(
                source=Listing.Source.RICARDO,
                platform_slug__in=platforms,
            ).delete()
            self.stdout.write(
                f"Supprimé {deleted[0]} anciennes annonces Ricardo ({','.join(platforms)})"
            )

        total_found = 0
        total_matched = 0

        for platform in platforms:
            if platform not in CONSOLE_SEARCHES:
                self.stdout.write(self.style.WARNING(f"Plateforme inconnue: {platform}"))
                continue

            self.stdout.write(f"\n{'='*50}")
            self.stdout.write(f"  Ricardo - {platform.upper()}")
            self.stdout.write(f"{'='*50}\n")

            results = scrape_ricardo_console(platform)

            if not results:
                self.stdout.write(self.style.WARNING("  Aucune annonce trouvée"))
                continue

            # Pré-charger les jeux de la plateforme (filtre cheap)
            candidate_games = list(
                Game.objects.filter(machines__slug=platform).distinct()
            )

            for r in results:
                game, score = match_listing_title(r["title"], candidate_games)

                Listing.objects.create(
                    game=game,
                    source=Listing.Source.RICARDO,
                    platform_slug=platform,
                    title=r["title"],
                    listing_url=r["listing_url"],
                    image_url=r.get("image_url", ""),
                    current_price=r["current_price"],
                    buy_now_price=r.get("buy_now_price"),
                    currency="CHF",
                    bid_count=r.get("bid_count", 0),
                    ends_at=None,
                    region=r.get("region", "PAL"),
                    condition=r.get("condition", "loose"),
                )

                if game:
                    total_matched += 1
                    matched = f" -> {game.title} ({score})"
                else:
                    matched = ""
                self.stdout.write(
                    f"  CHF {r['current_price']:>8} | {r['bid_count']:>2} ench. | {r['title'][:45]}{matched}"
                )
                total_found += 1

        pct = (total_matched * 100 // total_found) if total_found else 0
        self.stdout.write(
            self.style.SUCCESS(
                f"\nTerminé ! {total_found} annonces importées, {total_matched} matchées ({pct}%)."
            )
        )
