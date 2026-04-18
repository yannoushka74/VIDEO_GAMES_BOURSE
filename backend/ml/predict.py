"""Module d'inférence pour la classification de condition de jeu vidéo.

Charge le modèle MobileNetV2 fine-tuné et classifie une image (URL ou fichier)
en loose/cib/new/graded.

Usage standalone :
    python ml/predict.py https://example.com/image.jpg
    python ml/predict.py image.jpg

Usage programmatique :
    from ml.predict import ConditionClassifier
    clf = ConditionClassifier("ml/condition_model.pth", "ml/class_names.txt")
    condition, confidence = clf.predict_url("https://...")
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


class ConditionClassifier:
    """Classifie la condition d'un jeu vidéo depuis une image."""

    def __init__(
        self,
        model_path: str = "ml/condition_model.pth",
        class_names_path: str = "ml/class_names.txt",
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
        """Classifie une image PIL. Retourne (classe, confidence)."""
        img = img.convert("RGB")
        tensor = _transform(img).unsqueeze(0).to(DEVICE)

        with torch.no_grad():
            outputs = self.model(tensor)
            probs = torch.softmax(outputs, dim=1)
            confidence, predicted = probs.max(1)

        cls = self.class_names[predicted.item()]
        conf = confidence.item()
        return cls, conf

    def predict_url(self, url: str, timeout: int = 10) -> tuple[str | None, float]:
        """Télécharge une image et la classifie.

        Retourne (None, 0) si le téléchargement échoue.
        """
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content))
            return self.predict_image(img)
        except Exception:
            return None, 0.0

    def predict_with_fallback(
        self, url: str, title_condition: str
    ) -> tuple[str, float, str]:
        """Classifie avec fallback sur la condition titre si confidence basse.

        Retourne (condition, confidence, source) où source = "image" ou "title".
        """
        cls, conf = self.predict_url(url)
        if cls is not None and conf >= self.confidence_threshold:
            return cls, conf, "image"
        return title_condition, conf, "title"


# Singleton lazy-loaded
_classifier: ConditionClassifier | None = None


def get_classifier(**kwargs) -> ConditionClassifier:
    """Retourne le classifieur singleton (chargé une seule fois)."""
    global _classifier
    if _classifier is None:
        _classifier = ConditionClassifier(**kwargs)
    return _classifier


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ml/predict.py <image_url_or_path>")
        sys.exit(1)

    target = sys.argv[1]
    clf = ConditionClassifier()

    if target.startswith("http"):
        cls, conf = clf.predict_url(target)
    else:
        img = Image.open(target)
        cls, conf = clf.predict_image(img)

    print(f"Condition: {cls} ({conf:.1%})")
