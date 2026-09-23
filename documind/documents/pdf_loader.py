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
# WHY IT CALLS ocr.py DIRECTLY:
# OCR availability is a fact about the machine, not a strategy with alternatives
# to choose between — wrapping two module functions in a class would add a name
# without adding a decision.

import pdfplumber

import ocr
from documind.config import AppConfig
from documind.documents.document_loader import DocumentLoader
from documind.documents.models import ExtractedPage
from errors import ScannedPdfTooLong


class PdfLoader(DocumentLoader):
    """Reads PDFs, using OCR for pages that have no text layer."""

    SUPPORTED_EXTENSIONS = (".pdf",)
    DEFAULT_NAME = "document.pdf"

    def __init__(self, config: AppConfig, use_ocr: bool = True):
        super().__init__(config)
        # use_ocr=False forces the text-layer-only path, which is how the tests
        # describe a machine without Tesseract.
        self._use_ocr = use_ocr

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

        Pages with no usable text layer fall back to OCR when Tesseract is
        available — those come back with used_ocr=True — and pages that yield
        nothing either way are skipped.
        """
        pages: list[ExtractedPage] = []

        with pdfplumber.open(file) as pdf:
            ocr_pages = [
                page for page in pdf.pages if ocr.page_needs_ocr(page.extract_text())
            ]
            ocr_wanted = self._use_ocr and ocr_pages and ocr.is_available()

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

                if ocr.page_needs_ocr(page_text) and ocr_wanted:
                    page_text = ocr.ocr_page(page)
                    used_ocr = True

                if page_text and page_text.strip():  # image-only pages return None
                    pages.append(
                        ExtractedPage(
                            number=page_number, text=page_text, used_ocr=used_ocr
                        )
                    )

        return pages
