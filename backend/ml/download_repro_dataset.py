"""Construction auto d'un dataset original vs repro à partir des listings.

Stratégie : on utilise les marqueurs textuels DÉJÀ FIABLES comme labels.
- POSITIFS (repro) : titre contient "strictly limited", "limited run",
  "30th anniversary", "directors cut" (combiné avec sealed dans le titre).
- NÉGATIFS (original) : titre "loose" ou "cib" sans aucun marqueur de
  reprint, sur une plateforme rétro avant 2000.

Sortie :
    repro_dataset/
        repro/      → images de listings labellisés repro
        original/   → images de listings labellisés original

Usage (à exécuter dans un pod ayant accès à la DB) :
    python -m ml.download_repro_dataset --out repro_dataset --limit-per-class 800
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import requests  # noqa: E402

from games.models import Listing  # noqa: E402
from scrapers.matching import is_likely_accessory  # noqa: E402


REPRO_TITLE_PHRASES = (
    "strictly limited", "limited run", "premium edition games",
    "super rare games", "forever physical", "retro-bit", "retrobit",
    "piko interactive", "evercade",
    "30th anniversary", "directors cut", "director's cut",
    "anniversary edition", "collectors edition", "collector's edition",
    "turrican anthology", "turrican director", "super turrican 2 special",
    "super turrican 2 se ", "fan made", "fan-made", "homebrew",
)

# Pour les originaux : on veut être sûrs → exiger "loose" + console connue
ORIGINAL_TITLE_REQUIRED_TOKENS = ("loose", "cib", "boite vide", "boitier seul")


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def is_repro_title(title: str) -> bool:
    low = title.lower()
    return any(p in low for p in REPRO_TITLE_PHRASES)


def looks_like_safe_original(title: str) -> bool:
    low = title.lower()
    if any(p in low for p in REPRO_TITLE_PHRASES):
        return False
    if any(t in low for t in ORIGINAL_TITLE_REQUIRED_TOKENS):
        return True
    return False


def download_image(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except Exception as e:
        print(f"  ERR {url[:60]}: {e}", file=sys.stderr)
        return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="repro_dataset")
    p.add_argument("--limit-per-class", type=int, default=800)
    args = p.parse_args()

    repro_dir = Path(args.out) / "repro"
    orig_dir = Path(args.out) / "original"
    repro_dir.mkdir(parents=True, exist_ok=True)
    orig_dir.mkdir(parents=True, exist_ok=True)

    # POSITIFS — listings avec marqueurs repro dans titre
    print(f"[+] Téléchargement repros (limite {args.limit_per_class})...")
    repro_qs = Listing.objects.exclude(image_url="").exclude(image_url__icontains=".svg")
    repro_count = 0
    for l in repro_qs.iterator():
        if not is_repro_title(l.title):
            continue
        if repro_count >= args.limit_per_class:
            break
        h = hashlib.md5(l.image_url.encode()).hexdigest()
        ext = l.image_url.split(".")[-1].split("?")[0][:4] or "jpg"
        dest = repro_dir / f"{h}.{ext}"
        if download_image(l.image_url, dest):
            repro_count += 1
    print(f"  {repro_count} repros téléchargés")

    # NÉGATIFS — listings clairement loose/cib sans repro markers
    print(f"[+] Téléchargement originals (limite {args.limit_per_class})...")
    orig_qs = (Listing.objects.exclude(image_url="")
               .exclude(image_url__icontains=".svg")
               .order_by("?"))  # random
    orig_count = 0
    for l in orig_qs.iterator():
        if not looks_like_safe_original(l.title):
            continue
        if is_likely_accessory(l.title):
            continue
        if orig_count >= args.limit_per_class:
            break
        h = hashlib.md5(l.image_url.encode()).hexdigest()
        ext = l.image_url.split(".")[-1].split("?")[0][:4] or "jpg"
        dest = orig_dir / f"{h}.{ext}"
        if download_image(l.image_url, dest):
            orig_count += 1
    print(f"  {orig_count} originals téléchargés")
    print(f"\nDataset prêt : {args.out}/{{repro,original}}/")
    print("Entraîner avec :")
    print(f"  python ml/train.py --data {args.out} --classes original,repro \\\\")
    print(f"      --model-name repro_model.pth --epochs 15")


if __name__ == "__main__":
    main()
