"""
Recherche Ricardo CIBLÉE par jeu : pour chaque jeu PAL-vérifié sans annonce
Ricardo, on lance une recherche dédiée sur ricardo.ch avec le titre du jeu.

Usage:
  python manage.py scrape_ricardo_targeted                       # tous les jeux PAL sans listing
  python manage.py scrape_ricardo_targeted --limit 10            # prototype
  python manage.py scrape_ricardo_targeted --platform snes       # une console
  python manage.py scrape_ricardo_targeted --threshold 75        # seuil matching plus strict
"""

import os

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef, Q

from games.models import Game, Listing, Price
from scrapers.matching import (
    has_game_indicator,
    is_alien_platform_listing,
    is_likely_accessory,
    match_listing_title,
)
from scrapers.ricardo import scrape_ricardo_for_games

RETRO_SLUGS = ["snes", "nes", "n64", "gba", "saturn", "neo", "ps1", "dreamcast"]


class Command(BaseCommand):
    help = "Recherche Ricardo ciblée par jeu (pour combler les jeux PAL sans annonces)"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Limite nb de jeux")
        parser.add_argument("--platform", type=str, help="Console (slug)")
        parser.add_argument("--threshold", type=int, default=75, help="Seuil matching (recherche ciblée → plus strict)")
        parser.add_argument("--dry-run", action="store_true", help="N'écrit pas en BDD")

    def handle(self, *args, **options):
        # Sélection : jeux PAL-vérifiés (pal_status='pal' OR has PriceCharting price)
        # ET sans aucune annonce Ricardo actuellement.
        has_pc = Exists(Price.objects.filter(game=OuterRef("pk"), source="pricecharting"))
        has_ricardo = Exists(Listing.objects.filter(game=OuterRef("pk"), source="ricardo"))

        qs = Game.objects.filter(machines__slug__in=RETRO_SLUGS).distinct()
        if options["platform"]:
            qs = qs.filter(machines__slug=options["platform"])
        qs = qs.annotate(has_pc=has_pc, has_ricardo=has_ricardo)
        qs = qs.filter(Q(pal_status="pal") | Q(has_pc=True))
        qs = qs.filter(has_ricardo=False)

        if options["limit"]:
            qs = qs[: options["limit"]]

        # Construire la liste game_specs : (game_id, title, platform_slug)
        # Pour chaque jeu, on prend la console rétro (s'il en a plusieurs, on prend la 1ère)
        game_specs = []
        game_obj_by_id = {}
        for g in qs.prefetch_related("machines"):
            for m in g.machines.all():
                if m.slug in RETRO_SLUGS:
                    game_specs.append(
                        {
                            "game_id": g.id,
                            "title": g.title_en or g.title,
                            "platform_slug": m.slug,
                        }
                    )
                    game_obj_by_id[g.id] = g
                    break

        total = len(game_specs)
        self.stdout.write(f"Cibles : {total} jeux PAL sans annonce Ricardo")
        if not total:
            return

        # Botasaurus reuse_driver=True : on passe la liste, il itère 1 par 1
        # avec le même Chrome.
        self.stdout.write(f"\n>> Lancement scraping ciblé sur {total} jeux...")
        all_outputs = scrape_ricardo_for_games(game_specs)
        # Si un seul item est passé, botasaurus retourne dict direct (pas liste)
        if isinstance(all_outputs, dict):
            all_outputs = [all_outputs]

        # Persistance + matching de vérification
        threshold = options["threshold"]
        dry_run = options["dry_run"]
        created = 0
        skipped_acc = 0
        skipped_alien = 0
        skipped_no_indicator = 0
        rejected_match = 0
        no_results = 0
        games_with_new_listings = set()

        for out in all_outputs:
            game_id = out["game_id"]
            game = game_obj_by_id.get(game_id)
            platform = out["platform_slug"]
            listings = out["listings"]

            if not listings:
                no_results += 1
                continue

            for r in listings:
                # Vérifier accessoire (DVD, console, manette...)
                if is_likely_accessory(r["title"]):
                    skipped_acc += 1
                    continue
                # Vérifier console étrangère (PS2/Xbox/Wii/...)
                if is_alien_platform_listing(r["title"], platform):
                    skipped_alien += 1
                    continue
                # Vérifier qu'il y a un indicateur "jeu vidéo" (sinon livre/film)
                if not has_game_indicator(r["title"], platform):
                    skipped_no_indicator += 1
                    continue
                # Vérifier matching avec ce game spécifique uniquement
                matched, score = match_listing_title(r["title"], [game], threshold=threshold)
                if not matched:
                    rejected_match += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"  [DRY] {game.title[:30]:30s} <- {r['title'][:55]} ({score})"
                    )
                else:
                    # Eviter les doublons (même listing_url)
                    if Listing.objects.filter(source="ricardo", listing_url=r["listing_url"]).exists():
                        continue
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
                        region=r.get("region", "PAL"),
                    )
                created += 1
                games_with_new_listings.add(game_id)

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("BILAN")
        self.stdout.write("=" * 60)
        self.stdout.write(f"  Jeux ciblés       : {total}")
        self.stdout.write(f"  Jeux sans résultat : {no_results}")
        self.stdout.write(f"  Annonces accessoires/DVD (skipped) : {skipped_acc}")
        self.stdout.write(f"  Annonces console étrangère (skipped) : {skipped_alien}")
        self.stdout.write(f"  Annonces sans indicateur jeu (skipped) : {skipped_no_indicator}")
        self.stdout.write(f"  Annonces rejetées par matching : {rejected_match}")
        self.stdout.write(self.style.SUCCESS(f"  Nouvelles annonces créées : {created}"))
        self.stdout.write(self.style.SUCCESS(f"  Jeux nouvellement couverts : {len(games_with_new_listings)}"))
