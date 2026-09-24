# documind/ocr/models.py
#
# WHAT THIS FILE DOES:
# Defines OcrResult — what one OCR pass over an image produced: the text, and
# how sure Tesseract was about it.
#
# WHY CONFIDENCE TRAVELS WITH THE TEXT:
# Text read off a scan is a machine's guess, and a guess is only useful when you
# know how good it is. Keeping the two in one object means no caller can end up
# holding recognised text without the number that says whether to trust it.

from dataclasses import dataclass


@dataclass(frozen=True)
class OcrResult:
    """
    The text recognised in one image and Tesseract's confidence in it.

    `confidence` runs from 0 to 100: the mean of Tesseract's per-word
    confidences. A failed or empty recognition is text "" with confidence 0.0.
    """

    text: str
    confidence: float
