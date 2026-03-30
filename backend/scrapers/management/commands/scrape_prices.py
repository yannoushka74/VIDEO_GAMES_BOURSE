"""
Management command pour scraper les prix des jeux vidéo.
Usage:
  python manage.py scrape_prices                              # Amazon, 50 jeux sans prix
  python manage.py scrape_prices --source galaxus              # Galaxus
  python manage.py scrape_prices --source amazon,galaxus       # Les deux
  python manage.py scrape_prices --parallel 3                  # 3 navigateurs en parallèle
  python manage.py scrape_prices --limit 200                   # 200 jeux
  python manage.py scrape_prices --game "Zelda"                # un jeu spécifique
  python manage.py scrape_prices --platform ps5                # jeux PS5 uniquement
  python manage.py scrape_prices --all --parallel 4            # tout scraper, 4x plus vite
"""

import os
import signal
from datetime import timedelta

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from games.models import Game, Price

PLATFORM_ALIASES = {
    "ps5": "ps5", "ps4": "ps4", "ps3": "ps3",
    "switch": "switch", "switch2": "switch-2",
    "xbox": "xbox-series", "xboxone": "one",
    "pc": "pc", "3ds": "3ds", "vita": "vita",
    "wii": "wii", "wiiu": "wiiu", "steamdeck": "steam-deck",
}

SOURCE_CONFIG = {
    "amazon": {
        "label": "Amazon",
        "source": Price.Source.AMAZON,
        "currency": "EUR",
        "scraper_class": "scrapers.amazon.AmazonScraper",
    },
    "galaxus": {
        "label": "Galaxus",
        "source": Price.Source.GALAXUS,
        "currency": "CHF",
        "scraper_class": "scrapers.galaxus.GalaxusScraper",
    },
    "pricecharting": {
        "label": "PriceCharting",
        "source": Price.Source.PRICECHARTING,
        "currency": "USD",
        "scraper_class": "scrapers.pricecharting.PriceChartingScraper",
    },
    "ebay": {
        "label": "eBay",
        "source": Price.Source.EBAY,
        "currency": "EUR",
        "scraper_class": "scrapers.ebay.EbayScraper",
    },
}


def _load_scraper(class_path, delay, parallel=1):
    module_path, class_name = class_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(delay=delay, parallel=parallel)


class Command(BaseCommand):
    help = "Scrape les prix des jeux vidéo depuis Amazon et/ou Galaxus"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            type=str,
            default="amazon",
            help="Source(s) : amazon, galaxus, ou amazon,galaxus (défaut: amazon)",
        )
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--game", type=str, help="Recherche par titre")
        parser.add_argument("--platform", type=str, help="Filtrer par plateforme(s)")
        parser.add_argument("--refresh", action="store_true", help="Prix > 24h")
        parser.add_argument("--all", action="store_true", help="Tout scraper")
        parser.add_argument("--delay", type=float, default=3.0)
        parser.add_argument(
            "--parallel",
            type=int,
            default=1,
            help="Nombre de navigateurs en parallèle (défaut: 1, max recommandé: 5)",
        )

    def handle(self, *args, **options):
        sources = [s.strip().lower() for s in options["source"].split(",")]
        for s in sources:
            if s not in SOURCE_CONFIG:
                self.stdout.write(self.style.ERROR(f"Source inconnue: {s}. Choix: {', '.join(SOURCE_CONFIG)}"))
                return

        for source_name in sources:
            self._scrape_source(source_name, options)

    def _scrape_source(self, source_name, options):
        config = SOURCE_CONFIG[source_name]
        limit = options["limit"]
        delay = options["delay"]

        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(f"  Source : {config['label']} ({config['currency']})")
        self.stdout.write(f"{'='*50}\n")

        # Base queryset
        base_qs = Game.objects.all()

        if options["platform"]:
            slugs = [PLATFORM_ALIASES.get(p.strip().lower(), p.strip().lower()) for p in options["platform"].split(",")]
            base_qs = base_qs.filter(machines__slug__in=slugs).distinct()
            self.stdout.write(f"Plateforme(s) : {', '.join(slugs)} ({base_qs.count()} jeux)")

        # Sélection des jeux
        source_choice = config["source"]
        if options["game"]:
            games = list(base_qs.filter(title__icontains=options["game"]))
            self.stdout.write(f"Recherche : {len(games)} jeux pour '{options['game']}'")
        elif options["refresh"]:
            cutoff = timezone.now() - timedelta(hours=24)
            games = list(
                base_qs.filter(
                    Q(prices__isnull=True) | Q(prices__source=source_choice, prices__scraped_at__lt=cutoff)
                ).distinct()[:limit]
            )
            self.stdout.write(f"Refresh : {len(games)} jeux")
        elif options["all"]:
            # Jeux sans prix pour CETTE source
            games = list(
                base_qs.exclude(prices__source=source_choice)
            )
            self.stdout.write(f"Mode ALL : {len(games)} jeux sans prix {config['label']}")
            self.stdout.write("Ctrl+C pour arrêter proprement.\n")
        else:
            games = list(
                base_qs.exclude(prices__source=source_choice)[:limit]
            )
            self.stdout.write(f"Nouveaux : {len(games)} jeux sans prix {config['label']}")

        if not games:
            self.stdout.write(self.style.WARNING("Aucun jeu à scraper."))
            return

        total = len(games)
        parallel = options.get("parallel", 1)
        self.stdout.write(f"Lancement ({total} jeux, délai: {delay}s, parallel: {parallel})...\n")

        found = 0
        errors = 0

        def _save_price(game, result):
            Price.objects.create(
                game=game,
                source=source_choice,
                price=result["price"],
                old_price=result.get("old_price"),
                discount_percent=result.get("discount_percent"),
                currency=result.get("currency", config["currency"]),
                product_url=result.get("product_url", ""),
                product_title=result.get("product_title", ""),
                asin=result.get("asin", ""),
                image_url=result.get("image_url", ""),
                rating=result.get("rating"),
                review_count=result.get("review_count"),
                availability=result.get("availability", ""),
                category=result.get("category", ""),
                cib_price=result.get("cib_price"),
                new_price=result.get("new_price"),
                graded_price=result.get("graded_price"),
                box_only_price=result.get("box_only_price"),
                manual_only_price=result.get("manual_only_price"),
            )

        def _format_info(result):
            currency = result.get("currency", config["currency"])
            info = f'{result["price"]} {currency}'
            if result.get("cib_price"):
                info += f' | CIB: {result["cib_price"]} | Neuf: {result.get("new_price", "?")}'
            elif result.get("old_price"):
                info += f' (ancien: {result["old_price"]}, -{result.get("discount_percent", "?")}%)'
            if result.get("rating"):
                info += f' | {result["rating"]}/5'
            return info

        scraper = _load_scraper(config["scraper_class"], delay, parallel)

        if parallel > 1:
            self.stdout.write(f"  Scraping en batch avec {parallel} navigateurs...\n")
            title_to_game = {game.title: game for game in games}
            titles = [game.title for game in games]

            def _get_platform(game):
                """Retourne le slug de la première console rétro du jeu."""
                for m in game.machines.all():
                    if m.slug in PLATFORM_ALIASES.values() or m.slug in PLATFORM_ALIASES:
                        return m.slug
                return ""

            with scraper:
                results = scraper.search_prices_batch(titles)

            for title, result in zip(titles, results):
                game = title_to_game[title]
                if result:
                    _save_price(game, result)
                    self.stdout.write(
                        self.style.SUCCESS(f"  {game.title[:50]} → {_format_info(result)}")
                    )
                    found += 1
                else:
                    errors += 1
        else:
            stopped = False

            RETRO = {"neo", "nes", "snes", "gba", "saturn", "n64"}

            def _get_platform(game):
                for m in game.machines.all():
                    if m.slug in RETRO:
                        return m.slug
                return ""

            def signal_handler(sig, frame):
                nonlocal stopped
                stopped = True
                self.stdout.write(self.style.WARNING("\n\nArrêt demandé..."))

            signal.signal(signal.SIGINT, signal_handler)

            with scraper:
                for i, game in enumerate(games, 1):
                    if stopped:
                        break

                    platform_slug = _get_platform(game)
                    self.stdout.write(f"  [{i}/{total}] {game.title[:50]} ({platform_slug})...", ending=" ")
                    try:
                        result = scraper.search_price(game.title, platform_slug)
                    except TypeError:
                        result = scraper.search_price(game.title)

                    if result:
                        _save_price(game, result)
                        self.stdout.write(self.style.SUCCESS(_format_info(result)))
                        found += 1
                    else:
                        self.stdout.write(self.style.WARNING("non trouvé"))
                        errors += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{config['label']} : {found} prix trouvés, {errors} non trouvés."
            )
        )
