# documind/ocr/__init__.py
#
# Text recognition: the engine that reads text out of an image, and the result
# it hands back.

from documind.ocr.models import OcrResult
from documind.ocr.ocr_engine import OcrEngine

__all__ = ["OcrEngine", "OcrResult"]
