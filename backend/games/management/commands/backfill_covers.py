"""Remplit Game.cover_url depuis les pages catalogue PriceCharting.

Re-scrape les pages catalogue pour récupérer les thumbnails et les stocker
comme cover_url sur les jeux qui n'en ont pas.

Usage :
    python manage.py backfill_covers                     # toutes les consoles
    python manage.py backfill_covers --platform snes     # une seule
    python manage.py backfill_covers --dry-run
"""

from __future__ import annotations

import os

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand

from games.models import Game
from scrapers.pricecharting_catalog import PAL_CONSOLES, scrape_console_catalog


class Command(BaseCommand):
    help = "Remplit Game.cover_url depuis les thumbnails PriceCharting."

    def add_arguments(self, parser):
        parser.add_argument(
            "--platform",
            type=str,
            default=",".join(PAL_CONSOLES.keys()),
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--delay", type=float, default=1.5)

    def handle(self, *args, **opts):
        platforms = [p.strip() for p in opts["platform"].split(",") if p.strip()]
        dry = opts["dry_run"]
        total_filled = 0

        for platform in platforms:
            if platform not in PAL_CONSOLES:
                continue

            self.stdout.write(f"\n  {platform}...")
            filled = 0

            for item in scrape_console_catalog(platform, delay=opts["delay"]):
                pc_url = item["product_url"]
                image_url = item.get("image_url", "")
                if not image_url:
                    continue

                updated = Game.objects.filter(
                    pricecharting_url=pc_url,
                    cover_url="",
                ).update(cover_url=image_url) if not dry else (
                    1 if Game.objects.filter(pricecharting_url=pc_url, cover_url="").exists() else 0
                )

                if updated:
                    filled += updated

            self.stdout.write(f"  {platform}: {filled} covers remplis")
            total_filled += filled

        self.stdout.write(
            self.style.SUCCESS(
                f"\nTotal: {total_filled} covers — {'DRY RUN' if dry else 'LIVE'}"
            )
        )
