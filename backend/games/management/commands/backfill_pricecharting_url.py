"""Remplit Game.pricecharting_url depuis les Price.product_url existantes.

Pour les jeux déjà en base (importés via JVC) qui ont une cote PriceCharting,
copie le product_url de la Price la plus récente vers Game.pricecharting_url.

Usage :
    python manage.py backfill_pricecharting_url             # apply
    python manage.py backfill_pricecharting_url --dry-run    # preview
"""

from django.core.management.base import BaseCommand
from django.db.models import Subquery, OuterRef

from games.models import Game, Price


class Command(BaseCommand):
    help = "Remplit Game.pricecharting_url depuis Price.product_url existantes."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        games_without_pc_url = Game.objects.filter(
            pricecharting_url__isnull=True,
            prices__source="pricecharting",
            prices__product_url__gt="",
        ).distinct()

        total = games_without_pc_url.count()
        self.stdout.write(f"{total} jeux avec cote PC mais sans pricecharting_url")

        filled = 0
        skipped = 0

        for game in games_without_pc_url.iterator():
            latest_price = (
                Price.objects.filter(
                    game=game,
                    source="pricecharting",
                    product_url__gt="",
                )
                .order_by("-scraped_at")
                .values_list("product_url", flat=True)
                .first()
            )

            if not latest_price:
                skipped += 1
                continue

            if Game.objects.filter(pricecharting_url=latest_price).exclude(pk=game.pk).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"  CONFLIT: {game.title} → {latest_price} (déjà pris par un autre jeu)"
                    )
                )
                skipped += 1
                continue

            if dry:
                self.stdout.write(f"  {game.title[:60]} → {latest_price}")
            else:
                game.pricecharting_url = latest_price
                game.save(update_fields=["pricecharting_url"])

            filled += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{filled} jeux remplis, {skipped} ignorés — {'DRY RUN' if dry else 'LIVE'}"
            )
        )
