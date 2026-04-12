"""
Scrape les annonces eBay en cours pour les jeux rétro et les stocke dans Listing.
Usage:
  python manage.py scrape_ebay_listings                          # toutes les consoles, 50 jeux
  python manage.py scrape_ebay_listings --platform snes          # SNES uniquement
  python manage.py scrape_ebay_listings --platform snes,nes      # SNES + NES
  python manage.py scrape_ebay_listings --all                    # tous les jeux
  python manage.py scrape_ebay_listings --game "Chrono Trigger"  # un jeu
"""

import os
import signal
import time

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand

from django.db.models import Exists, OuterRef, Q

from scrapers.ebay import EbayScraper, search_ebay, detect_region
from scrapers.matching import detect_condition, is_likely_accessory, match_listing_title
from games.models import Game, Listing, Price

RETRO_SLUGS = {"neo", "nes", "snes", "gba", "saturn", "n64", "ps1", "dreamcast"}


class Command(BaseCommand):
    help = "Scrape les annonces eBay en cours pour les jeux rétro"

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, help="Console(s) séparées par virgule")
        parser.add_argument("--game", type=str, help="Recherche par titre")
        parser.add_argument("--limit", type=int, default=50, help="Nombre de jeux (défaut: 50)")
        parser.add_argument("--all", action="store_true", help="Tous les jeux PAL-vérifiés")
        parser.add_argument("--clear", action="store_true", help="Supprimer les anciennes annonces eBay")
        parser.add_argument("--delay", type=float, default=0.5, help="Délai entre requêtes (défaut: 0.5)")
        parser.add_argument("--include-unverified", action="store_true", help="Inclure les jeux non PAL-vérifiés")

    def handle(self, *args, **options):
        # Déterminer les plateformes ciblées (pour le clear)
        if options["platform"]:
            target_slugs = [p.strip().lower() for p in options["platform"].split(",")]
        else:
            target_slugs = list(RETRO_SLUGS)

        if options["clear"]:
            deleted = Listing.objects.filter(
                source=Listing.Source.EBAY,
                platform_slug__in=target_slugs,
            ).delete()
            self.stdout.write(f"Supprimé {deleted[0]} anciennes annonces eBay ({','.join(target_slugs)})")

        # Charger le scraper (pour les clés .env)
        scraper = EbayScraper(delay=options["delay"])

        # Sélection des jeux — tous les jeux rétro (sous le quota eBay 5000/jour)
        base_qs = Game.objects.filter(machines__slug__in=RETRO_SLUGS).distinct()

        if options["platform"]:
            slugs = [p.strip().lower() for p in options["platform"].split(",")]
            base_qs = base_qs.filter(machines__slug__in=slugs).distinct()
            self.stdout.write(f"Plateforme(s) : {', '.join(slugs)} ({base_qs.count()} jeux)")

        if options["game"]:
            games = list(base_qs.filter(title__icontains=options["game"]))
            self.stdout.write(f"Recherche : {len(games)} jeux pour '{options['game']}'")
        elif options["all"]:
            games = list(base_qs)
            self.stdout.write(f"Mode ALL : {len(games)} jeux")
        else:
            games = list(base_qs[:options["limit"]])
            self.stdout.write(f"Jeux : {len(games)}")

        if not games:
            self.stdout.write(self.style.WARNING("Aucun jeu."))
            return

        total = len(games)
        delay = options["delay"]
        total_listings = 0
        stopped = False

        def signal_handler(sig, frame):
            nonlocal stopped
            stopped = True
            self.stdout.write(self.style.WARNING("\n\nArrêt demandé..."))

        signal.signal(signal.SIGINT, signal_handler)

        self.stdout.write(f"\nScraping eBay ({total} jeux, délai: {delay}s)...\n")

        for i, game in enumerate(games, 1):
            if stopped:
                break

            # Trouver la console du jeu
            platform_slug = ""
            for m in game.machines.all():
                if m.slug in RETRO_SLUGS:
                    platform_slug = m.slug
                    break

            # Préférer title_en si dispo (meilleur match sur eBay FR)
            search_title = game.title_en or game.title
            self.stdout.write(f"  [{i}/{total}] {search_title[:50]} ({platform_slug})...", ending=" ")

            time.sleep(delay)
            items = search_ebay(search_title, platform_slug, limit=10, pal_only=False)

            if not items:
                self.stdout.write(self.style.WARNING("0 annonces"))
                continue

            count = 0
            skipped = 0
            for item in items:
                # Filtrer accessoires, notices, publicités
                if is_likely_accessory(item["title"]):
                    skipped += 1
                    continue
                # Vérifier que le titre eBay correspond bien au jeu recherché
                # (eBay retourne parfois des résultats sponsorisés hors sujet)
                matched, score = match_listing_title(item["title"], [game], threshold=60)
                if not matched:
                    skipped += 1
                    continue
                region = detect_region(item["title"])
                condition = detect_condition(item["title"], item.get("condition", ""))
                # Éviter les doublons (même URL)
                if Listing.objects.filter(source=Listing.Source.EBAY, listing_url=item["listing_url"]).exists():
                    continue
                Listing.objects.create(
                    game=game,
                    source=Listing.Source.EBAY,
                    platform_slug=platform_slug,
                    title=item["title"],
                    listing_url=item["listing_url"],
                    image_url=item.get("image_url", ""),
                    current_price=item["price"],
                    buy_now_price=None,
                    currency=item["currency"],
                    bid_count=item.get("bid_count", 0),
                    condition=condition,
                    region=region,
                )
                count += 1

            regions = [detect_region(i["title"]) for i in items]
            pal = regions.count("PAL")
            ntsc = regions.count("NTSC")
            jp = regions.count("JP")
            self.stdout.write(self.style.SUCCESS(
                f"{count} annonces (PAL:{pal} NTSC:{ntsc} JP:{jp})"
            ))
            total_listings += count

        self.stdout.write(
            self.style.SUCCESS(f"\nTerminé ! {total_listings} annonces eBay importées.")
        )
