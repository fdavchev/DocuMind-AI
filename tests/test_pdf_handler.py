"""Extraction and chunking: does page provenance survive the pipeline?"""

from documind.config import AppConfig
from documind.documents.models import Document, ExtractedPage
from pdf_handler import (
    extract_pages_from_pdf,
    extract_text_from_pdf,
    load_pdf_as_chunks,
    load_pdf_as_document,
    split_document_into_chunks,
    split_text_into_chunks,
)


def _document(*pages, name="report.pdf") -> Document:
    """A Document built straight from (page_number, text) pairs."""
    return Document(
        name=name,
        pages=tuple(
            ExtractedPage(number=number, text=text, used_ocr=False)
            for number, text in pages
        ),
    )


def test_extract_pages_keeps_one_based_page_numbers(make_pdf):
    pdf = make_pdf(["Alpha content", "Beta content", "Gamma content"])

    pages = extract_pages_from_pdf(pdf)

    assert [page.number for page in pages] == [1, 2, 3]
    assert "Beta" in {page.number: page.text for page in pages}[2]


def test_extract_pages_skips_pages_with_no_text(make_pdf):
    # The middle page is blank — a scanned page behaves the same way.
    pdf = make_pdf(["Alpha content", "", "Gamma content"])

    pages = extract_pages_from_pdf(pdf)

    assert [page.number for page in pages] == [1, 3]


def test_extract_pages_marks_text_layer_pages_as_not_ocr(make_pdf):
    pdf = make_pdf(["a page with a proper text layer on it"])

    pages = extract_pages_from_pdf(pdf)

    assert [page.used_ocr for page in pages] == [False]
    # No confidence scoring exists yet — the field is reserved, not populated.
    assert pages[0].ocr_confidence is None


def test_extract_text_returns_every_page_joined(make_pdf):
    pdf = make_pdf(["Alpha content", "Beta content"])

    text = extract_text_from_pdf(pdf)

    assert "Alpha content" in text
    assert "Beta content" in text


def test_extract_text_of_image_only_pdf_is_empty(make_pdf):
    pdf = make_pdf([""])

    assert extract_text_from_pdf(pdf).strip() == ""


# ── The Document value object ──────────────────────────────────────────────────

def test_load_pdf_as_document_names_the_document_after_the_upload(make_pdf):
    pdf = make_pdf(["Alpha content", "Beta content"], name="annual_report.pdf")

    document = load_pdf_as_document(pdf)

    assert document.name == "annual_report.pdf"
    assert document.page_count == 2
    assert [page.number for page in document.pages] == [1, 2]


def test_load_pdf_as_document_accepts_an_explicit_name(make_pdf):
    pdf = make_pdf(["Alpha content"], name="upload_tmp_1234.pdf")

    assert load_pdf_as_document(pdf, name="thesis.pdf").name == "thesis.pdf"


def test_document_text_joins_every_page(make_pdf):
    pdf = make_pdf(["Alpha content", "Beta content"])

    text = load_pdf_as_document(pdf).text

    assert "Alpha content" in text
    assert "Beta content" in text


def test_an_image_only_document_reports_itself_empty(make_pdf):
    pdf = make_pdf(["", ""])

    document = load_pdf_as_document(pdf)

    assert document.is_empty
    assert document.page_count == 0


def test_a_readable_document_is_not_empty(make_pdf):
    assert not load_pdf_as_document(make_pdf(["Alpha content"])).is_empty


def test_ocr_page_count_counts_only_pages_read_by_ocr():
    document = Document(
        name="scan.pdf",
        pages=(
            ExtractedPage(number=1, text="text layer", used_ocr=False),
            ExtractedPage(number=2, text="recovered", used_ocr=True),
            ExtractedPage(number=3, text="recovered", used_ocr=True),
        ),
    )

    assert document.page_count == 3
    assert document.ocr_page_count == 2


# ── Chunking ───────────────────────────────────────────────────────────────────

def test_split_text_into_chunks_respects_chunk_size():
    text = "word " * 400  # ~2000 characters

    chunks = split_text_into_chunks(text)

    assert len(chunks) > 1
    assert all(len(chunk) <= AppConfig().chunk_size for chunk in chunks)


def test_split_document_tags_every_chunk_with_source_and_page():
    document = _document((1, "First page text."), (7, "Seventh page text."))

    chunks = split_document_into_chunks(document)

    assert {chunk.source_document for chunk in chunks} == {"report.pdf"}
    assert {chunk.page_number for chunk in chunks} == {1, 7}


def test_chunks_from_a_long_page_all_carry_that_page_number():
    long_page = "sentence about budgets. " * 100  # forces several chunks

    chunks = split_document_into_chunks(_document((4, long_page)))

    assert len(chunks) > 1
    assert all(chunk.page_number == 4 for chunk in chunks)


def test_no_chunk_spans_two_pages():
    # Page-by-page splitting is what makes "p. 4" honest — a chunk built from
    # both pages would make the citation ambiguous.
    document = _document(
        (1, "unique_alpha_marker " * 30), (2, "unique_beta_marker " * 30)
    )

    for chunk in split_document_into_chunks(document):
        has_alpha = "unique_alpha_marker" in chunk.text
        has_beta = "unique_beta_marker" in chunk.text
        assert not (has_alpha and has_beta)


def test_load_pdf_as_chunks_defaults_the_source_to_the_filename(make_pdf):
    pdf = make_pdf(["Alpha content", "Beta content"], name="annual_report.pdf")

    chunks = load_pdf_as_chunks(pdf)

    assert chunks
    assert all(chunk.source_document == "annual_report.pdf" for chunk in chunks)
    assert sorted({chunk.page_number for chunk in chunks}) == [1, 2]


def test_load_pdf_as_chunks_accepts_an_explicit_source(make_pdf):
    pdf = make_pdf(["Alpha content"], name="upload_tmp_1234.pdf")

    chunks = load_pdf_as_chunks(pdf, name="thesis.pdf")

    assert all(chunk.source_document == "thesis.pdf" for chunk in chunks)


def test_load_pdf_as_chunks_returns_empty_for_image_only_pdf(make_pdf):
    pdf = make_pdf(["", ""])

    assert load_pdf_as_chunks(pdf) == []
