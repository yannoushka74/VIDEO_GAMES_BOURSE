"""Classification original vs repro à partir de l'image du listing.

Modèle binaire MobileNetV2 fine-tuné sur des images de cartouches/boîtes :
- original : cartouches Nintendo/Sega/SNK officielles d'époque
- repro    : reprints modernes (Strictly Limited, Limited Run, etc.)

Usage :
    from ml.detect_repro import ReproClassifier
    clf = ReproClassifier()
    label, conf = clf.predict_url("https://...")  # ('repro', 0.93)
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


class ReproClassifier:
    """Classifie une image en original / repro."""

    def __init__(
        self,
        model_path: str = "ml/repro_model.pth",
        class_names_path: str = "ml/repro_class_names.txt",
        confidence_threshold: float = 0.85,
    ):
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Modèle repro absent ({model_path}). "
                "Construire le dataset puis entraîner :\n"
                "  python -m ml.download_repro_dataset\n"
                "  python ml/train.py --data repro_dataset --classes original,repro "
                "--model-name repro_model.pth"
            )
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

    def is_repro(self, url: str) -> bool:
        """Wrapper pratique : True si repro avec confiance suffisante."""
        label, conf = self.predict_url(url)
        return label == "repro" and conf >= self.confidence_threshold


_classifier: ReproClassifier | None = None


def get_classifier(**kwargs) -> ReproClassifier | None:
    """Retourne le singleton ou None si modèle non entraîné."""
    global _classifier
    if _classifier is None:
        try:
            _classifier = ReproClassifier(**kwargs)
        except FileNotFoundError as e:
            print(f"[detect_repro] {e}", file=sys.stderr)
            return None
    return _classifier


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ml/detect_repro.py <image_url_or_path>")
        sys.exit(1)
    target = sys.argv[1]
    clf = ReproClassifier()
    if target.startswith("http"):
        label, conf = clf.predict_url(target)
    else:
        img = Image.open(target)
        label, conf = clf.predict_image(img)
    print(f"Label: {label} ({conf:.1%})")
