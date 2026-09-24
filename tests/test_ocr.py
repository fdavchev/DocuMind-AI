"""
The OCR fallback for scanned PDFs.

Tesseract is a native binary, so these tests never invoke it. What they verify
is everything around it: that a page with no text layer is *detected*, that the
fallback is *reached*, that page numbers and the OCR confidence survive it, that
an absent Tesseract degrades to a clear message rather than a crash, and that a
document too long to OCR is refused rather than started.

The PdfLoader tests hand the loader a FakeOcrEngine (see conftest.py) in place
of the real one — the same seam the application uses, so nothing is patched
behind the loader's back.
"""

import pdfplumber.page
import pytest

import ocr
from documind.config import AppConfig
from documind.documents.pdf_loader import PdfLoader
from documind.documents.text_splitter import TextSplitter
from errors import (
    EmptyDocumentError,
    NoTextInPdf,
    OcrUnavailable,
    ScannedPdfTooLong,
    no_text_error,
    ocr_status,
)


# Captured at import time, before the autouse fixture replaces them with stubs.
REAL_IS_AVAILABLE = ocr.is_available
REAL_TESSERACT_VERSION = ocr.tesseract_version


# ── Detecting a page that needs OCR ────────────────────────────────────────────

def test_a_page_with_no_text_needs_ocr():
    assert ocr.page_needs_ocr(None)
    assert ocr.page_needs_ocr("")
    assert ocr.page_needs_ocr("   \n  ")


def test_a_page_with_a_stray_page_number_still_needs_ocr():
    # Scanned pages are rarely empty — a stamped page number is not a text layer.
    assert ocr.page_needs_ocr("- 7 -")


def test_a_page_with_real_text_does_not_need_ocr():
    assert not ocr.page_needs_ocr("This page has an actual text layer on it.")


def test_the_threshold_is_the_documented_one():
    assert not ocr.page_needs_ocr("x" * ocr.MIN_CHARS_FOR_TEXT_LAYER)
    assert ocr.page_needs_ocr("x" * (ocr.MIN_CHARS_FOR_TEXT_LAYER - 1))


def test_scanned_page_count_counts_only_pages_without_a_text_layer(make_pdf):
    pdf = make_pdf(["a page with a proper text layer on it", "", "- 3 -"])

    assert PdfLoader(AppConfig()).scanned_page_count(pdf) == 2


# ── Degrading without Tesseract ────────────────────────────────────────────────

def test_ocr_page_returns_empty_when_tesseract_is_missing(monkeypatch):
    monkeypatch.setattr(ocr, "is_available", lambda: False)

    assert ocr.ocr_page(object()) == ""


def test_availability_check_never_raises():
    # A missing binary must be a False, not a TesseractNotFoundError escaping
    # into the upload handler.
    REAL_IS_AVAILABLE.cache_clear()
    REAL_TESSERACT_VERSION.cache_clear()

    assert REAL_IS_AVAILABLE() in (True, False)


def test_a_broken_render_is_treated_as_a_page_with_no_text(monkeypatch):
    class ExplodingPage:
        def to_image(self, resolution):
            raise RuntimeError("render failed")

    monkeypatch.setattr(ocr, "is_available", lambda: True)

    # One unreadable page must not abandon the rest of the document.
    assert ocr.ocr_page(ExplodingPage()) == ""


def test_unavailable_hint_names_an_install_route_per_platform():
    hint = ocr.unavailable_hint()

    assert "winget" in hint
    assert "brew" in hint
    assert "apt" in hint


# ── The fallback in the extraction pipeline ────────────────────────────────────

def test_a_scanned_page_is_recovered_by_ocr(make_pdf, fake_ocr_engine):
    # Page 2 has no text layer, standing in for a scanned page.
    pdf = make_pdf(["a page with a proper text layer on it", ""])

    document = PdfLoader(AppConfig(), ocr_engine=fake_ocr_engine).load(pdf)
    pages = {page.number: page for page in document.pages}

    assert pages[2].text == "text recovered by OCR"


def test_a_page_records_that_it_was_read_by_ocr(make_pdf, fake_ocr_engine):
    pdf = make_pdf(["a page with a proper text layer on it", ""])

    document = PdfLoader(AppConfig(), ocr_engine=fake_ocr_engine).load(
        pdf, name="scan.pdf"
    )

    assert [page.used_ocr for page in document.pages] == [False, True]
    assert document.ocr_page_count == 1


def test_a_scanned_page_carries_the_confidence_the_engine_reported(
    make_pdf, fake_ocr_engine
):
    fake_ocr_engine.confidence = 73.25
    pdf = make_pdf(["a page with a proper text layer on it", ""])

    document = PdfLoader(AppConfig(), ocr_engine=fake_ocr_engine).load(pdf)

    assert document.pages[1].ocr_confidence == 73.25


def test_a_text_layer_page_has_no_ocr_confidence_even_with_ocr_on(
    make_pdf, fake_ocr_engine
):
    pdf = make_pdf(["a page with a proper text layer on it", ""])

    document = PdfLoader(AppConfig(), ocr_engine=fake_ocr_engine).load(pdf)

    assert document.pages[0].used_ocr is False
    assert document.pages[0].ocr_confidence is None


def test_the_scanned_page_is_rendered_to_an_image_for_the_engine(
    make_pdf, fake_ocr_engine
):
    pdf = make_pdf(["a page with a proper text layer on it", ""])

    PdfLoader(AppConfig(), ocr_engine=fake_ocr_engine).load(pdf)

    [image] = fake_ocr_engine.images
    # MediaBox is 612 x 792 points (1/72 inch), so at OCR_RESOLUTION dpi the
    # width in pixels is 612 / 72 * OCR_RESOLUTION.
    assert image.width == round(612 / 72 * ocr.OCR_RESOLUTION)


def test_a_page_that_fails_to_render_is_skipped_not_fatal(
    make_pdf, fake_ocr_engine, monkeypatch
):
    def exploding_render(self, *args, **kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr(pdfplumber.page.Page, "to_image", exploding_render)
    pdf = make_pdf(["a page with a proper text layer on it", ""])

    # One unreadable page must not abandon the rest of the document.
    document = PdfLoader(AppConfig(), ocr_engine=fake_ocr_engine).load(pdf)

    assert [page.number for page in document.pages] == [1]
    assert [page.used_ocr for page in document.pages] == [False]
    assert fake_ocr_engine.images == []


def test_a_page_the_engine_reads_as_empty_is_skipped(make_pdf, fake_ocr_engine):
    fake_ocr_engine.text = ""
    fake_ocr_engine.confidence = 0.0
    pdf = make_pdf(["a page with a proper text layer on it", ""])

    document = PdfLoader(AppConfig(), ocr_engine=fake_ocr_engine).load(pdf)

    assert [page.number for page in document.pages] == [1]


def test_ocr_recovered_text_keeps_its_page_number(make_pdf, fake_ocr_engine):
    config = AppConfig()
    pdf = make_pdf(["a page with a proper text layer on it", "", ""])

    document = PdfLoader(config, ocr_engine=fake_ocr_engine).load(pdf, name="scan.pdf")
    chunks = TextSplitter(config).split(document)

    ocr_pages = {
        chunk.page_number for chunk in chunks if "recovered by OCR" in chunk.text
    }
    assert ocr_pages == {2, 3}


def test_pages_with_a_text_layer_are_not_sent_to_ocr(make_pdf, fake_ocr_engine):
    pdf = make_pdf(["a page with a proper text layer on it"])

    pages = PdfLoader(AppConfig(), ocr_engine=fake_ocr_engine).load(pdf).pages

    assert fake_ocr_engine.images == []
    assert "proper text layer" in pages[0].text
    assert not pages[0].used_ocr


def test_use_ocr_false_forces_the_text_layer_only_path(make_pdf, fake_ocr_engine):
    pdf = make_pdf(["a page with a proper text layer on it", ""])

    pages = PdfLoader(
        AppConfig(), use_ocr=False, ocr_engine=fake_ocr_engine
    ).load(pdf).pages

    assert [page.number for page in pages] == [1]
    assert fake_ocr_engine.images == []


def test_a_fully_scanned_pdf_yields_nothing_without_ocr(make_pdf):
    # The autouse fixture keeps OCR off, so this is the no-Tesseract machine:
    # nothing can be read, and the upload is refused rather than indexed empty.
    pdf = make_pdf(["", ""], name="scan.pdf")

    with pytest.raises(EmptyDocumentError):
        PdfLoader(AppConfig()).load(pdf)


def test_a_document_needing_too_much_ocr_is_refused(make_pdf, fake_ocr_engine):
    pdf = make_pdf(["", "", ""], name="long_scan.pdf")

    with pytest.raises(ScannedPdfTooLong) as caught:
        PdfLoader(AppConfig(max_ocr_pages=2), ocr_engine=fake_ocr_engine).load(pdf)

    assert "long_scan.pdf" in caught.value.message
    assert caught.value.hint
    assert fake_ocr_engine.images == []


def test_the_page_limit_does_not_apply_when_ocr_is_off(make_pdf):
    # No OCR means no long OCR pass to refuse — the pages are simply skipped,
    # which leaves nothing to load.
    pdf = make_pdf(["", "", ""], name="scan.pdf")

    with pytest.raises(EmptyDocumentError):
        PdfLoader(AppConfig(max_ocr_pages=1)).load(pdf)


# ── Choosing the right message ─────────────────────────────────────────────────

def test_a_scanned_pdf_without_ocr_says_so(monkeypatch):
    monkeypatch.setattr(ocr, "is_available", lambda: False)

    error = no_text_error("scan.pdf", scanned_pages=4)

    assert isinstance(error, OcrUnavailable)
    assert "4 page(s)" in error.message
    assert "tesseract" in error.hint.lower()


def test_a_scanned_pdf_that_ocr_could_not_read_suggests_rescanning(monkeypatch):
    monkeypatch.setattr(ocr, "is_available", lambda: True)

    error = no_text_error("scan.pdf", scanned_pages=4)

    assert not isinstance(error, OcrUnavailable)
    assert "300 DPI" in error.hint


def test_a_genuinely_empty_pdf_is_not_blamed_on_ocr():
    error = no_text_error("empty.pdf", scanned_pages=0)

    assert isinstance(error, NoTextInPdf)
    assert "genuinely empty" in error.message


def test_ocr_status_reports_availability(monkeypatch):
    monkeypatch.setattr(ocr, "tesseract_version", lambda: "5.3.0")
    assert "Tesseract 5.3.0" in ocr_status()

    monkeypatch.setattr(ocr, "tesseract_version", lambda: None)
    assert "not available" in ocr_status()


# ── The real implementation, exercised as far as it can be here ────────────────

def test_ocr_page_calls_pytesseract_with_the_rendered_image(monkeypatch):
    """
    Covers the body of ocr_page without a Tesseract binary: the page must be
    rendered at the configured resolution and the bitmap handed to pytesseract.
    """
    pytesseract = pytest.importorskip("pytesseract")

    rendered = object()
    resolutions = []

    class Page:
        def to_image(self, resolution):
            resolutions.append(resolution)
            return type("Img", (), {"original": rendered})()

    monkeypatch.setattr(ocr, "is_available", lambda: True)
    monkeypatch.setattr(
        pytesseract, "image_to_string", lambda image: "  scanned words  "
    )

    assert ocr.ocr_page(Page()) == "scanned words"
    assert resolutions == [ocr.OCR_RESOLUTION]
