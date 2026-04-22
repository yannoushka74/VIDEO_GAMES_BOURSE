"""Pipeline d'inférence multi-modèle pour les listings.

Enchaîne 3 analyses sur l'image d'un listing :
1. Détection de condition (loose/cib/sealed)
2. Détection de console (nes/snes/n64/gba/ps1/saturn/dreamcast/neo)
3. Détection de langue/région (JP/PAL/unknown via OCR)

Usage :
    from ml.pipeline import ListingAnalyzer
    analyzer = ListingAnalyzer()
    result = analyzer.analyze(image_url, platform_slug="snes", title_condition="loose")

    result = {
        "condition": "cib",
        "condition_confidence": 0.92,
        "condition_source": "image",         # "image" ou "title"
        "console_detected": "snes",
        "console_confidence": 0.88,
        "console_match": True,               # correspond au platform_slug déclaré
        "region_detected": "JP",
        "region_confidence": 0.85,
        "flags": ["region_mismatch"],         # anomalies détectées
    }
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Mapping condition modèle → DB
CONDITION_MODEL_TO_DB = {
    "loose": "loose",
    "cib": "cib",
    "sealed": "new",
}


class ListingAnalyzer:
    """Pipeline d'analyse multi-modèle pour les images de listings."""

    # Consoles pour lesquelles un modèle région par forme de cartouche existe
    REGION_MODELS = {
        "snes": ("ml/region_snes_model.pth", "ml/region_snes_class_names.txt"),
        # "nes": ("ml/region_nes_model.pth", "ml/region_nes_class_names.txt"),
    }

    def __init__(
        self,
        condition_model: str = "ml/condition_model.pth",
        condition_classes: str = "ml/class_names.txt",
        console_model: str = "ml/console_model.pth",
        console_classes: str = "ml/console_class_names.txt",
        condition_threshold: float = 0.7,
        console_threshold: float = 0.6,
        region_threshold: float = 0.7,
        enable_ocr: bool = True,
    ):
        self.condition_threshold = condition_threshold
        self.console_threshold = console_threshold
        self.region_threshold = region_threshold
        self.enable_ocr = enable_ocr

        # Lazy load des modèles
        self._condition_clf = None
        self._console_clf = None
        self._region_clfs = {}  # par platform_slug
        self._condition_model = condition_model
        self._condition_classes = condition_classes
        self._console_model = console_model
        self._console_classes = console_classes

    def _get_condition_clf(self):
        if self._condition_clf is None:
            from ml.predict import ConditionClassifier
            self._condition_clf = ConditionClassifier(
                self._condition_model, self._condition_classes,
                self.condition_threshold,
            )
        return self._condition_clf

    def _get_console_clf(self):
        if self._console_clf is None:
            from ml.detect_console import ConsoleClassifier
            self._console_clf = ConsoleClassifier(
                self._console_model, self._console_classes,
                self.console_threshold,
            )
        return self._console_clf

    def _get_region_clf(self, platform_slug: str):
        """Retourne le classifieur région pour la console donnée (ou None)."""
        if platform_slug not in self.REGION_MODELS:
            return None
        if platform_slug in self._region_clfs:
            return self._region_clfs[platform_slug]
        model_path, classes_path = self.REGION_MODELS[platform_slug]
        try:
            from ml.detect_console import RegionClassifier
            clf = RegionClassifier(model_path, classes_path, self.region_threshold)
            self._region_clfs[platform_slug] = clf
            return clf
        except FileNotFoundError:
            self._region_clfs[platform_slug] = None
            return None

    def _download_image(self, url: str, timeout: int = 10) -> Optional[Image.Image]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            if "image" not in resp.headers.get("content-type", ""):
                return None
            return Image.open(BytesIO(resp.content)).convert("RGB")
        except Exception as e:
            logger.debug("Image download failed: %s", e)
            return None

    def analyze(
        self,
        image_url: str,
        platform_slug: str = "",
        title_condition: str = "loose",
    ) -> dict:
        """Analyse complète d'un listing.

        Retourne un dict avec condition, console, region et flags.
        """
        result = {
            "condition": title_condition,
            "condition_confidence": 0.0,
            "condition_source": "title",
            "console_detected": None,
            "console_confidence": 0.0,
            "console_match": True,
            "region_detected": "unknown",
            "region_confidence": 0.0,
            "flags": [],
        }

        if not image_url or image_url.endswith(".svg"):
            return result

        img = self._download_image(image_url)
        if img is None:
            return result

        # 1. Condition
        try:
            cond_clf = self._get_condition_clf()
            cond, cond_conf = cond_clf.predict_image(img)
            result["condition_confidence"] = cond_conf
            if cond_conf >= self.condition_threshold:
                result["condition"] = CONDITION_MODEL_TO_DB.get(cond, cond)
                result["condition_source"] = "image"
        except Exception as e:
            logger.warning("Condition model failed: %s", e)

        # 2. Console
        try:
            console_clf = self._get_console_clf()
            console, console_conf = console_clf.predict_image(img)
            result["console_detected"] = console
            result["console_confidence"] = console_conf
            if console_conf >= self.console_threshold and platform_slug:
                if console != platform_slug:
                    result["console_match"] = False
                    result["flags"].append("console_mismatch")
        except FileNotFoundError:
            pass  # Modèle console pas encore entraîné
        except Exception as e:
            logger.warning("Console model failed: %s", e)

        # 3a. Région via modèle image (SNES uniquement pour l'instant)
        region_clf = self._get_region_clf(platform_slug)
        if region_clf:
            try:
                region_img, region_conf_img = region_clf.predict_image(img)
                if region_conf_img >= self.region_threshold:
                    result["region_detected"] = region_img.upper()
                    result["region_confidence"] = region_conf_img
                    result["region_source"] = "cartridge_shape"
                    if region_img.upper() != "PAL":
                        result["flags"].append("region_mismatch")
            except Exception as e:
                logger.warning("Region model failed: %s", e)

        # 3b. Région via OCR (fallback / JP detection)
        if self.enable_ocr and result["region_detected"] == "unknown":
            try:
                from ml.detect_language import detect_region_from_image
                region, region_conf, details = detect_region_from_image(image_url)
                result["region_detected"] = region
                result["region_confidence"] = region_conf
                result["region_source"] = "ocr"
                if region == "JP":
                    result["flags"].append("region_mismatch")
            except Exception as e:
                logger.warning("OCR region detection failed: %s", e)

        return result

    def analyze_batch(
        self,
        listings: list[dict],
    ) -> list[dict]:
        """Analyse un batch de listings.

        Chaque listing doit avoir: image_url, platform_slug, condition.
        """
        results = []
        for i, listing in enumerate(listings):
            r = self.analyze(
                listing.get("image_url", ""),
                listing.get("platform_slug", ""),
                listing.get("condition", "loose"),
            )
            r["listing_id"] = listing.get("id")
            results.append(r)
            if (i + 1) % 50 == 0:
                logger.info("Analyzed %d/%d listings", i + 1, len(listings))
        return results
