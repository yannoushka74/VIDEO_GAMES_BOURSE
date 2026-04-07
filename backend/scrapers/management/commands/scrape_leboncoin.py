"""
Scrape les annonces LeBonCoin.fr pour les jeux rétro.
Utilise un profil Chrome persistant — le captcha n'apparaît qu'au premier lancement.

Usage:
  python manage.py scrape_leboncoin                      # toutes les consoles
  python manage.py scrape_leboncoin --platform snes      # SNES uniquement
  python manage.py scrape_leboncoin --platform nes,n64   # NES + N64
"""

import os

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand

from games.models import Game, Listing
from scrapers.leboncoin import scrape_leboncoin_console, CONSOLE_SEARCHES

RETRO_SLUGS = {"neo", "nes", "snes", "gba", "saturn", "n64"}

STOP_WORDS = {
    "super", "nintendo", "snes", "nes", "n64", "game", "boy", "advance",
    "gba", "neo", "geo", "sega", "saturn", "jeu", "jeux", "console",
    "the", "of", "and", "de", "la", "le", "les", "du", "des", "pour",
    "a", "an", "in", "on", "for", "avec", "lot", "pack", "complet",
    "pal", "ntsc", "fr", "fah", "bon", "etat", "très", "état",
    "1", "2", "3", "4", "5", "ii", "iii", "iv", "v", "-", ":", "&",
}


class Command(BaseCommand):
    help = "Scrape les annonces LeBonCoin.fr (profil persistant, captcha 1 seule fois)"

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, help=f"Console(s) : {', '.join(CONSOLE_SEARCHES.keys())}")
        parser.add_argument("--clear", action="store_true", help="Supprimer les anciennes annonces LeBonCoin")

    def handle(self, *args, **options):
        if options["platform"]:
            platforms = [p.strip().lower() for p in options["platform"].split(",")]
        else:
            platforms = list(CONSOLE_SEARCHES.keys())

        if options["clear"]:
            deleted = Listing.objects.filter(source="leboncoin").delete()
            self.stdout.write(f"Supprimé {deleted[0]} anciennes annonces LeBonCoin")

        self.stdout.write(self.style.WARNING(
            "\n  Si c'est le premier lancement, un captcha apparaîtra dans Chrome."
            "\n  Résolvez-le une fois — les prochains lancements seront automatiques.\n"
        ))

        # Pré-calculer les jeux par plateforme
        platform_games = {}
        for slug in platforms:
            games = list(Game.objects.filter(machines__slug=slug).distinct())
            game_index = {}
            for g in games:
                words = {w for w in g.title.lower().split() if w not in STOP_WORDS and len(w) > 2}
                game_index[g] = words
            platform_games[slug] = game_index

        total_found = 0

        for platform in platforms:
            if platform not in CONSOLE_SEARCHES:
                self.stdout.write(self.style.WARNING(f"Plateforme inconnue: {platform}"))
                continue

            self.stdout.write(f"\n{'='*50}")
            self.stdout.write(f"  LeBonCoin - {platform.upper()}")
            self.stdout.write(f"{'='*50}\n")

            results = scrape_leboncoin_console(platform)

            if not results:
                self.stdout.write(self.style.WARNING("  Aucune annonce trouvée"))
                continue

            game_index = platform_games.get(platform, {})

            for r in results:
                title_words = {w for w in r["title"].lower().split() if w not in STOP_WORDS and len(w) > 2}
                game = None
                best_score = 0

                for g, game_words in game_index.items():
                    if not game_words:
                        continue
                    common = title_words & game_words
                    score = len(common) / len(game_words) if game_words else 0
                    if score > best_score and len(common) >= 2:
                        best_score = score
                        game = g

                if best_score < 0.5:
                    game = None

                Listing.objects.create(
                    game=game,
                    source="leboncoin",
                    platform_slug=platform,
                    title=r["title"],
                    listing_url=r["listing_url"],
                    image_url=r.get("image_url", ""),
                    current_price=r["current_price"],
                    buy_now_price=r.get("buy_now_price"),
                    currency="EUR",
                    bid_count=0,
                    condition=r.get("condition", ""),
                )

                matched = f" -> {game.title}" if game else ""
                self.stdout.write(f"  {r['current_price']:>8}€ | {r['title'][:45]}{matched}")
                total_found += 1

        self.stdout.write(
            self.style.SUCCESS(f"\nTerminé ! {total_found} annonces LeBonCoin importées.")
        )
