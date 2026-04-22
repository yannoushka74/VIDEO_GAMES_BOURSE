"""Détection du format/console à partir de l'image du listing.

Classifie le format physique visible sur la photo :
NES, SNES, N64, GBA, PS1, Saturn, Dreamcast, Neo Geo.

Chaque console a un format de cartouche/boîtier très distinct :
- NES : cartouche grise rectangulaire large
- SNES : cartouche arrondie grise/violette
- N64 : petite cartouche grise
- GBA : mini cartouche
- PS1 : boîtier CD jewel case
- Saturn : boîtier CD, spine bleu
- Dreamcast : boîtier CD, spine bleu/orange
- Neo Geo : grande cartouche noire (AES)

Usage :
    from ml.detect_console import ConsoleClassifier
    clf = ConsoleClassifier()
    console, confidence = clf.predict_url("https://...")
"""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import requests
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

IMG_SIZE = 224
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


class ConsoleClassifier:
    """Classifie la console/format d'un jeu depuis une image."""

    def __init__(
        self,
        model_path: str = "ml/console_model.pth",
        class_names_path: str = "ml/console_class_names.txt",
        confidence_threshold: float = 0.6,
    ):
        self.class_names = Path(class_names_path).read_text().strip().split("\n")
        self.confidence_threshold = confidence_threshold

        self.model = models.mobilenet_v2(weights=None)
        self.model.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(self.model.last_channel, len(self.class_names)),
        )
        self.model.load_state_dict(
            torch.load(model_path, map_location=DEVICE, weights_only=True)
        )
        self.model.to(DEVICE)
        self.model.eval()

    def predict_image(self, img: Image.Image) -> tuple[str, float]:
        img = img.convert("RGB")
        tensor = _transform(img).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            outputs = self.model(tensor)
            probs = torch.softmax(outputs, dim=1)
            confidence, predicted = probs.max(1)
        return self.class_names[predicted.item()], confidence.item()

    def predict_url(self, url: str, timeout: int = 10) -> tuple[str | None, float]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            return self.predict_image(img)
        except Exception:
            return None, 0.0

    def verify_platform(
        self, url: str, expected_platform: str
    ) -> tuple[bool, str | None, float]:
        """Vérifie si l'image correspond à la console déclarée.

        Retourne (is_match, detected_console, confidence).
        """
        detected, conf = self.predict_url(url)
        if detected is None or conf < self.confidence_threshold:
            return True, detected, conf  # Pas assez confiant → on laisse passer
        return detected == expected_platform, detected, conf


_classifier = None


def get_console_classifier(**kwargs) -> ConsoleClassifier:
    global _classifier
    if _classifier is None:
        _classifier = ConsoleClassifier(**kwargs)
    return _classifier


class RegionClassifier:
    """Classifie la région (PAL/NTSC/JP) d'un jeu par la forme de sa cartouche.

    Disponible pour SNES (cartouches très distinctes : encoches PAL vs
    sans NTSC vs Super Famicom colorée). Le modèle NES peut être
    entraîné de la même façon.
    """

    def __init__(
        self,
        model_path: str = "ml/region_snes_model.pth",
        class_names_path: str = "ml/region_snes_class_names.txt",
        confidence_threshold: float = 0.7,
    ):
        self.class_names = Path(class_names_path).read_text().strip().split("\n")
        self.confidence_threshold = confidence_threshold

        self.model = models.mobilenet_v2(weights=None)
        self.model.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(self.model.last_channel, len(self.class_names)),
        )
        self.model.load_state_dict(
            torch.load(model_path, map_location=DEVICE, weights_only=True)
        )
        self.model.to(DEVICE)
        self.model.eval()

    def predict_image(self, img: Image.Image) -> tuple[str, float]:
        img = img.convert("RGB")
        tensor = _transform(img).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            outputs = self.model(tensor)
            probs = torch.softmax(outputs, dim=1)
            confidence, predicted = probs.max(1)
        return self.class_names[predicted.item()], confidence.item()

    def predict_url(self, url: str, timeout: int = 10) -> tuple[str | None, float]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            return self.predict_image(img)
        except Exception:
            return None, 0.0


_region_classifier = None


def get_region_classifier(**kwargs) -> RegionClassifier:
    global _region_classifier
    if _region_classifier is None:
        _region_classifier = RegionClassifier(**kwargs)
    return _region_classifier


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ml/detect_console.py <image_url>")
        sys.exit(1)
    clf = ConsoleClassifier()
    cls, conf = clf.predict_url(sys.argv[1])
    print(f"Console: {cls} ({conf:.1%})")
