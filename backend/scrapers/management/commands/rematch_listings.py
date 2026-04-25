"""
Re-applique le matching annonce → jeu sur les Listing existants
sans re-scraper les sources externes.

Usage:
  python manage.py rematch_listings                    # tous les listings
  python manage.py rematch_listings --source ricardo   # source spécifique
  python manage.py rematch_listings --platform snes    # console spécifique
  python manage.py rematch_listings --dry-run          # aperçu sans écrire
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from games.models import Game, Listing
from scrapers.matching import is_alien_platform_listing, is_likely_accessory, match_listing_title

PLATFORMS = ["snes", "nes", "n64", "gba", "saturn", "neo", "ps1", "dreamcast"]


class Command(BaseCommand):
    help = "Re-applique le matching annonce → jeu sur les Listings existants"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            type=str,
            default="ricardo",
            help="Source à retraiter (défaut: ricardo)",
        )
        parser.add_argument(
            "--platform",
            type=str,
            help="Limiter à une console (slug)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Afficher les changements sans les écrire en BDD",
        )
        parser.add_argument(
            "--threshold",
            type=int,
            default=70,
            help="Seuil de matching (défaut: 70)",
        )

    def handle(self, *args, **options):
        source = options["source"]
        platform = options["platform"]
        dry_run = options["dry_run"]
        threshold = options["threshold"]

        platforms = [platform] if platform else PLATFORMS

        # Pré-charger les jeux par plateforme (1 query par console)
        games_by_platform: dict[str, list[Game]] = {}
        for p in platforms:
            games_by_platform[p] = list(
                Game.objects.filter(machines__slug=p).distinct()
            )
            self.stdout.write(f"  {p}: {len(games_by_platform[p])} jeux candidats")

        # Stats
        before_matched = 0
        after_matched = 0
        kept_same = 0
        newly_matched = 0
        changed_match = 0
        lost_match = 0
        total = 0
        accessories = 0

        # Échantillons pour rapport
        samples_new: list[tuple[str, str, int]] = []
        samples_changed: list[tuple[str, str, str, int]] = []
        samples_lost: list[tuple[str, str]] = []

        listings_qs = Listing.objects.filter(source=source).select_related("game")
        if platform:
            listings_qs = listings_qs.filter(platform_slug=platform)

        # Update en bulk : on stocke les changements, on flush par batch
        updates_to_apply: list[tuple[int, int | None]] = []  # (listing_id, new_game_id)

        for listing in listings_qs.iterator():
            total += 1
            old_game_id = listing.game_id
            if old_game_id:
                before_matched += 1

            if is_likely_accessory(listing.title, listing.description or ""):
                accessories += 1
                # Forcer game=NULL pour les accessoires
                if old_game_id is not None:
                    updates_to_apply.append((listing.id, None))
                    lost_match += 1
                continue

            # Rejeter les listings d'une console différente
            if is_alien_platform_listing(listing.title, listing.platform_slug):
                if old_game_id is not None:
                    updates_to_apply.append((listing.id, None))
                    lost_match += 1
                continue

            candidates = games_by_platform.get(listing.platform_slug, [])
            new_game, score = match_listing_title(
                listing.title, candidates, threshold=threshold
            )
            new_game_id = new_game.id if new_game else None

            if new_game_id:
                after_matched += 1

            if new_game_id == old_game_id:
                if new_game_id is not None:
                    kept_same += 1
                continue

            # Changement
            if old_game_id is None and new_game_id is not None:
                newly_matched += 1
                if len(samples_new) < 10:
                    samples_new.append((listing.title, new_game.title, score))
            elif old_game_id is not None and new_game_id is None:
                lost_match += 1
                if len(samples_lost) < 10:
                    samples_lost.append((listing.title, listing.game.title))
            else:
                changed_match += 1
                if len(samples_changed) < 10:
                    samples_changed.append(
                        (listing.title, listing.game.title, new_game.title, score)
                    )

            updates_to_apply.append((listing.id, new_game_id))

        # Apply updates
        if not dry_run and updates_to_apply:
            with transaction.atomic():
                for listing_id, new_game_id in updates_to_apply:
                    Listing.objects.filter(pk=listing_id).update(game_id=new_game_id)
            self.stdout.write(
                self.style.SUCCESS(f"\n{len(updates_to_apply)} listings mis à jour.")
            )
        elif dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY-RUN : {len(updates_to_apply)} listings auraient été mis à jour."
                )
            )

        # Rapport
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("BILAN")
        self.stdout.write("=" * 60)
        before_pct = (before_matched * 100 // total) if total else 0
        after_pct = (after_matched * 100 // total) if total else 0
        # Recalcul du % en excluant les accessoires (ce qui est matchable réellement)
        matchable = total - accessories
        after_pct_matchable = (after_matched * 100 // matchable) if matchable else 0
        self.stdout.write(f"  Total listings    : {total}")
        self.stdout.write(f"  Accessoires/bundles : {accessories} (exclus du matching)")
        self.stdout.write(f"  Listings 'jeu'    : {matchable}")
        self.stdout.write(f"  Matchés AVANT     : {before_matched} ({before_pct}% du total)")
        self.stdout.write(f"  Matchés APRÈS     : {after_matched} ({after_pct}% du total, {after_pct_matchable}% des jeux matchables)")
        self.stdout.write(f"  Conservés         : {kept_same}")
        self.stdout.write(self.style.SUCCESS(f"  Nouveaux matchs   : {newly_matched}"))
        self.stdout.write(f"  Match changé      : {changed_match}")
        self.stdout.write(self.style.WARNING(f"  Match perdu       : {lost_match}"))
        self.stdout.write(f"  Δ                 : {after_matched - before_matched:+d}")

        if samples_new:
            self.stdout.write("\n--- Exemples de NOUVEAUX matchs ---")
            for title, game_title, score in samples_new:
                self.stdout.write(f"  [{score}] {title[:55]} -> {game_title}")
        if samples_changed:
            self.stdout.write("\n--- Exemples de matchs CHANGÉS ---")
            for title, old, new, score in samples_changed:
                self.stdout.write(f"  {title[:50]}")
                self.stdout.write(f"    {old} -> {new} ({score})")
        if samples_lost:
            self.stdout.write("\n--- Exemples de matchs PERDUS ---")
            for title, old in samples_lost:
                self.stdout.write(f"  {title[:55]} -X- {old}")
