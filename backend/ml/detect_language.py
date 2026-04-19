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
from PIL import Image

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
        _reader = easyocr.Reader(["ja", "en", "fr", "de"], gpu=False, verbose=False)
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
    jp_char_threshold: int = 3,
    timeout: int = 10,
) -> tuple[str, float, dict]:
    """Détecte la région à partir de l'image via OCR.

    Retourne (region, confidence, details).
    - region: "JP", "PAL", "unknown"
    - confidence: 0.0-1.0
    - details: dict avec les infos OCR

    Stratégie :
    - Si >= jp_char_threshold caractères japonais détectés → JP
    - Sinon → "unknown" (on ne peut pas distinguer PAL de NTSC visuellement)
    """
    details = {"japanese_chars": 0, "total_chars": 0, "texts": []}

    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            return "unknown", 0.0, details

        reader = _get_reader()
        results = reader.readtext(resp.content)

        all_text = ""
        for bbox, text, conf in results:
            if conf > 0.3:
                all_text += text
                details["texts"].append({"text": text, "confidence": conf})

        details["total_chars"] = len(all_text)
        details["japanese_chars"] = _count_japanese_chars(all_text)

        if details["japanese_chars"] >= jp_char_threshold:
            confidence = min(details["japanese_chars"] / 10, 1.0)
            return "JP", confidence, details

        return "unknown", 0.5, details

    except Exception as e:
        logger.warning("OCR failed for %s: %s", image_url[:60], e)
        return "unknown", 0.0, details
