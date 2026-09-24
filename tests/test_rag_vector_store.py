"""
The VectorStore class: indexing, retrieval, and the Chunk round trip.

The promise these pin is that nothing outside this class ever handles a
LangChain Document: Chunks go in and Chunks come back, with their page and
filename intact.
"""

from dataclasses import replace

import pytest
from conftest import FakeEmbeddings
from langchain_core.embeddings import Embeddings

from documind.config import AppConfig
from documind.documents.models import Chunk
from documind.documents.pdf_loader import PdfLoader
from documind.documents.text_splitter import TextSplitter
from documind.rag.vector_store import TaskPrefixedEmbeddings, VectorStore


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


# ── Embedding in batches ──────────────────────────────────────────────────────

class RecordingEmbeddings(FakeEmbeddings):
    """FakeEmbeddings that remembers how many texts each embedding call carried."""

    def __init__(self):
        self.batch_sizes: list[int] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batch_sizes.append(len(texts))
        return super().embed_documents(texts)


class FailingOnSecondBatchEmbeddings(FakeEmbeddings):
    """FakeEmbeddings whose second embedding call fails, like a refused request."""

    def __init__(self):
        self.calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls == 2:
            raise ConnectionError("embedding request refused")
        return super().embed_documents(texts)


def _batched_store(embeddings) -> VectorStore:
    return VectorStore(replace(AppConfig(), embedding_batch_size=2), embeddings=embeddings)


def test_build_sends_the_chunks_in_batches_no_larger_than_configured():
    embeddings = RecordingEmbeddings()
    store = _batched_store(embeddings)

    store.build(_many("a.pdf", 5))

    assert embeddings.batch_sizes == [2, 2, 1]


def test_add_sends_the_chunks_in_batches_no_larger_than_configured():
    embeddings = RecordingEmbeddings()
    store = _batched_store(embeddings)
    store.build(_many("a.pdf", 1))
    embeddings.batch_sizes.clear()

    store.add(_many("b.pdf", 5))

    assert embeddings.batch_sizes == [2, 2, 1]


def test_every_batched_chunk_is_indexed_and_searchable():
    store = _batched_store(RecordingEmbeddings())
    first_file, second_file = _many("a.pdf", 5), _many("b.pdf", 5)

    store.build(first_file)
    store.add(second_file)
    hits = store.search("text", k=20)

    assert len(hits) == 10
    assert set(hits) == set(first_file + second_file)


def test_a_batched_build_still_replaces_what_was_indexed_before():
    store = _batched_store(RecordingEmbeddings())
    store.build(_many("a.pdf", 5))

    store.build(_many("b.pdf", 5))

    assert store.sources == ("b.pdf",)
    assert len(store.search("text", k=20)) == 5


def test_a_batch_that_fails_leaves_the_index_as_it_was():
    embeddings = FailingOnSecondBatchEmbeddings()
    store = _batched_store(embeddings)
    store.build(_many("a.pdf", 2))

    with pytest.raises(ConnectionError):
        store.add(_many("b.pdf", 5))

    assert store.sources == ("a.pdf",)
    assert len(store.search("text", k=20)) == 2


# ── nomic-embed-text-v2-moe's task prefixes ──────────────────────────────────

class TextRecordingEmbeddings(FakeEmbeddings):
    """FakeEmbeddings that remembers every text it was asked to embed."""

    def __init__(self):
        self.document_texts: list[str] = []
        self.query_texts: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_texts.extend(texts)
        return super().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        self.query_texts.append(text)
        return super().embed_query(text)


def _prefixed(inner: Embeddings) -> TaskPrefixedEmbeddings:
    return TaskPrefixedEmbeddings(
        inner, document_prefix="search_document: ", query_prefix="search_query: "
    )


def test_passages_are_embedded_with_the_document_prefix():
    inner = TextRecordingEmbeddings()

    _prefixed(inner).embed_documents(["the budget", "the lab"])

    assert inner.document_texts == [
        "search_document: the budget",
        "search_document: the lab",
    ]


def test_questions_are_embedded_with_the_query_prefix():
    inner = TextRecordingEmbeddings()

    _prefixed(inner).embed_query("what is the budget?")

    assert inner.query_texts == ["search_query: what is the budget?"]


def test_the_prefix_never_reaches_the_stored_or_returned_text():
    inner = TextRecordingEmbeddings()
    store = VectorStore(AppConfig(), embeddings=_prefixed(inner))
    store.build(_chunks(FINANCE))

    hit = store.search("budget forecast")[0]

    assert inner.query_texts == ["search_query: budget forecast"]
    assert hit.text == FINANCE[0]


def test_the_default_ollama_model_gets_the_configured_prefixes():
    config = AppConfig()

    embeddings = VectorStore(config)._resolve_embeddings()

    assert isinstance(embeddings, TaskPrefixedEmbeddings)
    assert embeddings._document_prefix == config.embedding_document_prefix
    assert embeddings._query_prefix == config.embedding_query_prefix


def test_an_injected_embedding_model_is_used_unwrapped(fake_embeddings):
    store = VectorStore(AppConfig(), embeddings=fake_embeddings)

    assert store._resolve_embeddings() is fake_embeddings


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
