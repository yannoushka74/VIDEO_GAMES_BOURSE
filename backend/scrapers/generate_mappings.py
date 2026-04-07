"""
Génère data/mappings.json à partir de jeux_video_complet.json.

Le JSON des jeux contient déjà les noms (genre_names, machine_names) en plus
des IDs numériques — ce script en extrait un mapping id → slug propre.

Usage:
  python backend/scrapers/generate_mappings.py
  python backend/scrapers/generate_mappings.py --games data/jeux_video_complet.json --out data/mappings.json
"""

import argparse
import json
import re
import unicodedata
from pathlib import Path


def slugify(name: str) -> str:
    """Convertit un nom lisible en slug ASCII minuscule."""
    name = unicodedata.normalize("NFD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    return name


# Slugs manuels pour les consoles ciblées (priorité sur le slugify automatique)
MACHINE_SLUG_OVERRIDES = {
    340: "neo",       # Neo Geo
    360: "nes",       # NES
    430: "snes",      # SNES
    210: "gba",       # Game Boy Advance
    420: "saturn",    # Sega Saturn
    370: "n64",       # Nintendo 64
    200: "gb",        # Game Boy
    380: "ds",        # Nintendo DS
    70:  "3ds",       # 3DS
    390: "ps1",       # PlayStation
    400: "ps2",       # PlayStation 2
    410: "psp",       # PSP
    50:  "ps3",       # PlayStation 3
    20:  "ps4",       # PlayStation 4
    22:  "ps5",       # PlayStation 5
    60:  "xbox360",   # Xbox 360
    30:  "xboxone",   # Xbox One
    32:  "xboxseries",# Xbox Series
    220: "gamecube",  # GameCube
    460: "wii",       # Wii
    40:  "wiiu",      # Wii U
    177539: "switch", # Nintendo Switch
    42:  "switch2",   # Nintendo Switch 2
    10:  "pc",        # PC
    280: "mac",       # Mac
    90:  "ios",       # iOS
    100: "android",   # Android
    300: "megadrive", # Mega Drive
    171740: "arcade", # Arcade
}


def main():
    parser = argparse.ArgumentParser(description="Génère mappings.json depuis jeux_video_complet.json")
    parser.add_argument(
        "--games",
        default="data/jeux_video_complet.json",
        help="Chemin vers jeux_video_complet.json",
    )
    parser.add_argument(
        "--out",
        default="data/mappings.json",
        help="Chemin de sortie pour mappings.json",
    )
    args = parser.parse_args()

    games_path = Path(args.games)
    out_path = Path(args.out)

    if not games_path.exists():
        print(f"Fichier introuvable : {games_path}")
        print("Lance d'abord : python backend/scrapers/scraper_jvc.py")
        return

    print(f"Lecture de {games_path}...")
    with open(games_path, encoding="utf-8") as f:
        games = json.load(f)

    genres: dict[str, str] = {}    # id_str -> slug
    machines: dict[str, str] = {}  # id_str -> slug

    for game in games:
        # Genres
        genre_ids = game.get("genres", [])
        genre_names = game.get("genre_names", [])
        for gid, gname in zip(genre_ids, genre_names):
            key = str(gid)
            if key not in genres and gname:
                genres[key] = slugify(gname)

        # Machines
        machine_ids = game.get("machines", [])
        machine_names_list = game.get("machine_names", [])
        for mid, mname in zip(machine_ids, machine_names_list):
            key = str(mid)
            if key not in machines:
                if mid in MACHINE_SLUG_OVERRIDES:
                    machines[key] = MACHINE_SLUG_OVERRIDES[mid]
                elif mname:
                    machines[key] = slugify(mname)

    # Trier par ID pour une lecture facile
    genres = dict(sorted(genres.items(), key=lambda x: int(x[0])))
    machines = dict(sorted(machines.items(), key=lambda x: int(x[0])))

    mappings = {"genres": genres, "machines": machines}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mappings, f, ensure_ascii=False, indent=2)

    print(f"{len(genres)} genres trouvés")
    print(f"{len(machines)} machines trouvées")
    print(f"Mappings exportés : {out_path}")

    # Afficher les consoles ciblées
    retro_slugs = {"neo", "nes", "snes", "gba", "saturn", "n64"}
    found = {slug for slug in machines.values() if slug in retro_slugs}
    missing = retro_slugs - found
    print(f"\nConsoles rétro ciblées : {sorted(found)}")
    if missing:
        print(f"Manquantes : {sorted(missing)}")


if __name__ == "__main__":
    main()
