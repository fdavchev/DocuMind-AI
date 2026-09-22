"""
One way of loading a file, two file types.

These tests are less about PDFs and text files than about the shape they
share: the steps around extraction are written once on DocumentLoader, and
every loader inherits them. So the same assertions are run against both
loaders in `test_both_loaders_*`, and the PDF-specific and text-specific tests
below only cover the one step each of them does differently.
"""

import io

import pytest

import ocr
from documind.config import AppConfig
from documind.documents.document_loader import DocumentLoader
from documind.documents.models import Document, ExtractedPage
from documind.documents.pdf_loader import PdfLoader
from documind.documents.text_loader import TextLoader
from errors import (
    EmptyDocumentError,
    FriendlyError,
    ScannedPdfTooLong,
    UnsupportedFileError,
)


class UploadedText(io.BytesIO):
    """Mimics the Streamlit UploadedFile duck type for a text upload."""

    def __init__(self, data: bytes, name: str = "notes.txt"):
        super().__init__(data)
        self.name = name


@pytest.fixture
def ocr_enabled(monkeypatch):
    """Pretend Tesseract is installed and reads every page as a fixed string."""
    monkeypatch.setattr(ocr, "is_available", lambda: True)
    monkeypatch.setattr(ocr, "ocr_page", lambda page: "text recovered by OCR")


@pytest.fixture
def make_txt():
    """make_txt("file contents", name="notes.md")"""

    def _make(text: str, name: str = "notes.txt", encoding: str = "utf-8"):
        return UploadedText(text.encode(encoding), name)

    return _make


# ── The abstract base class enforces its contract ──────────────────────────────

def test_the_base_loader_cannot_be_instantiated():
    with pytest.raises(TypeError):
        DocumentLoader(AppConfig())


def test_a_loader_that_does_not_extract_pages_cannot_be_instantiated():
    class ForgetfulLoader(DocumentLoader):
        SUPPORTED_EXTENSIONS = (".txt",)

    with pytest.raises(TypeError):
        ForgetfulLoader(AppConfig())


# ── The template method, exercised through a minimal subclass ──────────────────

class StubLoader(DocumentLoader):
    """A loader whose extraction step is whatever the test hands it."""

    SUPPORTED_EXTENSIONS = (".stub",)
    DEFAULT_NAME = "document.stub"

    def __init__(self, config: AppConfig, pages: list[ExtractedPage]):
        super().__init__(config)
        self._pages = pages

    def _extract_pages(self, file) -> list[ExtractedPage]:
        return self._pages


def _stub(*texts: str) -> StubLoader:
    pages = [
        ExtractedPage(number=number, text=text, used_ocr=False)
        for number, text in enumerate(texts, start=1)
    ]
    return StubLoader(AppConfig(), pages)


def test_load_wraps_the_extracted_pages_in_a_document():
    document = _stub("first page", "second page").load(io.BytesIO(), name="a.stub")

    assert isinstance(document, Document)
    assert document.page_count == 2
    assert document.name == "a.stub"


def test_load_names_the_document_after_the_upload():
    upload = UploadedText(b"", name="annual_report.stub")

    assert _stub("content").load(upload).name == "annual_report.stub"


def test_an_explicit_name_wins_over_the_uploads_own():
    upload = UploadedText(b"", name="upload_tmp_1234.stub")

    assert _stub("content").load(upload, name="thesis.stub").name == "thesis.stub"


def test_a_file_object_with_no_name_falls_back_to_the_loaders_default():
    assert _stub("content").load(io.BytesIO()).name == "document.stub"


def test_load_refuses_a_file_type_this_loader_does_not_handle():
    with pytest.raises(UnsupportedFileError) as caught:
        _stub("content").load(io.BytesIO(), name="report.docx")

    assert "report.docx" in caught.value.message
    assert ".stub" in caught.value.hint


def test_load_refuses_a_file_that_yielded_no_pages():
    with pytest.raises(EmptyDocumentError) as caught:
        _stub().load(io.BytesIO(), name="blank.stub")

    assert "blank.stub" in caught.value.message
    assert caught.value.hint


def test_load_refuses_a_file_whose_pages_are_only_whitespace():
    with pytest.raises(EmptyDocumentError):
        _stub("   ", "\n\n").load(io.BytesIO(), name="blank.stub")


def test_both_new_errors_are_friendly_errors():
    # They belong to the project's one exception hierarchy, so app.py's existing
    # `except FriendlyError: render it` handler already covers them.
    assert isinstance(EmptyDocumentError("a.pdf"), FriendlyError)
    assert isinstance(UnsupportedFileError("a.docx"), FriendlyError)


# ── supports() answers by extension, without building anything ─────────────────

def test_supports_matches_the_declared_extensions():
    assert PdfLoader.supports("report.pdf")
    assert TextLoader.supports("notes.txt")
    assert TextLoader.supports("README.md")


def test_supports_ignores_the_case_of_the_extension():
    assert PdfLoader.supports("REPORT.PDF")
    assert TextLoader.supports("NOTES.TXT")


def test_supports_rejects_another_loaders_file_type():
    assert not PdfLoader.supports("notes.txt")
    assert not TextLoader.supports("report.pdf")
    assert not PdfLoader.supports("report.docx")


def test_supports_is_answerable_without_building_a_loader():
    # A classmethod, so no AppConfig and no instance are needed to ask — which
    # is what lets a factory pick the right loader before constructing one.
    chosen = next(
        loader for loader in (PdfLoader, TextLoader) if loader.supports("notes.md")
    )

    assert chosen is TextLoader


# ── The same calls against both loaders ────────────────────────────────────────

def _both_loaders(make_pdf, make_txt):
    """(loader, upload) pairs holding the same sentence in two file formats."""
    sentence = "The budget was approved in March."
    return [
        (PdfLoader(AppConfig()), make_pdf([sentence], name="report.pdf")),
        (TextLoader(AppConfig()), make_txt(sentence, name="report.txt")),
    ]


def test_both_loaders_return_a_document_from_the_same_call(make_pdf, make_txt):
    for loader, upload in _both_loaders(make_pdf, make_txt):
        document = loader.load(upload)

        assert isinstance(document, Document)
        assert "budget was approved" in document.text
        assert document.page_count >= 1
        assert not document.is_empty


def test_both_loaders_name_the_document_after_the_upload(make_pdf, make_txt):
    for loader, upload in _both_loaders(make_pdf, make_txt):
        assert loader.load(upload).name == upload.name


def test_both_loaders_refuse_an_empty_file_the_same_way(make_pdf, make_txt):
    empties = [
        (PdfLoader(AppConfig()), make_pdf([""], name="blank.pdf")),
        (TextLoader(AppConfig()), make_txt("   \n  ", name="blank.txt")),
    ]

    for loader, upload in empties:
        with pytest.raises(EmptyDocumentError):
            loader.load(upload)


def test_both_loaders_refuse_the_other_ones_file_type(make_pdf, make_txt):
    with pytest.raises(UnsupportedFileError):
        PdfLoader(AppConfig()).load(make_txt("text", name="notes.txt"))

    with pytest.raises(UnsupportedFileError):
        TextLoader(AppConfig()).load(make_pdf(["text"], name="report.pdf"))


# ── PdfLoader: the one step it does differently ────────────────────────────────

def test_pdf_pages_keep_one_based_page_numbers(make_pdf):
    document = PdfLoader(AppConfig()).load(make_pdf(["Alpha", "Beta", "Gamma"]))

    assert [page.number for page in document.pages] == [1, 2, 3]
    assert "Beta" in {page.number: page.text for page in document.pages}[2]


def test_pdf_pages_with_no_text_are_skipped(make_pdf):
    document = PdfLoader(AppConfig()).load(make_pdf(["Alpha content", "", "Gamma"]))

    assert [page.number for page in document.pages] == [1, 3]


def test_a_text_layer_page_is_not_marked_as_ocr(make_pdf):
    document = PdfLoader(AppConfig()).load(
        make_pdf(["a page with a proper text layer on it"])
    )

    assert [page.used_ocr for page in document.pages] == [False]
    assert document.pages[0].ocr_confidence is None


def test_a_scanned_page_is_recovered_by_ocr(make_pdf, ocr_enabled):
    pdf = make_pdf(["a page with a proper text layer on it", ""], name="scan.pdf")

    document = PdfLoader(AppConfig()).load(pdf)

    assert document.pages[1].text == "text recovered by OCR"
    assert [page.used_ocr for page in document.pages] == [False, True]
    assert document.ocr_page_count == 1


def test_pages_with_a_text_layer_are_not_sent_to_ocr(make_pdf, monkeypatch):
    monkeypatch.setattr(ocr, "is_available", lambda: True)
    calls = []
    monkeypatch.setattr(ocr, "ocr_page", lambda page: calls.append(page) or "unused")

    PdfLoader(AppConfig()).load(make_pdf(["a page with a proper text layer on it"]))

    assert calls == []


def test_use_ocr_false_forces_the_text_layer_only_path(make_pdf, ocr_enabled):
    pdf = make_pdf(["a page with a proper text layer on it", ""])

    document = PdfLoader(AppConfig(), use_ocr=False).load(pdf)

    assert [page.number for page in document.pages] == [1]


def test_a_document_needing_too_much_ocr_is_refused(make_pdf, ocr_enabled):
    pdf = make_pdf(["", "", ""], name="long_scan.pdf")

    with pytest.raises(ScannedPdfTooLong) as caught:
        PdfLoader(AppConfig(max_ocr_pages=2)).load(pdf)

    assert "long_scan.pdf" in caught.value.message
    assert caught.value.hint


def test_the_ocr_threshold_is_the_documented_one(make_pdf, ocr_enabled):
    # A page holding fewer characters than MIN_CHARS_FOR_TEXT_LAYER has no
    # usable text layer, however many characters extract_text() returned.
    thin = "x" * (ocr.MIN_CHARS_FOR_TEXT_LAYER - 1)
    thick = "y" * ocr.MIN_CHARS_FOR_TEXT_LAYER

    document = PdfLoader(AppConfig()).load(make_pdf([thin, thick]))

    assert document.pages[0].text == "text recovered by OCR"
    assert document.pages[0].used_ocr
    assert document.pages[1].text.startswith("y")
    assert not document.pages[1].used_ocr


def test_the_page_limit_does_not_apply_when_ocr_is_off(make_pdf):
    # No OCR means no long OCR pass to refuse — the pages are simply skipped,
    # which leaves nothing to load.
    pdf = make_pdf(["", "", ""], name="scan.pdf")

    with pytest.raises(EmptyDocumentError):
        PdfLoader(AppConfig(max_ocr_pages=1)).load(pdf)


def test_scanned_page_count_counts_only_pages_without_a_text_layer(make_pdf):
    pdf = make_pdf(["a page with a proper text layer on it", "", "- 3 -"])

    assert PdfLoader(AppConfig()).scanned_page_count(pdf) == 2


# ── TextLoader: the one step it does differently ───────────────────────────────

def test_a_text_file_is_one_page(make_txt):
    document = TextLoader(AppConfig()).load(make_txt("line one\nline two"))

    assert document.page_count == 1
    assert document.pages[0].number == 1
    assert not document.pages[0].used_ocr
    assert document.text == "line one\nline two"


def test_a_utf8_file_keeps_its_macedonian_text(make_txt):
    document = TextLoader(AppConfig()).load(make_txt("Извештај за проектот"))

    assert "Извештај" in document.text


def test_a_cp1251_file_is_decoded_by_the_fallback(make_txt):
    # Older Macedonian documents are Windows-1251; those bytes are not valid
    # UTF-8, so the first attempt raises and the second one reads it.
    document = TextLoader(AppConfig()).load(
        make_txt("Извештај за проектот", name="stari.txt", encoding="cp1251")
    )

    assert "Извештај" in document.text


def test_a_markdown_file_loads_the_same_way(make_txt):
    document = TextLoader(AppConfig()).load(make_txt("# Heading\n\nBody", name="a.md"))

    assert document.name == "a.md"
    assert "# Heading" in document.text


def test_a_text_file_read_once_already_still_loads(make_txt):
    upload = make_txt("some content")
    upload.read()  # e.g. a size check, or a loader that was asked first

    assert "some content" in TextLoader(AppConfig()).load(upload).text
