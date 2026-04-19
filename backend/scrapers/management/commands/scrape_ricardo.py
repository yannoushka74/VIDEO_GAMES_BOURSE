"""
Scrape les enchères Ricardo.ch pour les jeux rétro.
Usage:
  python manage.py scrape_ricardo                       # toutes les consoles (parallèle)
  python manage.py scrape_ricardo --platform snes       # SNES uniquement
  python manage.py scrape_ricardo --platform nes,n64    # NES + N64
  python manage.py scrape_ricardo --parallel 4          # 4 navigateurs (défaut)
  python manage.py scrape_ricardo --no-parallel         # séquentiel
"""

import os

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand

from games.models import Game, Listing
from scrapers.matching import is_alien_platform_listing, is_likely_accessory, match_listing_title
from scrapers.ricardo import scrape_ricardo_console, scrape_ricardo_all_parallel, CONSOLE_SEARCHES


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
        parser.add_argument(
            "--parallel",
            type=int,
            default=4,
            help="Nombre de navigateurs en parallèle (défaut: 4)",
        )
        parser.add_argument(
            "--no-parallel",
            action="store_true",
            help="Forcer le mode séquentiel",
        )
        parser.add_argument(
            "--threshold",
            type=int,
            default=80,
            help="Seuil de matching (défaut: 80)",
        )

    def handle(self, *args, **options):
        if options["platform"]:
            platforms = [p.strip().lower() for p in options["platform"].split(",")]
        else:
            platforms = list(CONSOLE_SEARCHES.keys())

        if options["clear"]:
            deleted = Listing.objects.filter(
                source=Listing.Source.RICARDO,
                platform_slug__in=platforms,
            ).delete()
            self.stdout.write(
                f"Supprimé {deleted[0]} anciennes annonces Ricardo ({','.join(platforms)})"
            )

        threshold = options["threshold"]
        use_parallel = not options["no_parallel"] and len(platforms) > 1

        # Pré-charger les jeux par plateforme
        games_by_platform = {}
        for p in platforms:
            if p in CONSOLE_SEARCHES:
                games_by_platform[p] = list(
                    Game.objects.filter(machines__slug=p).distinct()
                )

        # Scraping
        if use_parallel:
            parallel = min(options["parallel"], len(platforms))
            self.stdout.write(f"\nScraping Ricardo en parallèle ({parallel} navigateurs, {len(platforms)} consoles)...\n")
            results_by_platform = scrape_ricardo_all_parallel(platforms, parallel=parallel)
        else:
            self.stdout.write(f"\nScraping Ricardo séquentiel ({len(platforms)} consoles)...\n")
            results_by_platform = {}
            for platform in platforms:
                if platform not in CONSOLE_SEARCHES:
                    self.stdout.write(self.style.WARNING(f"Plateforme inconnue: {platform}"))
                    continue
                results_by_platform[platform] = scrape_ricardo_console(platform) or []

        # Matching + insertion
        total_found = 0
        total_matched = 0

        for platform in platforms:
            results = results_by_platform.get(platform, [])
            self.stdout.write(f"\n{'='*50}")
            self.stdout.write(f"  Ricardo - {platform.upper()} ({len(results)} annonces)")
            self.stdout.write(f"{'='*50}\n")

            if not results:
                self.stdout.write(self.style.WARNING("  Aucune annonce trouvée"))
                continue

            candidate_games = games_by_platform.get(platform, [])

            for r in results:
                # Filtres
                if is_likely_accessory(r["title"]):
                    continue
                if is_alien_platform_listing(r["title"], platform):
                    continue

                game, score = match_listing_title(
                    r["title"], candidate_games, threshold=threshold
                )

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
