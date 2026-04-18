#!/usr/bin/env python3
"""Télécharge les images des listings pour constituer le dataset d'entraînement.

Utilise la condition détectée par le titre (detect_condition) comme label initial.
Les images sont organisées par classe dans des dossiers :
    dataset/loose/
    dataset/cib/
    dataset/new/
    dataset/graded/

Usage :
    # Depuis le pod backend ou en local avec accès DB
    python ml/download_dataset.py --output dataset --limit-per-class 400
    python ml/download_dataset.py --output dataset --limit-per-class 400 --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import requests

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django
django.setup()

from games.models import Listing

CLASSES = ["loose", "cib", "new", "graded"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def download_image(url: str, dest: Path, timeout: int = 10) -> bool:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            return False
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        # Vérifier taille minimale (éviter les placeholders)
        if dest.stat().st_size < 2000:
            dest.unlink()
            return False
        return True
    except Exception:
        if dest.exists():
            dest.unlink()
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dataset", help="Dossier de sortie")
    parser.add_argument("--limit-per-class", type=int, default=400)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output = Path(args.output)

    for cls in CLASSES:
        cls_dir = output / cls
        cls_dir.mkdir(parents=True, exist_ok=True)

        existing = len(list(cls_dir.glob("*.jpg")))
        needed = max(0, args.limit_per_class - existing)

        listings = (
            Listing.objects
            .filter(condition=cls)
            .exclude(image_url="")
            .order_by("?")  # random pour diversifier
            [:needed + 50]  # marge pour les échecs
        )

        print(f"\n[{cls}] {existing} existants, {needed} à télécharger ({listings.count()} candidats)")

        downloaded = 0
        for listing in listings:
            if downloaded >= needed:
                break

            # Hash de l'URL comme nom de fichier (évite doublons)
            fname = hashlib.md5(listing.image_url.encode()).hexdigest() + ".jpg"
            dest = cls_dir / fname
            if dest.exists():
                continue

            if args.dry_run:
                print(f"  [DRY] {listing.image_url[:80]}")
                downloaded += 1
                continue

            if download_image(listing.image_url, dest):
                downloaded += 1
                if downloaded % 50 == 0:
                    print(f"  {downloaded}/{needed}...")
            # Pas de sleep — les images sont sur des CDN différents

        total = len(list(cls_dir.glob("*.jpg")))
        print(f"  [{cls}] Total: {total} images")

    print("\nDataset prêt :", output)


if __name__ == "__main__":
    main()
