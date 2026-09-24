"""
Cutting a Document into Chunks: does every passage keep an honest page number?

The invariant these tests exist for is DECISIONS.md #1 — each page is split on
its own, so no chunk is ever assembled from two pages and every citation points
at exactly one of them. The rest pin the configured chunk size, the provenance
carried on each Chunk, and the shape of the edge cases (blank pages, an empty
document, fragments with almost no letters) that must never reach the index.
"""

import dataclasses

from documind.config import AppConfig
from documind.documents.models import Chunk, Document, ExtractedPage
from documind.documents.text_splitter import TextSplitter


def _document(*pages, name="report.pdf") -> Document:
    """A Document built straight from (page_number, text) pairs."""
    return Document(
        name=name,
        pages=tuple(
            ExtractedPage(number=number, text=text, used_ocr=False)
            for number, text in pages
        ),
    )


def _splitter(**overrides) -> TextSplitter:
    return TextSplitter(dataclasses.replace(AppConfig(), **overrides))


def _shared_edge_length(first: str, second: str) -> int:
    """How many characters at the end of `first` reappear at the start of `second`."""
    for length in range(min(len(first), len(second)), 0, -1):
        if first[-length:] == second[:length]:
            return length
    return 0


# ── The page-boundary invariant (DECISIONS.md #1) ──────────────────────────────

def test_no_chunk_spans_two_pages():
    # Page-by-page splitting is what makes "p. 4" honest — a chunk built from
    # both pages would make the citation ambiguous.
    document = _document(
        (1, "unique_alpha_marker " * 30), (2, "unique_beta_marker " * 30)
    )

    for chunk in _splitter().split(document):
        has_alpha = "unique_alpha_marker" in chunk.text
        has_beta = "unique_beta_marker" in chunk.text
        assert not (has_alpha and has_beta)


def test_no_chunk_spans_two_pages_even_when_pages_are_short():
    # Short pages are the tempting case: a splitter fed the whole document at
    # once would happily pack all three into one chunk.
    document = _document((1, "alpha_marker"), (2, "beta_marker"), (3, "gamma_marker"))

    chunks = _splitter().split(document)

    assert len(chunks) == 3
    for chunk in chunks:
        markers = [
            marker
            for marker in ("alpha_marker", "beta_marker", "gamma_marker")
            if marker in chunk.text
        ]
        assert len(markers) == 1


def test_chunks_from_a_long_page_all_carry_that_page_number():
    long_page = "sentence about budgets. " * 100  # forces several chunks

    chunks = _splitter().split(_document((4, long_page)))

    assert len(chunks) > 1
    assert all(chunk.page_number == 4 for chunk in chunks)


# ── Provenance ─────────────────────────────────────────────────────────────────

def test_every_chunk_is_tagged_with_its_source_and_page():
    document = _document((1, "First page text."), (7, "Seventh page text."))

    chunks = _splitter().split(document)

    assert {chunk.source_document for chunk in chunks} == {"report.pdf"}
    assert {chunk.page_number for chunk in chunks} == {1, 7}


def test_the_source_is_the_document_name_not_the_filename_on_disk():
    document = _document((1, "Some text."), name="thesis.pdf")

    assert all(
        chunk.source_document == "thesis.pdf" for chunk in _splitter().split(document)
    )


def test_it_returns_chunk_objects():
    chunks = _splitter().split(_document((1, "Some text.")))

    assert chunks
    assert all(isinstance(chunk, Chunk) for chunk in chunks)


def test_page_order_is_preserved():
    document = _document((1, "alpha"), (2, "beta"), (3, "gamma"))

    assert [chunk.page_number for chunk in _splitter().split(document)] == [1, 2, 3]


# ── Chunk size comes from config ───────────────────────────────────────────────

def test_chunks_respect_the_configured_size():
    long_page = "word " * 400  # ~2000 characters

    chunks = _splitter().split(_document((1, long_page)))

    assert len(chunks) > 1
    assert all(len(chunk.text) <= AppConfig().chunk_size for chunk in chunks)


def test_a_smaller_configured_size_produces_more_chunks():
    long_page = "word " * 400

    wide = _splitter(chunk_size=500, chunk_overlap=50).split(_document((1, long_page)))
    narrow = _splitter(chunk_size=100, chunk_overlap=10).split(
        _document((1, long_page))
    )

    assert len(narrow) > len(wide)
    assert all(len(chunk.text) <= 100 for chunk in narrow)


def test_consecutive_chunks_overlap_by_at_most_the_configured_amount():
    # RecursiveCharacterTextSplitter only cuts on whole separator units (here,
    # whole words), so the shared text at a chunk boundary is trimmed to the
    # nearest word and is rarely exactly chunk_overlap — it is guaranteed to be
    # no more than that.
    long_page = " ".join(f"word{i:03d}" for i in range(200))
    chunk_overlap = 20

    chunks = _splitter(chunk_size=100, chunk_overlap=chunk_overlap).split(
        _document((1, long_page))
    )

    assert len(chunks) > 2
    for first, second in zip(chunks, chunks[1:]):
        overlap = _shared_edge_length(first.text, second.text)
        assert 0 < overlap <= chunk_overlap


def test_split_text_cuts_a_bare_string_with_no_provenance():
    chunks = _splitter().split_text("word " * 400)

    assert len(chunks) > 1
    assert all(isinstance(chunk, str) for chunk in chunks)
    assert all(len(chunk) <= AppConfig().chunk_size for chunk in chunks)


def test_a_short_page_stays_one_chunk():
    chunks = _splitter().split(_document((1, "Short enough to fit.")))

    assert len(chunks) == 1
    assert chunks[0].text == "Short enough to fit."


# ── Edge cases ─────────────────────────────────────────────────────────────────

def test_an_empty_document_produces_no_chunks():
    assert _splitter().split(Document(name="blank.pdf", pages=())) == []


def test_a_whitespace_only_page_produces_no_chunks():
    assert _splitter().split(_document((1, "   \n\n  "))) == []


def test_a_page_with_almost_no_letters_produces_no_chunks():
    # A lone ")" or a page number embeds as a generic vector that falsely
    # matches many questions, so it must never reach the index.
    document = _document((1, "alpha_marker"), (2, ")"), (3, "12 ."), (4, "gamma_marker"))

    assert [chunk.page_number for chunk in _splitter().split(document)] == [1, 4]


def test_a_short_page_with_enough_letters_is_kept_in_any_alphabet():
    document = _document((1, "Fig"), (2, "Шум"))

    assert [chunk.page_number for chunk in _splitter().split(document)] == [1, 2]


def test_the_minimum_letter_count_comes_from_config():
    document = _document((1, "Fig"))

    assert _splitter(min_chunk_letters=4).split(document) == []


def test_a_blank_page_between_two_real_ones_is_skipped():
    document = _document((1, "alpha_marker"), (2, "  "), (3, "gamma_marker"))

    assert [chunk.page_number for chunk in _splitter().split(document)] == [1, 3]


def test_the_splitter_can_be_reused_across_documents():
    # One instance is held for the life of the app, so splitting must not depend
    # on what it was handed last.
    splitter = _splitter()
    first = splitter.split(_document((1, "alpha text"), name="one.pdf"))
    second = splitter.split(_document((1, "beta text"), name="two.pdf"))

    assert splitter.split(_document((1, "alpha text"), name="one.pdf")) == first
    assert {chunk.source_document for chunk in second} == {"two.pdf"}


def test_chunks_are_immutable():
    # Frozen Chunks mean the passage the vector store indexes is the passage the
    # splitter created.
    chunk = _splitter().split(_document((1, "Some text.")))[0]

    try:
        chunk.text = "rewritten"
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Chunk should be immutable")
