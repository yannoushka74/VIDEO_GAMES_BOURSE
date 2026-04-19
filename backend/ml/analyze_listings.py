#!/usr/bin/env python3
"""Analyse les listings via le pipeline multi-modèle (condition + console + région).

Post-processing : tourne après le scraping pour enrichir les listings
avec les résultats des 3 modèles d'inférence.

Usage :
    python ml/analyze_listings.py --limit 100 --dry-run
    python ml/analyze_listings.py --source ebay
    python ml/analyze_listings.py --source ricardo --no-ocr     # sans OCR (plus rapide)
    python ml/analyze_listings.py --no-console                  # sans détection console
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django
django.setup()

from games.models import Listing
from ml.pipeline import ListingAnalyzer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str, help="Filtrer par source (ebay, ricardo)")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-ocr", action="store_true", help="Désactiver la détection de langue OCR")
    parser.add_argument("--no-console", action="store_true", help="Désactiver la détection de console")
    parser.add_argument("--condition-threshold", type=float, default=0.7)
    parser.add_argument("--console-threshold", type=float, default=0.6)
    args = parser.parse_args()

    analyzer = ListingAnalyzer(
        condition_threshold=args.condition_threshold,
        console_threshold=args.console_threshold,
        enable_ocr=not args.no_ocr,
    )

    qs = Listing.objects.exclude(image_url="").exclude(image_url__icontains=".svg").order_by("-scraped_at")
    if args.source:
        qs = qs.filter(source=args.source)
    if args.limit > 0:
        qs = qs[:args.limit]

    total = qs.count() if args.limit == 0 else min(args.limit, qs.count())
    print(f"\n{total} listings à analyser...")
    print(f"OCR: {'ON' if not args.no_ocr else 'OFF'}")
    print(f"Console: {'ON' if not args.no_console else 'OFF'}")

    condition_changed = 0
    console_mismatches = 0
    region_jp = 0
    failed = 0

    for i, listing in enumerate(qs.iterator(), 1):
        result = analyzer.analyze(
            listing.image_url,
            listing.platform_slug,
            listing.condition or "loose",
        )

        flags = result["flags"]
        changed = False

        # Condition mise à jour
        if result["condition_source"] == "image" and result["condition"] != (listing.condition or "loose"):
            old_cond = listing.condition or "loose"
            if not args.dry_run:
                listing.condition = result["condition"]
                changed = True
            condition_changed += 1
            if args.dry_run:
                print(f"  [{i}] CONDITION {old_cond}→{result['condition']} ({result['condition_confidence']:.0%}) | {listing.title[:50]}")

        # Console mismatch
        if "console_mismatch" in flags:
            console_mismatches += 1
            if args.dry_run:
                print(f"  [{i}] CONSOLE {listing.platform_slug}→{result['console_detected']} ({result['console_confidence']:.0%}) | {listing.title[:50]}")

        # Région JP détectée
        if "region_mismatch" in flags:
            region_jp += 1
            if not args.dry_run and listing.region != "JP":
                listing.region = "JP"
                changed = True
            if args.dry_run:
                print(f"  [{i}] REGION →JP ({result['region_confidence']:.0%}) | {listing.title[:50]}")

        if changed:
            listing.save(update_fields=["condition", "region"])

        if i % 100 == 0:
            print(f"  {i}/{total} — cond:{condition_changed} console:{console_mismatches} jp:{region_jp}")

    print(f"\nTerminé — {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"  Conditions modifiées: {condition_changed}")
    print(f"  Console mismatches: {console_mismatches}")
    print(f"  Région JP détectée: {region_jp}")


if __name__ == "__main__":
    main()
