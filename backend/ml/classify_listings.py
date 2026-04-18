#!/usr/bin/env python3
"""Reclassifie la condition des listings via le modèle image.

Post-processing : tourne après le scraping pour mettre à jour
Listing.condition en se basant sur l'image au lieu du titre.

Usage :
    python ml/classify_listings.py                        # tous les listings non classifiés
    python ml/classify_listings.py --source ebay          # eBay seulement
    python ml/classify_listings.py --source ricardo       # Ricardo seulement
    python ml/classify_listings.py --limit 200            # max 200 listings
    python ml/classify_listings.py --reclassify           # re-traiter même ceux déjà classifiés
    python ml/classify_listings.py --dry-run              # preview
    python ml/classify_listings.py --threshold 0.8        # seuil de confiance plus strict
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django
django.setup()

from games.models import Listing
from ml.predict import ConditionClassifier

# Mapping 3 classes modèle → valeurs Listing.condition existantes
MODEL_TO_LISTING = {
    "loose": "loose",
    "cib": "cib",
    "sealed": "new",  # le modèle dit "sealed", la DB utilise "new"
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str, help="Filtrer par source (ebay, ricardo)")
    parser.add_argument("--limit", type=int, default=0, help="Max listings (0=tous)")
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--reclassify", action="store_true",
                        help="Re-traiter les listings déjà classifiés par image")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default="ml/condition_model.pth")
    parser.add_argument("--classes", default="ml/class_names.txt")
    args = parser.parse_args()

    print("Chargement du modèle...")
    clf = ConditionClassifier(
        model_path=args.model,
        class_names_path=args.classes,
        confidence_threshold=args.threshold,
    )
    print(f"Modèle chargé. Classes: {clf.class_names}, seuil: {args.threshold}")

    # Query listings avec image
    qs = Listing.objects.exclude(image_url="").order_by("-scraped_at")

    if args.source:
        qs = qs.filter(source=args.source)

    if not args.reclassify:
        # Ne traiter que ceux pas encore classifiés par le modèle
        # On utilise le champ region comme marqueur temporaire "ml_classified"
        # Alternative propre : ajouter un champ condition_source au modèle
        # Pour l'instant on traite tous ceux qui n'ont pas le tag
        pass  # traiter tous — le modèle est idempotent

    if args.limit > 0:
        qs = qs[:args.limit]

    total = qs.count() if args.limit == 0 else min(args.limit, qs.count())
    print(f"\n{total} listings à traiter...")

    updated = 0
    kept = 0
    failed = 0
    changed_details = {"loose→cib": 0, "loose→new": 0, "cib→loose": 0,
                       "cib→new": 0, "new→loose": 0, "new→cib": 0}

    for i, listing in enumerate(qs.iterator(), 1):
        cls, conf = clf.predict_url(listing.image_url)

        if cls is None:
            failed += 1
            continue

        new_condition = MODEL_TO_LISTING.get(cls, cls)

        if conf < args.threshold:
            kept += 1
            continue

        old_condition = listing.condition or "loose"

        if new_condition != old_condition:
            change_key = f"{old_condition}→{new_condition}"
            if change_key in changed_details:
                changed_details[change_key] += 1

            if args.dry_run:
                print(
                    f"  [{i}/{total}] {listing.title[:45]} | "
                    f"{old_condition}→{new_condition} ({conf:.0%})"
                )
            else:
                listing.condition = new_condition
                listing.save(update_fields=["condition"])

            updated += 1
        else:
            kept += 1

        if i % 100 == 0:
            print(f"  {i}/{total} traités ({updated} modifiés, {kept} gardés, {failed} échoués)")

    print(f"\nTerminé. {updated} modifiés, {kept} gardés, {failed} échoués — "
          f"{'DRY RUN' if args.dry_run else 'LIVE'}")
    print("Détail des changements :")
    for k, v in changed_details.items():
        if v:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
