# documind/documents/pdf_loader.py
#
# WHAT THIS FILE DOES:
# Reads an uploaded PDF page by page, falling back to OCR on pages that have no
# text layer. It is the PDF half of DocumentLoader: the only thing it adds to
# the base class is `_extract_pages`, because validating the file, naming the
# document and refusing an empty one are already written once in `load()`.
#
# WHY OCR IS DECIDED PER DOCUMENT AND APPLIED PER PAGE:
# The pages needing OCR are counted before anything is read, so a document that
# would take minutes of Tesseract time is refused up front rather than halfway
# through — the same principle as the upload size gate. Then each page is
# handled on its own: a page with a real text layer is never sent to OCR, and a
# page that yields nothing either way is skipped rather than stored empty.
#
# WHY THE OCR ENGINE IS PASSED IN:
# Reading an image is OcrEngine's job; this class only decides which pages need
# it and turns each page into an image. Taking the engine as a constructor
# argument means a test can hand in a fake one that reports a chosen text and
# confidence, instead of patching module functions behind the loader's back.
# The deciding still uses ocr.py's page_needs_ocr and OCR_RESOLUTION, so those
# rules stay written in one place.

import pdfplumber

import ocr
from documind.config import AppConfig
from documind.documents.document_loader import DocumentLoader
from documind.documents.models import ExtractedPage
from documind.ocr.models import OcrResult
from documind.ocr.ocr_engine import OcrEngine
from errors import ScannedPdfTooLong


class PdfLoader(DocumentLoader):
    """
    Reads PDFs, using OCR for pages that have no text layer.

    `ocr_engine` reads the scanned pages; when none is given, a real OcrEngine
    is built from `config`. `use_ocr=False` skips OCR entirely.
    """

    SUPPORTED_EXTENSIONS = (".pdf",)
    DEFAULT_NAME = "document.pdf"

    def __init__(
        self,
        config: AppConfig,
        use_ocr: bool = True,
        ocr_engine: OcrEngine | None = None,
    ):
        super().__init__(config)
        # use_ocr=False forces the text-layer-only path, which is how the tests
        # describe a machine without Tesseract.
        self._use_ocr = use_ocr
        self._ocr_engine = ocr_engine if ocr_engine is not None else OcrEngine(config)

    def scanned_page_count(self, file) -> int:
        """
        How many pages lack a usable text layer.

        Used to tell "this PDF is scanned and we need OCR" apart from "this PDF
        is genuinely empty", which are different problems with different
        remedies.
        """
        with pdfplumber.open(file) as pdf:
            return sum(
                1 for page in pdf.pages if ocr.page_needs_ocr(page.extract_text())
            )

    def _extract_pages(self, file) -> list[ExtractedPage]:
        """
        One ExtractedPage per readable page, numbered from 1 as a reader sees
        them.

        Pages with no usable text layer fall back to OCR when the engine is
        available — those come back with used_ocr=True and the engine's
        confidence in ocr_confidence — and pages that yield nothing either way
        are skipped.
        """
        pages: list[ExtractedPage] = []

        with pdfplumber.open(file) as pdf:
            ocr_pages = [
                page for page in pdf.pages if ocr.page_needs_ocr(page.extract_text())
            ]
            ocr_wanted = (
                self._use_ocr and ocr_pages and self._ocr_engine.is_available()
            )

            # Refuse up front rather than starting an OCR pass we know will take
            # minutes — the same principle as the upload size gate.
            if ocr_wanted and len(ocr_pages) > self._config.max_ocr_pages:
                raise ScannedPdfTooLong(
                    getattr(file, "name", "The file"),
                    len(ocr_pages),
                    self._config.max_ocr_pages,
                )

            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                used_ocr = False
                ocr_confidence = None

                if ocr.page_needs_ocr(page_text) and ocr_wanted:
                    result = self._recognise_page(page)
                    page_text = result.text
                    used_ocr = True
                    ocr_confidence = result.confidence

                if page_text and page_text.strip():  # image-only pages return None
                    pages.append(
                        ExtractedPage(
                            number=page_number,
                            text=page_text,
                            used_ocr=used_ocr,
                            ocr_confidence=ocr_confidence,
                        )
                    )

        return pages

    def _recognise_page(self, page) -> OcrResult:
        """The OCR engine's reading of one pdfplumber page, rendered to an image."""
        try:
            image = page.to_image(resolution=ocr.OCR_RESOLUTION).original
        except Exception:
            # A page that fails to render is a page with no text, not a reason
            # to abandon the rest of the document. pdfplumber hands rendering to
            # pypdfium2, whose failures on a damaged page are not one exception
            # type, so this cannot be narrowed without letting some of them out.
            return OcrResult("", 0.0)

        return self._ocr_engine.recognise(image)
