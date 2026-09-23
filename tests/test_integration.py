"""
End-to-end: PDF bytes → chunks → FAISS → retrieval → prompt → streamed answer.

This is the whole stack the app runs on, assembled exactly as `app.py` assembles
it — a real LoaderFactory, TextSplitter, VectorStore and OllamaProvider behind a
RagPipeline. Both external dependencies are stubbed (embeddings are the
deterministic FakeEmbeddings, Ollama is a canned token stream), so this runs in
CI with no model pulled and no server running. Unlike `test_rag_pipeline.py`,
which swaps in a FakeProvider, the provider here is the real one: the prompt
asserted below is the prompt Ollama would have received.
"""

import pytest

from documind.config import AppConfig
from documind.documents.loader_factory import LoaderFactory
from documind.documents.text_splitter import TextSplitter
from documind.llm import ollama_provider
from documind.llm.ollama_provider import OllamaProvider
from documind.rag.rag_pipeline import RagPipeline
from documind.rag.vector_store import VectorStore


class RecordingOllama:
    def __init__(self):
        self.prompt = None

    def __call__(self, **kwargs):
        self.prompt = kwargs["messages"][0]["content"]
        return iter([{"message": {"content": "The deadline is March 1 [1]."}}])


@pytest.fixture
def recorded_ollama(monkeypatch):
    fake = RecordingOllama()
    monkeypatch.setattr(ollama_provider.ollama, "chat", fake)
    return fake


@pytest.fixture
def pipeline(fake_embeddings):
    """The same object graph app.py builds at startup."""
    config = AppConfig()
    return RagPipeline(
        loader_factory=LoaderFactory(config),
        splitter=TextSplitter(config),
        vector_store=VectorStore(config, embeddings=fake_embeddings),
        provider=OllamaProvider(config),
    )


def test_full_pipeline_cites_the_right_file_and_page(
    pipeline, make_pdf, recorded_ollama
):
    handbook = make_pdf(
        [
            "introduction and general boilerplate",
            "unrelated filler about the cafeteria",
            "the submission deadline is March first",
        ],
        name="handbook.pdf",
    )
    finance = make_pdf(["the budget forecast for the quarter"], name="finance.pdf")

    # Index both PDFs into one store — the multi-document path.
    pipeline.ingest(handbook)
    pipeline.ingest(finance)

    answer = "".join(pipeline.ask("When is the deadline?"))

    # The retrieved passage came from the right page of the right file …
    assert pipeline.last_sources[0].source_document == "handbook.pdf"
    assert pipeline.last_sources[0].page_number == 3
    # … the prompt showed the model that provenance …
    assert "[1] handbook.pdf, p. 3" in recorded_ollama.prompt
    assert "When is the deadline?" in recorded_ollama.prompt
    # … and the UI can show the user the same passage list.
    assert "[1] handbook.pdf, p. 3" in pipeline.format_sources_markdown()
    assert answer == "The deadline is March 1 [1]."


def test_question_about_the_second_document_retrieves_from_it(
    pipeline, make_pdf, recorded_ollama
):
    pipeline.ingest(
        make_pdf(["the submission deadline is March first"], name="handbook.pdf")
    )
    pipeline.ingest(
        make_pdf(["intro", "the budget forecast for the quarter"], name="finance.pdf")
    )

    list(pipeline.ask("budget forecast quarter"))

    assert pipeline.last_sources[0].source_document == "finance.pdf"
    assert pipeline.last_sources[0].page_number == 2
    assert "[1] finance.pdf, p. 2" in recorded_ollama.prompt


def test_prompt_never_invents_a_passage_marker(pipeline, make_pdf, recorded_ollama):
    # One passage indexed, four retrieval slots — the prompt must number only
    # what actually came back.
    pipeline.ingest(make_pdf(["only passage"], name="a.pdf"))

    list(pipeline.ask("What is here?"))

    context_section = recorded_ollama.prompt.split("CONTEXT:")[1].split("QUESTION:")[0]
    assert "[1]" in context_section
    assert "[2]" not in context_section
