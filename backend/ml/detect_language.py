"""Détection de la région d'un jeu via OCR sur l'image de l'annonce.

Détecte la présence de caractères japonais (hiragana, katakana, kanji)
sur l'image pour identifier les imports JP.

Usage :
    from ml.detect_language import detect_region_from_image
    region, confidence, details = detect_region_from_image(url)
    # region: "JP", "PAL", "unknown"
    # confidence: 0.0-1.0
    # details: {"japanese_chars": 12, "total_chars": 45, ...}
"""

from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import Optional

import requests
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Lazy-load easyocr (lourd en mémoire)
_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["ja", "en"], gpu=False, verbose=False)
    return _reader


def _count_japanese_chars(text: str) -> int:
    """Compte les caractères japonais (hiragana, katakana, kanji)."""
    count = 0
    for c in text:
        cp = ord(c)
        if (0x3040 <= cp <= 0x309F  # Hiragana
                or 0x30A0 <= cp <= 0x30FF  # Katakana
                or 0x4E00 <= cp <= 0x9FFF  # CJK Unified (Kanji)
                or 0xFF00 <= cp <= 0xFFEF  # Fullwidth forms
                ):
            count += 1
    return count


def detect_region_from_image(
    image_url: str,
    jp_char_threshold: int = 2,
    timeout: int = 10,
    min_size: int = 1200,
    ocr_confidence: float = 0.1,
) -> tuple[str, float, dict]:
    """Détecte la région à partir de l'image via OCR.

    Retourne (region, confidence, details).
    - region: "JP", "PAL", "unknown"
    - confidence: 0.0-1.0
    - details: dict avec les infos OCR

    Les petites images (< min_size px) sont upscalées avant OCR
    pour permettre la détection de caractères sur les thumbnails Ricardo.
    """
    import numpy as np

    details = {"japanese_chars": 0, "total_chars": 0, "texts": []}

    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            return "unknown", 0.0, details

        # Upscale + renforcement contraste/netteté pour les petites images Ricardo
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        w, h = img.size
        if max(w, h) < min_size:
            scale = min_size / max(w, h)
            img = img.resize(
                (int(w * scale), int(h * scale)),
                Image.LANCZOS,
            )
            details["upscaled"] = f"{w}x{h} → {img.size[0]}x{img.size[1]}"
            img = ImageEnhance.Contrast(img).enhance(1.5)
            img = ImageEnhance.Sharpness(img).enhance(1.8)

        reader = _get_reader()
        # text_threshold bas pour capter les caractères de basse résolution
        results = reader.readtext(
            np.array(img),
            paragraph=False,
            width_ths=0.3,
            text_threshold=0.3,
            low_text=0.2,
        )

        all_text = ""
        high_conf_jp_chars = 0
        for bbox, text, conf in results:
            if conf > ocr_confidence:
                all_text += text
                details["texts"].append({"text": text, "confidence": conf})
                # Seuil haute confidence à 0.7 pour éviter les faux positifs
                # (les artefacts visuels sont souvent détectés à 40-60%)
                if conf > 0.7:
                    high_conf_jp_chars += _count_japanese_chars(text)

        details["total_chars"] = len(all_text)
        details["japanese_chars"] = _count_japanese_chars(all_text)
        details["high_conf_jp_chars"] = high_conf_jp_chars

        # JP si (au moins 3 chars JP total) OU (au moins 2 chars JP en haute conf)
        # Plus strict que v1 pour éliminer les faux positifs (pitfall, tron, etc.
        # étaient taggés JP par erreur sur des artefacts visuels)
        if details["japanese_chars"] >= 3 or high_conf_jp_chars >= 2:
            confidence = min(max(details["japanese_chars"], high_conf_jp_chars * 2) / 10, 1.0)
            return "JP", confidence, details

        return "unknown", 0.5, details

    except Exception as e:
        logger.warning("OCR failed for %s: %s", image_url[:60], e)
        return "unknown", 0.0, details
