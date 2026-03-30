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
from django.utils import timezone

from games.models import Game, Listing
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
            deleted = Listing.objects.filter(source=Listing.Source.RICARDO).delete()
            self.stdout.write(f"Supprimé {deleted[0]} anciennes annonces Ricardo")

        total_found = 0

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

            # Mots trop courants à ignorer pour le matching
            STOP_WORDS = {
                "super", "nintendo", "snes", "nes", "n64", "game", "boy", "advance",
                "gba", "neo", "geo", "sega", "saturn", "jeu", "spiel", "für", "fuer",
                "famicom", "the", "of", "and", "de", "la", "le", "les", "du", "des",
                "a", "an", "in", "on", "for", "mit", "ovp", "pal", "ntsc", "japan",
                "usa", "eur", "komplett", "original", "top", "1", "2", "3", "4", "5",
                "ii", "iii", "iv", "v", "-", ":", "&",
            }

            # Pré-calculer les mots significatifs de chaque jeu
            platform_games = list(Game.objects.filter(machines__slug=platform).distinct())
            game_word_index = {}
            for g in platform_games:
                words = {w for w in g.title.lower().split() if w not in STOP_WORDS and len(w) > 2}
                game_word_index[g] = words

            for r in results:
                title_words = {w for w in r["title"].lower().split() if w not in STOP_WORDS and len(w) > 2}
                game = None
                best_score = 0

                for g, game_words in game_word_index.items():
                    if not game_words:
                        continue
                    common = title_words & game_words
                    # Score = proportion de mots du jeu trouvés dans l'annonce
                    score = len(common) / len(game_words) if game_words else 0
                    if score > best_score and len(common) >= 2:
                        best_score = score
                        game = g

                # Seuil minimum : au moins 50% des mots du jeu doivent matcher
                if best_score < 0.5:
                    game = None

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
                )

                matched = f" -> {game.title}" if game else ""
                self.stdout.write(
                    f"  CHF {r['current_price']:>8} | {r['bid_count']:>2} ench. | {r['title'][:45]}{matched}"
                )
                total_found += 1

        self.stdout.write(
            self.style.SUCCESS(f"\nTerminé ! {total_found} annonces importées.")
        )
