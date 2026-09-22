"""
One place that knows which loader reads which file.

These tests are about dispatch, not about reading files — the loaders' own
behaviour is pinned in test_document_loader.py. What matters here is that the
right loader comes back for a filename, that it arrives already configured, and
that a format nobody handles is refused with a message naming the ones that do.
The last group is the open-closed check: a loader the factory has never heard of
is dispatched to without changing a line of the dispatch code.
"""

import io

import pytest

import ocr
from documind.config import AppConfig
from documind.documents.document_loader import DocumentLoader
from documind.documents.loader_factory import LoaderFactory
from documind.documents.models import Document, ExtractedPage
from documind.documents.pdf_loader import PdfLoader
from documind.documents.text_loader import TextLoader
from errors import FriendlyError, ScannedPdfTooLong, UnsupportedFileError


@pytest.fixture
def factory():
    return LoaderFactory(AppConfig())


@pytest.fixture
def ocr_enabled(monkeypatch):
    """Pretend Tesseract is installed and reads every page as a fixed string."""
    monkeypatch.setattr(ocr, "is_available", lambda: True)
    monkeypatch.setattr(ocr, "ocr_page", lambda page: "text recovered by OCR")


@pytest.fixture
def make_txt():
    """make_txt("file contents", name="notes.md")"""

    def _make(text: str, name: str = "notes.txt"):
        upload = io.BytesIO(text.encode("utf-8"))
        upload.name = name
        return upload

    return _make


# ── The right loader for the filename ──────────────────────────────────────────

def test_a_pdf_gets_the_pdf_loader(factory):
    assert isinstance(factory.create_loader("report.pdf"), PdfLoader)


def test_a_text_file_gets_the_text_loader(factory):
    assert isinstance(factory.create_loader("notes.txt"), TextLoader)


def test_a_markdown_file_gets_the_text_loader(factory):
    assert isinstance(factory.create_loader("README.md"), TextLoader)


def test_dispatch_ignores_the_case_of_the_extension(factory):
    assert isinstance(factory.create_loader("REPORT.PDF"), PdfLoader)
    assert isinstance(factory.create_loader("NOTES.MD"), TextLoader)


def test_a_full_path_dispatches_on_its_extension(factory):
    assert isinstance(factory.create_loader("C:/uploads/2026/q1.pdf"), PdfLoader)


def test_every_loader_it_returns_is_a_document_loader(factory):
    # The caller only ever needs the base type — which is what lets the upload
    # handler hold the result without knowing what was uploaded.
    for filename in ("report.pdf", "notes.txt", "README.md"):
        assert isinstance(factory.create_loader(filename), DocumentLoader)


def test_each_call_returns_a_fresh_loader(factory):
    assert factory.create_loader("a.pdf") is not factory.create_loader("b.pdf")


# ── The loader comes back already configured ───────────────────────────────────

def test_the_loader_is_built_with_the_factorys_config(make_pdf, ocr_enabled):
    # max_ocr_pages only reaches the loader through the factory's AppConfig, so
    # the refusal below is proof the config was passed through.
    factory = LoaderFactory(AppConfig(max_ocr_pages=2))
    pdf = make_pdf(["", "", ""], name="long_scan.pdf")

    with pytest.raises(ScannedPdfTooLong):
        factory.create_loader("long_scan.pdf").load(pdf)


def test_the_loader_it_returns_actually_loads_the_file(factory, make_pdf, make_txt):
    uploads = [
        make_pdf(["The budget was approved in March."], name="report.pdf"),
        make_txt("The budget was approved in March.", name="report.txt"),
    ]

    for upload in uploads:
        document = factory.create_loader(upload.name).load(upload)

        assert isinstance(document, Document)
        assert "budget was approved" in document.text


# ── Anything else is refused, with the supported formats named ─────────────────

def test_an_unknown_file_type_is_refused(factory):
    with pytest.raises(UnsupportedFileError) as caught:
        factory.create_loader("report.docx")

    assert "report.docx" in caught.value.message


def test_the_refusal_names_the_formats_that_would_have_worked(factory):
    with pytest.raises(UnsupportedFileError) as caught:
        factory.create_loader("photo.png")

    for extension in (".pdf", ".txt", ".md"):
        assert extension in caught.value.hint


def test_a_file_with_no_extension_is_refused(factory):
    with pytest.raises(UnsupportedFileError):
        factory.create_loader("README")


def test_the_refusal_is_a_friendly_error(factory):
    # app.py's one "catch a friendly error, render it" handler already covers
    # this, so no new UI code is needed for an unsupported upload.
    with pytest.raises(FriendlyError):
        factory.create_loader("archive.zip")


# ── The list of formats is read off the loaders, not written down here ─────────

def test_supported_extensions_covers_every_registered_loader():
    assert set(LoaderFactory.supported_extensions()) == {".pdf", ".txt", ".md"}


def test_supported_extensions_is_answerable_without_a_config():
    # A classmethod, so the file-uploader widget can ask which types to accept
    # before anything has been built.
    assert ".pdf" in LoaderFactory.supported_extensions()


def test_every_supported_extension_dispatches_to_a_loader(factory):
    for extension in LoaderFactory.supported_extensions():
        assert isinstance(factory.create_loader(f"file{extension}"), DocumentLoader)


# ── Open-closed: a new format is a registry entry, not a code change ───────────

class HtmlLoader(DocumentLoader):
    """A format the factory has never heard of, written for this test alone."""

    SUPPORTED_EXTENSIONS = (".html",)
    DEFAULT_NAME = "document.html"

    def _extract_pages(self, file) -> list[ExtractedPage]:
        return [ExtractedPage(number=1, text="<h1>Hello</h1>", used_ocr=False)]


class HtmlAwareFactory(LoaderFactory):
    LOADERS = LoaderFactory.LOADERS + (HtmlLoader,)


def test_a_newly_registered_loader_is_dispatched_to():
    # Nothing in create_loader changed — it asks each registered loader whether
    # it supports the file, and HtmlLoader answers for itself.
    factory = HtmlAwareFactory(AppConfig())

    assert isinstance(factory.create_loader("page.html"), HtmlLoader)


def test_registering_a_loader_widens_the_supported_formats():
    assert ".html" in HtmlAwareFactory.supported_extensions()
    assert ".html" not in LoaderFactory.supported_extensions()


def test_registering_a_loader_does_not_disturb_the_existing_ones():
    factory = HtmlAwareFactory(AppConfig())

    assert isinstance(factory.create_loader("report.pdf"), PdfLoader)
    assert isinstance(factory.create_loader("notes.txt"), TextLoader)


def test_an_unregistered_format_is_still_refused_by_the_wider_factory():
    with pytest.raises(UnsupportedFileError):
        HtmlAwareFactory(AppConfig()).create_loader("report.docx")
