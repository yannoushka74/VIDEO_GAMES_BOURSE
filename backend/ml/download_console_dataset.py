#!/usr/bin/env python3
"""Télécharge les images des listings pour le dataset de détection console.

Les images sont labellisées par platform_slug du listing.
Seuls les listings eBay sont utilisés (Ricardo a trop de placeholders).

Usage :
    python ml/download_console_dataset.py --output console_dataset --limit-per-class 200
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

CONSOLES = ["nes", "snes", "n64", "gba", "ps1", "saturn", "dreamcast", "neo"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
PLACEHOLDER_PATTERNS = ("RicardoAi.svg", "placeholder", ".svg")


def _is_real_image(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    return not any(p in url for p in PLACEHOLDER_PATTERNS)


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
    parser.add_argument("--output", default="console_dataset")
    parser.add_argument("--limit-per-class", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output = Path(args.output)

    for console in CONSOLES:
        cls_dir = output / console
        cls_dir.mkdir(parents=True, exist_ok=True)

        existing = len(list(cls_dir.glob("*.jpg")))
        needed = max(0, args.limit_per_class - existing)

        # Préférer eBay (images réelles), exclure les conditions "loose" pures
        # car une cartouche loose NES/SNES/N64 se ressemble trop
        # Préférer CIB/new car la boîte montre le format console
        listings = (
            Listing.objects
            .filter(platform_slug=console, source="ebay")
            .exclude(image_url="")
            .filter(condition__in=["cib", "new"])
            .order_by("?")
            [:needed + 100]
        )

        # Fallback : inclure loose si pas assez de CIB
        if listings.count() < needed:
            listings = (
                Listing.objects
                .filter(platform_slug=console, source="ebay")
                .exclude(image_url="")
                .order_by("?")
                [:needed + 100]
            )

        print(f"\n[{console}] {existing} existants, {needed} à télécharger ({listings.count()} candidats)")

        downloaded = 0
        for listing in listings:
            if downloaded >= needed:
                break
            if not _is_real_image(listing.image_url):
                continue

            fname = hashlib.md5(listing.image_url.encode()).hexdigest() + ".jpg"
            dest = cls_dir / fname
            if dest.exists():
                continue

            if args.dry_run:
                downloaded += 1
                continue

            if download_image(listing.image_url, dest):
                downloaded += 1
                if downloaded % 50 == 0:
                    print(f"  {downloaded}/{needed}...")

        total = len(list(cls_dir.glob("*.jpg")))
        print(f"  [{console}] Total: {total} images")

    print("\nDataset prêt :", output)


if __name__ == "__main__":
    main()
