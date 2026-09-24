# documind/ocr/ocr_engine.py
#
# WHAT THIS FILE DOES:
# Reads the text out of an image with Tesseract and reports how confident
# Tesseract was, after preparing the image so Tesseract has the best chance.
#
# WHY PREPROCESS:
# Tesseract reads dark glyphs on a light background in straight horizontal
# lines. Colour carries no information for it, so the image is made greyscale;
# a scan fed in slightly crooked breaks its line finding, so the image is
# straightened (deskewed) first.
#
# WHY DESKEW WITH NUMPY:
# numpy and pillow are already dependencies, and a projection-profile search
# needs nothing more: rotate the page by each candidate angle and add up the
# ink in every row. When the lines of text are level, rows alternate between
# full of ink and empty, so the row sums swing hard and their variance peaks.
# Pulling in OpenCV for this one step would add a large native dependency for
# no gain in clarity.
#
# WHY CONFIDENCE IS TESSERACT'S OWN MEAN WORD CONFIDENCE:
# Tesseract already scores every word it recognises. Averaging those scores is
# the measure it is designed to give, and it needs no ground truth, so it can
# be computed for every page of every upload.

import numpy as np
from PIL import Image

import ocr
from documind.config import AppConfig
from documind.ocr.models import OcrResult

# A scanner or phone photo is rarely more than a few degrees off. A wider search
# costs one extra rotation per degree and starts to risk "straightening" a page
# whose content is legitimately set at an angle.
DESKEW_ANGLES = range(-5, 6)


class OcrEngine:
    """Recognises text in images with Tesseract, returning text and confidence."""

    def __init__(self, config: AppConfig):
        self._config = config

    def is_available(self) -> bool:
        """True when the Tesseract binary and its Python wrapper are installed."""
        return ocr.is_available()

    def recognise(self, image: Image.Image) -> OcrResult:
        """
        The text Tesseract reads in `image`, with its mean word confidence.

        The image is converted to greyscale and deskewed before recognition,
        and read with the language set in `AppConfig.ocr_language`. Returns
        OcrResult("", 0.0) when OCR is unavailable or fails, so a failed image
        is treated the same as an image with no text. Never raises.
        """
        if not self.is_available():
            return OcrResult("", 0.0)

        # Imported here, not at the top, for the same reason ocr.py does: the
        # wrapper is optional and this module must import without it.
        import pytesseract

        try:
            prepared = self._deskew(image.convert("L"))
            data = pytesseract.image_to_data(
                prepared,
                lang=self._config.ocr_language,
                output_type=pytesseract.Output.DICT,
            )
        except Exception:
            # Same convention as ocr.ocr_page: an image that fails to process or
            # recognise is an image with no text, not a reason to abandon the
            # rest of the document.
            return OcrResult("", 0.0)

        words = [word for word in data["text"] if word.strip()]

        # Tesseract reports -1 for layout entries (blocks, paragraphs, lines)
        # that are not words; counting them would drag every mean down.
        confidences = [conf for conf in data["conf"] if conf >= 0]
        mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return OcrResult(" ".join(words), float(mean_confidence))

    def _deskew(self, greyscale: Image.Image) -> Image.Image:
        """The greyscale image rotated to the angle that best levels its text."""
        best_angle = 0
        best_variance = -1.0

        # Tried smallest correction first, and only a strictly higher variance
        # replaces the current best, so a blank page or a tie is left unrotated
        # rather than turned by an arbitrary angle.
        for angle in sorted(DESKEW_ANGLES, key=abs):
            rotated = greyscale.rotate(angle, expand=False, fillcolor=255)
            row_sums = np.asarray(rotated, dtype=np.float64).sum(axis=1)
            variance = float(row_sums.var())
            if variance > best_variance:
                best_angle = angle
                best_variance = variance

        return greyscale.rotate(best_angle, expand=False, fillcolor=255)
