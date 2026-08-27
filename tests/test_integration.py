"""
End-to-end: PDF bytes → chunks → FAISS → retrieval → prompt → streamed answer.

Both external dependencies are stubbed (embeddings are the deterministic
FakeEmbeddings, Ollama is a canned token stream), so this runs in CI with no
model pulled and no server running.
"""

import pytest
from langchain_core.documents import Document

import rag_chain
from pdf_handler import load_pdf_as_documents
from rag_chain import (
    format_sources_markdown,
    stream_rag_answer_from_documents,
)
from vector_store import add_documents, build_vector_store, retrieve_relevant_documents


class RecordingOllama:
    def __init__(self):
        self.prompt = None

    def __call__(self, model, messages, stream):
        self.prompt = messages[0]["content"]
        return iter([{"message": {"content": "The deadline is March 1 [1]."}}])


@pytest.fixture
def recorded_ollama(monkeypatch):
    fake = RecordingOllama()
    monkeypatch.setattr(rag_chain.ollama, "chat", fake)
    return fake


def test_full_pipeline_cites_the_right_file_and_page(
    make_pdf, fake_embeddings, recorded_ollama
):
    handbook = make_pdf(
        [
            "introduction and general boilerplate",
            "unrelated filler about the cafeteria",
            "the submission deadline is March first",
        ],
        name="handbook.pdf",
    )
    finance = make_pdf(
        ["the budget forecast for the quarter"], name="finance.pdf"
    )

    # Index both PDFs into one store — the multi-document path.
    store = build_vector_store(load_pdf_as_documents(handbook), embeddings=fake_embeddings)
    add_documents(store, load_pdf_as_documents(finance))

    docs = retrieve_relevant_documents(store, "submission deadline March first", k=1)
    answer = "".join(stream_rag_answer_from_documents(docs, "When is the deadline?"))

    # The retrieved passage came from the right page of the right file …
    assert docs[0].metadata == {"source": "handbook.pdf", "page": 3}
    # … the prompt showed the model that provenance …
    assert "[1] handbook.pdf, p. 3" in recorded_ollama.prompt
    assert "When is the deadline?" in recorded_ollama.prompt
    # … and the UI can show the user the same passage list.
    assert "[1] handbook.pdf, p. 3" in format_sources_markdown(docs)
    assert answer == "The deadline is March 1 [1]."


def test_question_about_the_second_document_retrieves_from_it(
    make_pdf, fake_embeddings, recorded_ollama
):
    handbook = make_pdf(["the submission deadline is March first"], name="handbook.pdf")
    finance = make_pdf(
        ["intro", "the budget forecast for the quarter"], name="finance.pdf"
    )

    store = build_vector_store(load_pdf_as_documents(handbook), embeddings=fake_embeddings)
    add_documents(store, load_pdf_as_documents(finance))

    docs = retrieve_relevant_documents(store, "budget forecast quarter", k=1)
    list(stream_rag_answer_from_documents(docs, "What is the forecast?"))

    assert docs[0].metadata == {"source": "finance.pdf", "page": 2}
    assert "[1] finance.pdf, p. 2" in recorded_ollama.prompt


def test_prompt_never_invents_a_passage_marker(fake_embeddings, recorded_ollama):
    store = build_vector_store(
        [Document(page_content="only passage", metadata={"source": "a.pdf", "page": 1})],
        embeddings=fake_embeddings,
    )

    docs = retrieve_relevant_documents(store, "only passage", k=4)
    list(stream_rag_answer_from_documents(docs, "What is here?"))

    context_section = recorded_ollama.prompt.split("CONTEXT:")[1].split("QUESTION:")[0]
    assert "[1]" in context_section
    assert "[2]" not in context_section
