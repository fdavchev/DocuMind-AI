"""Embedding and retrieval, including the multi-document case."""

from langchain_core.documents import Document

from pdf_handler import load_pdf_as_documents
from vector_store import (
    add_documents,
    build_vector_store,
    list_sources,
    retrieve_relevant_chunks,
    retrieve_relevant_documents,
)


def _docs(*pairs) -> list[Document]:
    return [
        Document(page_content=text, metadata={"source": source, "page": page})
        for text, source, page in pairs
    ]


def test_build_vector_store_indexes_every_chunk(fake_embeddings):
    store = build_vector_store(
        _docs(
            ("budget forecast for the quarter", "finance.pdf", 2),
            ("safety procedures for the lab", "safety.pdf", 5),
        ),
        embeddings=fake_embeddings,
    )

    assert len(store.docstore._dict) == 2


def test_build_vector_store_accepts_plain_strings(fake_embeddings):
    store = build_vector_store(
        ["budget forecast", "safety procedures"], embeddings=fake_embeddings
    )

    results = retrieve_relevant_documents(store, "budget", k=1)
    assert results[0].page_content == "budget forecast"


def test_retrieval_returns_the_matching_chunk_with_its_metadata(fake_embeddings):
    store = build_vector_store(
        _docs(
            ("the budget forecast for the quarter", "finance.pdf", 2),
            ("the safety procedures for the lab", "safety.pdf", 5),
        ),
        embeddings=fake_embeddings,
    )

    results = retrieve_relevant_documents(store, "budget forecast quarter", k=1)

    assert results[0].metadata == {"source": "finance.pdf", "page": 2}


def test_retrieval_honours_k(fake_embeddings):
    store = build_vector_store(
        _docs(
            ("alpha text", "a.pdf", 1),
            ("beta text", "a.pdf", 2),
            ("gamma text", "a.pdf", 3),
        ),
        embeddings=fake_embeddings,
    )

    assert len(retrieve_relevant_documents(store, "text", k=2)) == 2


def test_retrieve_relevant_chunks_returns_joined_text(fake_embeddings):
    store = build_vector_store(
        _docs(("the budget forecast", "finance.pdf", 2)), embeddings=fake_embeddings
    )

    context = retrieve_relevant_chunks(store, "budget", k=1)

    assert context == "the budget forecast"


def test_add_documents_extends_the_same_index(fake_embeddings):
    store = build_vector_store(
        _docs(("the budget forecast for the quarter", "finance.pdf", 2)),
        embeddings=fake_embeddings,
    )

    add_documents(store, _docs(("the safety procedures for the lab", "safety.pdf", 5)))

    assert len(store.docstore._dict) == 2


def test_multi_document_retrieval_picks_the_right_file(fake_embeddings):
    store = build_vector_store(
        _docs(("the budget forecast for the quarter", "finance.pdf", 2)),
        embeddings=fake_embeddings,
    )
    add_documents(store, _docs(("the safety procedures for the lab", "safety.pdf", 5)))

    finance_hit = retrieve_relevant_documents(store, "budget forecast quarter", k=1)[0]
    safety_hit = retrieve_relevant_documents(store, "safety procedures lab", k=1)[0]

    assert finance_hit.metadata["source"] == "finance.pdf"
    assert safety_hit.metadata["source"] == "safety.pdf"


def test_list_sources_reports_every_indexed_file(fake_embeddings):
    store = build_vector_store(
        _docs(("alpha", "b.pdf", 1), ("beta", "b.pdf", 2)), embeddings=fake_embeddings
    )
    add_documents(store, _docs(("gamma", "a.pdf", 1)))

    assert list_sources(store) == ["a.pdf", "b.pdf"]


def test_pdf_to_retrieval_keeps_the_page_number(make_pdf, fake_embeddings):
    pdf = make_pdf(
        ["intro boilerplate", "unrelated filler", "the deadline is March first"],
        name="handbook.pdf",
    )

    store = build_vector_store(load_pdf_as_documents(pdf), embeddings=fake_embeddings)
    hit = retrieve_relevant_documents(store, "deadline March first", k=1)[0]

    assert hit.metadata == {"source": "handbook.pdf", "page": 3}
