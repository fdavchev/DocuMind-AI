"""Extraction and chunking: does page provenance survive the pipeline?"""

from pdf_handler import (
    CHUNK_SIZE,
    extract_pages_from_pdf,
    extract_text_from_pdf,
    load_pdf_as_documents,
    split_pages_into_chunks,
    split_text_into_chunks,
)


def test_extract_pages_keeps_one_based_page_numbers(make_pdf):
    pdf = make_pdf(["Alpha content", "Beta content", "Gamma content"])

    pages = extract_pages_from_pdf(pdf)

    assert [number for number, _ in pages] == [1, 2, 3]
    assert "Beta" in dict(pages)[2]


def test_extract_pages_skips_pages_with_no_text(make_pdf):
    # The middle page is blank — a scanned page behaves the same way.
    pdf = make_pdf(["Alpha content", "", "Gamma content"])

    pages = extract_pages_from_pdf(pdf)

    assert [number for number, _ in pages] == [1, 3]


def test_extract_text_returns_every_page_joined(make_pdf):
    pdf = make_pdf(["Alpha content", "Beta content"])

    text = extract_text_from_pdf(pdf)

    assert "Alpha content" in text
    assert "Beta content" in text


def test_extract_text_of_image_only_pdf_is_empty(make_pdf):
    pdf = make_pdf([""])

    assert extract_text_from_pdf(pdf).strip() == ""


def test_split_text_into_chunks_respects_chunk_size():
    text = "word " * 400  # ~2000 characters

    chunks = split_text_into_chunks(text)

    assert len(chunks) > 1
    assert all(len(chunk) <= CHUNK_SIZE for chunk in chunks)


def test_split_pages_tags_every_chunk_with_source_and_page():
    pages = [(1, "First page text."), (7, "Seventh page text.")]

    documents = split_pages_into_chunks(pages, source="report.pdf")

    assert {doc.metadata["source"] for doc in documents} == {"report.pdf"}
    assert {doc.metadata["page"] for doc in documents} == {1, 7}


def test_chunks_from_a_long_page_all_carry_that_page_number():
    long_page = "sentence about budgets. " * 100  # forces several chunks

    documents = split_pages_into_chunks([(4, long_page)], source="report.pdf")

    assert len(documents) > 1
    assert all(doc.metadata["page"] == 4 for doc in documents)


def test_no_chunk_spans_two_pages():
    # Page-by-page splitting is what makes "p. 4" honest — a chunk built from
    # both pages would make the citation ambiguous.
    pages = [(1, "unique_alpha_marker " * 30), (2, "unique_beta_marker " * 30)]

    documents = split_pages_into_chunks(pages, source="report.pdf")

    for doc in documents:
        has_alpha = "unique_alpha_marker" in doc.page_content
        has_beta = "unique_beta_marker" in doc.page_content
        assert not (has_alpha and has_beta)


def test_load_pdf_as_documents_defaults_source_to_filename(make_pdf):
    pdf = make_pdf(["Alpha content", "Beta content"], name="annual_report.pdf")

    documents = load_pdf_as_documents(pdf)

    assert documents
    assert all(doc.metadata["source"] == "annual_report.pdf" for doc in documents)
    assert sorted({doc.metadata["page"] for doc in documents}) == [1, 2]


def test_load_pdf_as_documents_accepts_an_explicit_source(make_pdf):
    pdf = make_pdf(["Alpha content"], name="upload_tmp_1234.pdf")

    documents = load_pdf_as_documents(pdf, source="thesis.pdf")

    assert all(doc.metadata["source"] == "thesis.pdf" for doc in documents)


def test_load_pdf_as_documents_returns_empty_for_image_only_pdf(make_pdf):
    pdf = make_pdf(["", ""])

    assert load_pdf_as_documents(pdf) == []
