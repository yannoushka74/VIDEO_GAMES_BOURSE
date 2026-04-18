#!/usr/bin/env python3
"""Outil de labellisation rapide pour vérifier/corriger les labels du dataset.

Affiche chaque image avec son label pré-assigné. L'utilisateur peut :
- Entrée → garder le label actuel
- l/c/n/g → changer en loose/cib/new/graded
- d → supprimer l'image (faux positif, mauvaise qualité)
- q → quitter

Usage :
    python ml/label_tool.py dataset/          # vérifier toutes les classes
    python ml/label_tool.py dataset/cib/      # vérifier une classe
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("pip install Pillow")
    sys.exit(1)

SHORTCUTS = {"l": "loose", "c": "cib", "n": "new", "g": "graded"}


def label_directory(data_dir: Path):
    classes_dirs = sorted(
        [d for d in data_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )

    if not classes_dirs:
        # Single class directory
        classes_dirs = [data_dir]

    total = 0
    moved = 0
    deleted = 0

    for cls_dir in classes_dirs:
        images = sorted(cls_dir.glob("*.jpg"))
        if not images:
            continue

        current_class = cls_dir.name
        print(f"\n{'='*50}")
        print(f"  Classe: {current_class} ({len(images)} images)")
        print(f"  [Entrée]=garder  l/c/n/g=changer  d=supprimer  q=quitter")
        print(f"{'='*50}\n")

        for i, img_path in enumerate(images, 1):
            total += 1
            # Tenter d'ouvrir l'image pour vérifier qu'elle est valide
            try:
                img = Image.open(img_path)
                w, h = img.size
                size_info = f"{w}x{h}"
            except Exception:
                print(f"  [{i}/{len(images)}] {img_path.name} — CORROMPUE, supprimée")
                img_path.unlink()
                deleted += 1
                continue

            choice = input(
                f"  [{i}/{len(images)}] {img_path.name} ({size_info}) "
                f"[{current_class}] → "
            ).strip().lower()

            if choice == "q":
                print("\nArrêt.")
                print(f"Total: {total} vues, {moved} déplacées, {deleted} supprimées")
                return

            if choice == "d":
                img_path.unlink()
                deleted += 1
                print("    → supprimée")
                continue

            if choice in SHORTCUTS:
                new_class = SHORTCUTS[choice]
                if new_class != current_class:
                    dest_dir = data_dir / new_class
                    dest_dir.mkdir(exist_ok=True)
                    dest = dest_dir / img_path.name
                    shutil.move(str(img_path), str(dest))
                    moved += 1
                    print(f"    → déplacée vers {new_class}/")
                    continue

            # Entrée vide ou même classe → garder

    print(f"\nTerminé. {total} vues, {moved} déplacées, {deleted} supprimées")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ml/label_tool.py <dataset_dir>")
        sys.exit(1)

    label_directory(Path(sys.argv[1]))
