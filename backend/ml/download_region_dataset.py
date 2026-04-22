#!/usr/bin/env python3
"""Télécharge un dataset labellisé par région pour entraîner un modèle PAL/NTSC/JP.

Uniquement pour SNES et NES où la forme de la cartouche diffère selon la région :
- SNES PAL : cartouche avec encoches latérales
- SNES NTSC : cartouche sans encoches, plus large
- Super Famicom (JP) : cartouche plus petite/colorée
- NES PAL/NTSC : cartouches largement identiques visuellement
- Famicom (JP) : cartouches colorées très différentes

Labels via Listing.region (PAL/NTSC/JP) détectée par titre.

Usage :
    python ml/download_region_dataset.py --console snes --output region_snes --limit 200
    python ml/download_region_dataset.py --console nes --output region_nes --limit 200
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django
django.setup()

from games.models import Listing

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
PLACEHOLDERS = (".svg", "RicardoAi")


def _is_real(url: str) -> bool:
    return url and url.startswith("http") and not any(p in url for p in PLACEHOLDERS)


def download_image(url: str, dest: Path, timeout: int = 10) -> bool:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
        resp.raise_for_status()
        if "image" not in resp.headers.get("content-type", ""):
            return False
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
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
    parser.add_argument("--console", required=True, choices=["snes", "nes"])
    parser.add_argument("--output", default="region_dataset")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    output = Path(args.output)

    for region in ["PAL", "NTSC", "JP"]:
        cls_dir = output / region.lower()
        cls_dir.mkdir(parents=True, exist_ok=True)

        existing = len(list(cls_dir.glob("*.jpg")))
        needed = max(0, args.limit - existing)

        # Sélection : listings de la console ciblée, région donnée, image réelle
        # Préférer les cib/loose pour bien voir la cartouche
        listings = (
            Listing.objects
            .filter(platform_slug=args.console, region=region)
            .exclude(image_url="")
            .order_by("?")
            [:needed + 100]
        )

        print(f"\n[{args.console}/{region}] {existing} existants, {needed} à télécharger ({listings.count()} candidats)")

        downloaded = 0
        for listing in listings:
            if downloaded >= needed:
                break
            if not _is_real(listing.image_url):
                continue

            fname = hashlib.md5(listing.image_url.encode()).hexdigest() + ".jpg"
            dest = cls_dir / fname
            if dest.exists():
                continue

            if download_image(listing.image_url, dest):
                downloaded += 1
                if downloaded % 50 == 0:
                    print(f"  {downloaded}/{needed}...")

        total = len(list(cls_dir.glob("*.jpg")))
        print(f"  [{region}] Total: {total} images")

    print(f"\nDataset prêt : {output}")


if __name__ == "__main__":
    main()
