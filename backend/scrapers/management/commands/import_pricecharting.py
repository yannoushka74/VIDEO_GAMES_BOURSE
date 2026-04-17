"""Importe le catalogue PriceCharting PAL comme source primaire de jeux.

Scrape les pages catalogue PriceCharting par console PAL et crée/met à jour
les objets Game + Price en base. Chaque jeu est identifié par son
`pricecharting_url` (unique).

Usage :
    python manage.py import_pricecharting                      # toutes les consoles PAL
    python manage.py import_pricecharting --platform snes      # une seule
    python manage.py import_pricecharting --platform snes,nes  # plusieurs
    python manage.py import_pricecharting --dry-run            # preview
    python manage.py import_pricecharting --delay 2            # throttle (défaut 1.5s)
"""

from __future__ import annotations

import os
import signal

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand

from games.models import Game, Machine, Price
from scrapers.pricecharting_catalog import PAL_CONSOLES, scrape_console_catalog


class Command(BaseCommand):
    help = "Importe le catalogue PriceCharting PAL (crée/met à jour Game + Price)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--platform",
            type=str,
            default=",".join(PAL_CONSOLES.keys()),
            help="Console(s) à importer (défaut: toutes). Ex: snes,nes,n64",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--delay", type=float, default=1.5)

    def handle(self, *args, **opts):
        platforms = [p.strip() for p in opts["platform"].split(",") if p.strip()]
        dry = opts["dry_run"]
        delay = opts["delay"]

        stopped = False

        def signal_handler(sig, frame):
            nonlocal stopped
            stopped = True
            self.stdout.write(self.style.WARNING("\nArrêt demandé..."))

        signal.signal(signal.SIGINT, signal_handler)

        total_created = 0
        total_updated = 0
        total_prices = 0

        for platform in platforms:
            if platform not in PAL_CONSOLES:
                self.stdout.write(
                    self.style.ERROR(f"Platform '{platform}' inconnue. Choix: {list(PAL_CONSOLES.keys())}")
                )
                continue

            machine = Machine.objects.filter(slug=platform).first()
            if not machine:
                self.stdout.write(
                    self.style.WARNING(f"Machine slug='{platform}' absente en base, skip.")
                )
                continue

            self.stdout.write(f"\n{'='*50}")
            self.stdout.write(f"  {machine.name} ({platform}) — PriceCharting catalogue")
            self.stdout.write(f"{'='*50}")

            created = 0
            updated = 0
            prices_stored = 0

            for item in scrape_console_catalog(platform, delay=delay):
                if stopped:
                    break

                title = item["title"]
                pc_url = item["product_url"]
                loose = item["loose_price"]

                if dry:
                    status = "NEW" if not Game.objects.filter(pricecharting_url=pc_url).exists() else "UPD"
                    price_str = f"${loose}" if loose else "N/A"
                    self.stdout.write(f"  [{status}] {title[:60]} — {price_str}")
                    if status == "NEW":
                        created += 1
                    else:
                        updated += 1
                    continue

                game, was_created = Game.objects.update_or_create(
                    pricecharting_url=pc_url,
                    defaults={
                        "title": title,
                        "title_en": title,
                    },
                )
                game.machines.add(machine)

                if was_created:
                    created += 1
                else:
                    updated += 1

                if loose:
                    Price.objects.create(
                        game=game,
                        source="pricecharting",
                        price=loose,
                        cib_price=item["cib_price"],
                        new_price=item["new_price"],
                        currency="USD",
                        product_url=pc_url,
                        product_title=title,
                        image_url=item.get("image_url", ""),
                    )
                    prices_stored += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"  {machine.name}: {created} créés, {updated} mis à jour, "
                    f"{prices_stored} prix stockés"
                )
            )
            total_created += created
            total_updated += updated
            total_prices += prices_stored

            if stopped:
                break

        self.stdout.write(
            self.style.NOTICE(
                f"\nTotal: {total_created} jeux créés, {total_updated} mis à jour, "
                f"{total_prices} prix — {'DRY RUN' if dry else 'LIVE'}"
            )
        )
