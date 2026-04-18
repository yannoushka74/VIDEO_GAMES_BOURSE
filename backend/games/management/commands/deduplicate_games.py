"""Fusionne les jeux legacy JVC avec les jeux PriceCharting importés.

Pour chaque jeu JVC qui a un doublon PC (même pricecharting_url via Price.product_url),
transfère les Listings, Alerts et AlertNotifications vers le jeu PC, puis supprime le
jeu JVC.

Usage :
    python manage.py deduplicate_games --dry-run     # preview
    python manage.py deduplicate_games               # apply
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from games.models import Alert, AlertNotification, Game, Listing, Price


class Command(BaseCommand):
    help = "Fusionne les jeux legacy JVC vers les jeux PriceCharting importés."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        # Jeux PC = ceux avec pricecharting_url rempli
        pc_games_by_url = {}
        for g in Game.objects.filter(pricecharting_url__isnull=False):
            pc_games_by_url[g.pricecharting_url] = g

        # Jeux legacy = ceux SANS pricecharting_url
        legacy_games = Game.objects.filter(pricecharting_url__isnull=True)

        merged = 0
        orphans = 0
        skipped = 0

        for old_game in legacy_games.iterator():
            # Trouver le product_url PC le plus récent pour ce jeu
            pc_url = (
                Price.objects.filter(
                    game=old_game,
                    source="pricecharting",
                    product_url__gt="",
                )
                .order_by("-scraped_at")
                .values_list("product_url", flat=True)
                .first()
            )

            if not pc_url:
                orphans += 1
                continue

            new_game = pc_games_by_url.get(pc_url)
            if not new_game:
                skipped += 1
                continue

            if new_game.id == old_game.id:
                skipped += 1
                continue

            listings_count = Listing.objects.filter(game=old_game).count()
            alerts_count = Alert.objects.filter(game=old_game).count()
            prices_count = Price.objects.filter(game=old_game).count()

            if dry:
                self.stdout.write(
                    f"  MERGE: {old_game.title[:50]} (id={old_game.id}) "
                    f"→ {new_game.title[:50]} (id={new_game.id}) "
                    f"[{listings_count}L {alerts_count}A {prices_count}P]"
                )
            else:
                # Transférer les listings
                Listing.objects.filter(game=old_game).update(game=new_game)

                # Transférer les alertes
                Alert.objects.filter(game=old_game).update(game=new_game)

                # Transférer les prix historiques (pour conserver l'historique)
                Price.objects.filter(game=old_game).update(game=new_game)

                # Supprimer l'ancien jeu (cascades genres/machines M2M)
                old_game.delete()

            merged += 1

        # Compter les orphelins restants (legacy sans cote PC ni doublon)
        remaining_legacy = Game.objects.filter(pricecharting_url__isnull=True).count()

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{merged} jeux fusionnés, {orphans} orphelins (pas de cote PC), "
                f"{skipped} ignorés — {'DRY RUN' if dry else 'LIVE'}"
            )
        )
        self.stdout.write(f"Jeux legacy restants en base: {remaining_legacy}")
