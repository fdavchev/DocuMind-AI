"""
The VectorStore class: indexing, retrieval, and the Chunk round trip.

The promise these pin is that nothing outside this class ever handles a
LangChain Document: Chunks go in and Chunks come back, with their page and
filename intact.
"""

import pytest

from documind.config import AppConfig
from documind.documents.models import Chunk
from documind.documents.pdf_loader import PdfLoader
from documind.documents.text_splitter import TextSplitter
from documind.rag.vector_store import VectorStore


def _chunks(*triples) -> list[Chunk]:
    return [
        Chunk(text=text, source_document=source, page_number=page)
        for text, source, page in triples
    ]


FINANCE = ("the budget forecast for the quarter", "finance.pdf", 2)
SAFETY = ("the safety procedures for the lab", "safety.pdf", 5)


@pytest.fixture
def store(fake_embeddings):
    return VectorStore(AppConfig(), embeddings=fake_embeddings)


# ── Building ──────────────────────────────────────────────────────────────────

def test_a_new_store_is_not_ready(store):
    assert store.is_ready is False


def test_build_indexes_every_chunk(store):
    store.build(_chunks(FINANCE, SAFETY))

    assert store.is_ready is True
    assert len(store._store.docstore._dict) == 2


def test_build_replaces_whatever_was_indexed_before(store):
    store.build(_chunks(FINANCE))
    store.build(_chunks(SAFETY))

    assert store.sources == ("safety.pdf",)


def test_add_extends_the_same_index(store):
    store.build(_chunks(FINANCE))
    store.add(_chunks(SAFETY))

    assert len(store._store.docstore._dict) == 2
    assert store.sources == ("finance.pdf", "safety.pdf")


def test_add_to_an_empty_store_builds_it(store):
    # The caller never has to ask whether this upload is the first one.
    store.add(_chunks(FINANCE))

    assert store.is_ready is True
    assert store.sources == ("finance.pdf",)


# ── Removing one document ─────────────────────────────────────────────────────

def test_remove_drops_the_file_from_sources(store):
    store.build(_chunks(FINANCE, SAFETY))

    store.remove("finance.pdf")

    assert store.sources == ("safety.pdf",)


def test_remove_leaves_the_other_file_searchable(store):
    store.build(_chunks(FINANCE, SAFETY))

    store.remove("finance.pdf")
    hits = store.search("budget forecast quarter", k=4)

    assert [hit.source_document for hit in hits] == ["safety.pdf"]


def test_remove_takes_every_chunk_of_that_file(store):
    store.build(_many("a.pdf", 5) + _many("b.pdf", 3))

    store.remove("a.pdf")

    assert store.sources == ("b.pdf",)
    assert len(store.search("text", k=10)) == 3


def test_removing_the_only_file_leaves_the_store_not_ready(store):
    store.build(_chunks(FINANCE))

    store.remove("finance.pdf")

    assert store.is_ready is False
    assert store.sources == ()


def test_a_store_emptied_by_remove_can_be_added_to_again(store):
    store.build(_chunks(FINANCE))
    store.remove("finance.pdf")

    store.add(_chunks(SAFETY))

    assert store.sources == ("safety.pdf",)


def test_removing_a_file_that_is_not_indexed_changes_nothing(store):
    store.build(_chunks(FINANCE))

    store.remove("never-uploaded.pdf")

    assert store.sources == ("finance.pdf",)


def test_removing_from_an_empty_store_changes_nothing(store):
    store.remove("finance.pdf")

    assert store.is_ready is False


# ── Searching returns Chunks, not library objects ─────────────────────────────

def test_search_returns_chunk_objects(store):
    store.build(_chunks(FINANCE))

    results = store.search("budget forecast quarter", k=1)

    assert isinstance(results[0], Chunk)


def test_search_rebuilds_the_chunk_that_was_indexed(store):
    original = _chunks(FINANCE)[0]
    store.build([original])

    hit = store.search("budget forecast quarter", k=1)[0]

    # The full round trip: Chunk → FAISS metadata dictionary → Chunk again.
    assert hit == original


def test_search_keeps_the_page_and_the_filename(store):
    store.build(_chunks(FINANCE, SAFETY))

    hit = store.search("safety procedures lab", k=1)[0]

    assert hit.source_document == "safety.pdf"
    assert hit.page_number == 5


def test_search_before_anything_is_indexed_is_refused(store):
    with pytest.raises(RuntimeError):
        store.search("anything")


def test_multi_document_search_picks_the_right_file(store):
    store.build(_chunks(FINANCE))
    store.add(_chunks(SAFETY))

    finance_hit = store.search("budget forecast quarter", k=1)[0]
    safety_hit = store.search("safety procedures lab", k=1)[0]

    assert finance_hit.source_document == "finance.pdf"
    assert safety_hit.source_document == "safety.pdf"


# ── How many passages come back ───────────────────────────────────────────────

def _many(source: str, count: int) -> list[Chunk]:
    return [
        Chunk(text=f"filler text passage {index}", source_document=source,
              page_number=index)
        for index in range(1, count + 1)
    ]


def test_search_honours_an_explicit_k(store):
    store.build(_many("a.pdf", 8))

    assert len(store.search("text", k=2)) == 2


def test_k_defaults_to_the_single_document_setting(store):
    store.build(_many("a.pdf", 8))

    assert len(store.search("text")) == AppConfig().retrieval_k


def test_k_widens_once_a_second_document_is_indexed(store):
    store.build(_many("a.pdf", 8))
    store.add(_many("b.pdf", 8))

    assert len(store.search("text")) == AppConfig().retrieval_k_multi_document


def test_an_explicit_k_overrides_the_multi_document_default(store):
    store.build(_many("a.pdf", 8))
    store.add(_many("b.pdf", 8))

    assert len(store.search("text", k=3)) == 3


def test_k_comes_from_the_config_it_was_given(fake_embeddings):
    store = VectorStore(
        AppConfig(retrieval_k=1, retrieval_k_multi_document=2),
        embeddings=fake_embeddings,
    )
    store.build(_many("a.pdf", 8))

    assert len(store.search("text")) == 1

    store.add(_many("b.pdf", 8))

    assert len(store.search("text")) == 2


# ── Which files are indexed ───────────────────────────────────────────────────

def test_sources_is_empty_before_anything_is_indexed(store):
    assert store.sources == ()


def test_sources_reports_every_indexed_file_once_sorted(store):
    store.build(_chunks(("alpha", "b.pdf", 1), ("beta", "b.pdf", 2)))
    store.add(_chunks(("gamma", "a.pdf", 1)))

    assert store.sources == ("a.pdf", "b.pdf")


# ── The seam with the rest of the pipeline ────────────────────────────────────

def test_a_real_pdf_survives_indexing_and_retrieval(make_pdf, fake_embeddings):
    pdf = make_pdf(
        ["intro boilerplate", "unrelated filler", "the deadline is March first"],
        name="handbook.pdf",
    )
    config = AppConfig()
    store = VectorStore(config, embeddings=fake_embeddings)

    store.build(TextSplitter(config).split(PdfLoader(config).load(pdf)))
    hit = store.search("deadline March first", k=1)[0]

    assert hit.source_document == "handbook.pdf"
    assert hit.page_number == 3


def test_the_caller_is_never_handed_a_faiss_or_langchain_object(store):
    # Every public result is one of our own types; the library stays inside.
    store.build(_chunks(FINANCE))

    assert all(isinstance(hit, Chunk) for hit in store.search("budget"))
    assert all(isinstance(name, str) for name in store.sources)


def test_there_is_no_persistence_yet(store):
    # DECISIONS.md #9: the index lives in session state, not on disk. If saving
    # is ever added it is a deliberate decision, not something that appeared.
    assert not hasattr(store, "save")
    assert not hasattr(store, "load")
