"""Fusionne les entrées PAL et NTSC du même jeu PriceCharting.

Pour chaque paire de jeux qui partagent le même slug PC (ex: `secret-of-mana`)
sur la même console (ex: snes), garde l'entrée PAL comme primaire et transfère :
- Les prix de l'entrée NTSC vers PAL (en tagguant region='ntsc')
- Les listings de l'entrée NTSC vers PAL
- Les alertes de l'entrée NTSC vers PAL
Puis supprime l'entrée NTSC.

Aussi : backfill Price.region depuis product_url pour les prix existants.

Usage :
    python manage.py merge_pal_ntsc --dry-run
    python manage.py merge_pal_ntsc
"""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from games.models import Alert, Game, Listing, Price

# Mapping PC console slug → platform_slug interne
PC_TO_PLATFORM = {
    "pal-super-nintendo": "snes", "super-nintendo": "snes",
    "pal-nes": "nes", "nes": "nes",
    "pal-nintendo-64": "n64", "nintendo-64": "n64",
    "pal-gameboy-advance": "gba", "gameboy-advance": "gba",
    "pal-sega-saturn": "saturn", "sega-saturn": "saturn",
    "neo-geo-aes": "neo",
    "pal-playstation": "ps1", "playstation": "ps1",
    "pal-sega-dreamcast": "dreamcast", "sega-dreamcast": "dreamcast",
}

PAL_SLUGS = {
    "pal-super-nintendo", "pal-nes", "pal-nintendo-64",
    "pal-gameboy-advance", "pal-sega-saturn", "neo-geo-aes",
    "pal-playstation", "pal-sega-dreamcast",
}


def _parse_pc_url(url: str) -> tuple[str, str, str] | None:
    """Extrait (pc_console, game_slug, region) depuis une URL PriceCharting.

    Ex: https://www.pricecharting.com/game/pal-super-nintendo/secret-of-mana
        → ('pal-super-nintendo', 'secret-of-mana', 'pal')
    """
    if not url:
        return None
    m = re.search(r"/game/([^/]+)/([^/?]+)", url)
    if not m:
        return None
    pc_console, game_slug = m.group(1), m.group(2)
    region = "pal" if pc_console in PAL_SLUGS else "ntsc"
    return pc_console, game_slug, region


class Command(BaseCommand):
    help = "Fusionne les doublons PAL/NTSC du catalogue PriceCharting."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        # --- Étape 1 : backfill Price.region depuis product_url ---
        self.stdout.write("=== Étape 1 : backfill Price.region ===")
        prices_no_region = Price.objects.filter(region="", source="pricecharting").exclude(product_url="")
        total = prices_no_region.count()
        self.stdout.write(f"{total} prix PC sans region")

        if not dry:
            pal_count = 0
            ntsc_count = 0
            for p in prices_no_region.iterator():
                parsed = _parse_pc_url(p.product_url)
                if parsed:
                    _, _, region = parsed
                    p.region = region
                    p.save(update_fields=["region"])
                    if region == "pal":
                        pal_count += 1
                    else:
                        ntsc_count += 1
            self.stdout.write(f"  PAL: {pal_count}, NTSC: {ntsc_count}")
        else:
            self.stdout.write(f"  (dry-run, pas de changement)")

        # --- Étape 2 : trouver les paires PAL/NTSC à fusionner ---
        self.stdout.write("\n=== Étape 2 : recherche des doublons PAL/NTSC ===")

        # Grouper les jeux par (platform, game_slug)
        games_by_key = {}  # {(platform, slug): {"pal": game, "ntsc": game}}

        for g in Game.objects.exclude(pricecharting_url="").exclude(pricecharting_url__isnull=True):
            parsed = _parse_pc_url(g.pricecharting_url)
            if not parsed:
                continue
            pc_console, game_slug, region = parsed
            platform = PC_TO_PLATFORM.get(pc_console)
            if not platform:
                continue
            key = (platform, game_slug)
            games_by_key.setdefault(key, {})[region] = g

        pairs = [(k, v) for k, v in games_by_key.items() if "pal" in v and "ntsc" in v]
        self.stdout.write(f"{len(pairs)} paires PAL+NTSC trouvées")

        merged = 0
        total_prices_moved = 0
        total_listings_moved = 0
        total_alerts_moved = 0

        for key, pair in pairs:
            pal_game = pair["pal"]
            ntsc_game = pair["ntsc"]

            prices_count = ntsc_game.prices.count()
            listings_count = ntsc_game.listings.count()
            alerts_count = ntsc_game.alerts.count()

            if dry:
                self.stdout.write(
                    f"  MERGE {pal_game.title} ({key[0]}) | "
                    f"{prices_count}P {listings_count}L {alerts_count}A vers PAL"
                )
            else:
                with transaction.atomic():
                    # Prix : transférer + forcer region=ntsc
                    Price.objects.filter(game=ntsc_game).update(
                        game=pal_game, region="ntsc"
                    )
                    # Listings
                    Listing.objects.filter(game=ntsc_game).update(game=pal_game)
                    # Alerts
                    Alert.objects.filter(game=ntsc_game).update(game=pal_game)
                    # Transférer les machines M2M
                    for m in ntsc_game.machines.all():
                        pal_game.machines.add(m)
                    for genre in ntsc_game.genres.all():
                        pal_game.genres.add(genre)
                    # Supprimer le NTSC
                    ntsc_game.delete()

            merged += 1
            total_prices_moved += prices_count
            total_listings_moved += listings_count
            total_alerts_moved += alerts_count

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{merged} paires fusionnées — "
                f"{total_prices_moved}P {total_listings_moved}L {total_alerts_moved}A "
                f"transférés {'(DRY RUN)' if dry else ''}"
            )
        )

        # Stats finales
        total_games = Game.objects.count()
        self.stdout.write(f"\nTotal jeux restants : {total_games}")
