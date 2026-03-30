"""
Management command pour importer les jeux depuis le JSON scrappé de jeuxvideo.com.
Usage: python manage.py import_games ../jeux_video_complet.json ../mappings.json
"""

import json

from django.core.management.base import BaseCommand
from django.db import transaction

from games.models import Game, Genre, Machine


class Command(BaseCommand):
    help = "Importe les jeux vidéo depuis les fichiers JSON (jeux + mappings)"

    def add_arguments(self, parser):
        parser.add_argument(
            "games_file",
            help="Chemin vers jeux_video_complet.json",
        )
        parser.add_argument(
            "mappings_file",
            help="Chemin vers mappings.json",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Supprime toutes les données existantes avant import",
        )

    def handle(self, *args, **options):
        games_file = options["games_file"]
        mappings_file = options["mappings_file"]

        self.stdout.write("Chargement des fichiers...")
        with open(mappings_file, "r", encoding="utf-8") as f:
            mappings = json.load(f)
        with open(games_file, "r", encoding="utf-8") as f:
            games_data = json.load(f)

        if options["clear"]:
            self.stdout.write("Suppression des données existantes...")
            Game.objects.all().delete()
            Genre.objects.all().delete()
            Machine.objects.all().delete()

        # --- Import machines ---
        self.stdout.write("Import des plateformes...")
        machine_map = {}
        for jvc_id_str, slug in mappings["machines"].items():
            jvc_id = int(jvc_id_str)
            name = self._slug_to_name(slug, jvc_id, "machine")
            obj, _ = Machine.objects.update_or_create(
                jvc_id=jvc_id,
                defaults={"name": name, "slug": slug},
            )
            machine_map[jvc_id] = obj
        self.stdout.write(f"  {len(machine_map)} plateformes")

        # --- Import genres ---
        self.stdout.write("Import des genres...")
        genre_map = {}
        for jvc_id_str, slug in mappings["genres"].items():
            jvc_id = int(jvc_id_str)
            name = self._slug_to_name(slug, jvc_id, "genre")
            obj, _ = Genre.objects.update_or_create(
                jvc_id=jvc_id,
                defaults={"name": name, "slug": slug},
            )
            genre_map[jvc_id] = obj
        self.stdout.write(f"  {len(genre_map)} genres")

        # --- Import games par batch ---
        self.stdout.write(f"Import de {len(games_data)} jeux...")
        batch_size = 500
        created = 0
        updated = 0

        for i in range(0, len(games_data), batch_size):
            batch = games_data[i : i + batch_size]
            with transaction.atomic():
                for item in batch:
                    game, was_created = Game.objects.update_or_create(
                        jvc_id=item["id"],
                        defaults={
                            "title": item.get("title", ""),
                            "game_type": item.get("type", 9),
                            "release_date": item.get("releaseDate", ""),
                            "cover_url": item.get("coverUrl", ""),
                        },
                    )

                    # Relations M2M
                    machine_objs = [
                        machine_map[mid]
                        for mid in item.get("machines", [])
                        if mid in machine_map
                    ]
                    genre_objs = [
                        genre_map[gid]
                        for gid in item.get("genres", [])
                        if gid in genre_map
                    ]
                    game.machines.set(machine_objs)
                    game.genres.set(genre_objs)

                    if was_created:
                        created += 1
                    else:
                        updated += 1

            self.stdout.write(f"  {min(i + batch_size, len(games_data))}/{len(games_data)}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Terminé ! {created} créés, {updated} mis à jour."
            )
        )

    # Noms lisibles pour les plateformes/genres connus
    MACHINE_NAMES = {
        10: "PC", 14: "Stadia", 20: "PS4", 22: "PS5", 30: "Xbox One",
        32: "Xbox Series", 40: "Wii U", 42: "Switch 2", 50: "PS3",
        60: "Xbox 360", 70: "3DS", 80: "PS Vita", 90: "iOS", 100: "Android",
        110: "Web", 120: "3DO", 130: "Amiga", 150: "Apple II", 200: "Game Boy",
        210: "GBA", 220: "GameCube", 280: "Mac", 300: "Mega Drive",
        340: "Neo Geo", 360: "NES", 370: "N64", 380: "DS", 390: "PS1",
        400: "PS2", 410: "PSP", 420: "Saturn", 430: "SNES", 460: "Wii",
        470: "Xbox", 177539: "Switch", 200772: "Steam Deck", 171740: "Arcade",
        175794: "Linux",
    }

    GENRE_NAMES = {
        2020: "FPS", 2030: "TPS", 2170: "MMO", 2180: "MMOFPS", 2190: "MMORPG",
        2240: "RPG", 2250: "Action RPG", 2260: "Dungeon RPG", 2280: "Roguelike",
        2290: "Tactical RPG", 2350: "4X", 2480: "MOBA",
    }

    def _slug_to_name(self, slug, jvc_id, kind):
        if kind == "machine" and jvc_id in self.MACHINE_NAMES:
            return self.MACHINE_NAMES[jvc_id]
        if kind == "genre" and jvc_id in self.GENRE_NAMES:
            return self.GENRE_NAMES[jvc_id]
        return slug.replace("-", " ").title()
