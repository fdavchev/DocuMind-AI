"""
The RagPipeline class: upload in, cited answer out.

These exercise the whole document pipeline with the real LoaderFactory,
TextSplitter and VectorStore — real pdfplumber, real chunking, real FAISS — and
substitute only the two things that would need a server: the embedding model
(the deterministic `fake_embeddings` fixture) and the language model (the
`FakeProvider` below, which implements LLMProvider and replays canned tokens).
The OCR-confidence tests also stand in for Tesseract, with conftest's
FakeOcrEngine handed to the PDF loader by `PdfLoaderFactoryWithOcr`.
That substitution is the point of the seams built in the earlier steps, and it
is why this file runs offline.
"""

import dataclasses
import io

import pytest

from documind.config import AnswerLanguage, AppConfig
from documind.documents.loader_factory import LoaderFactory
from documind.documents.models import Chunk
from documind.documents.pdf_loader import PdfLoader
from documind.documents.text_splitter import TextSplitter
from documind.llm.llm_provider import LLMProvider
from documind.rag.rag_pipeline import OPENING_TEXT_LIMIT, IngestReport, RagPipeline
from documind.rag.vector_store import VectorStore
from errors import (
    EmptyDocumentError,
    FriendlyError,
    NoDocumentsIndexed,
    UnsupportedFileError,
)


# ── Fakes ──────────────────────────────────────────────────────────────────────

class FakeProvider(LLMProvider):
    """
    A language model that never leaves the process.

    It records every prompt it is asked to answer — which is how these tests
    check what the pipeline actually wrote — and replays a fixed token stream.
    """

    def __init__(self, tokens=("The deadline ", "is March 1 ", "[1].")):
        self.tokens = list(tokens)
        self.prompts: list[str] = []

    def is_available(self) -> bool:
        return True

    def stream_chat(self, messages):
        yield "chat"

    def stream_vision(self, image, prompt):
        yield "vision"

    def stream_answer(self, prompt):
        self.prompts.append(prompt)
        return iter(self.tokens)


class PdfLoaderFactoryWithOcr(LoaderFactory):
    """A factory whose PDF loaders read scanned pages with the given OCR engine."""

    def __init__(self, config: AppConfig, ocr_engine):
        super().__init__(config)
        self._ocr_engine = ocr_engine

    def create_loader(self, filename: str):
        return PdfLoader(self._config, ocr_engine=self._ocr_engine)


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def pipeline(provider, fake_embeddings):
    config = AppConfig()
    return RagPipeline(
        config=config,
        loader_factory=LoaderFactory(config),
        splitter=TextSplitter(config),
        vector_store=VectorStore(config, embeddings=fake_embeddings),
        provider=provider,
    )


@pytest.fixture
def make_txt():
    """make_txt("file contents", name="notes.md")"""

    def _make(text: str, name: str = "notes.txt"):
        upload = io.BytesIO(text.encode("utf-8"))
        upload.name = name
        return upload

    return _make


def _chunk(text, source="report.pdf", page=4) -> Chunk:
    return Chunk(text=text, source_document=source, page_number=page)


# ── Ingesting ─────────────────────────────────────────────────────────────────

def test_ingest_makes_a_pdf_searchable(pipeline, make_pdf):
    pipeline.ingest(make_pdf(["the budget was approved in March"], name="a.pdf"))

    assert pipeline._vector_store.is_ready is True
    assert pipeline._vector_store.sources == ("a.pdf",)


def test_ingest_reports_what_it_indexed(pipeline, make_pdf):
    report = pipeline.ingest(
        make_pdf(["first page text", "second page text"], name="report.pdf")
    )

    assert isinstance(report, IngestReport)
    assert report.document_name == "report.pdf"
    assert report.page_count == 2
    assert report.chunk_count >= 2
    assert report.ocr_page_count == 0


def test_ingest_reports_how_long_it_took(pipeline, make_pdf):
    report = pipeline.ingest(make_pdf(["some text"]))

    assert isinstance(report.elapsed_seconds, float)
    assert report.elapsed_seconds >= 0


def test_a_report_without_ocr_says_so(pipeline, make_pdf):
    report = pipeline.ingest(make_pdf(["a page with a real text layer"]))

    assert report.used_ocr is False


def test_a_report_without_ocr_has_no_ocr_confidences(pipeline, make_pdf):
    report = pipeline.ingest(make_pdf(["a page with a real text layer"]))

    assert report.ocr_confidences == ()


def _pipeline_reading_scans_with(ocr_engine, provider, fake_embeddings) -> RagPipeline:
    config = AppConfig()
    return RagPipeline(
        config=config,
        loader_factory=PdfLoaderFactoryWithOcr(config, ocr_engine),
        splitter=TextSplitter(config),
        vector_store=VectorStore(config, embeddings=fake_embeddings),
        provider=provider,
    )


def test_a_report_gives_each_ocr_pages_confidence_in_page_order(
    fake_ocr_engine, provider, fake_embeddings, make_pdf
):
    fake_ocr_engine.confidence = 42.0
    text_page = "a page with a proper text layer on it"
    pipeline = _pipeline_reading_scans_with(fake_ocr_engine, provider, fake_embeddings)

    report = pipeline.ingest(make_pdf([text_page, "", text_page, ""]))

    assert report.ocr_confidences == ((2, 42.0), (4, 42.0))


def test_a_report_lists_confident_ocr_pages_too(
    fake_ocr_engine, provider, fake_embeddings, make_pdf
):
    # The pipeline reports facts; filtering by AppConfig.ocr_min_confidence is
    # the UI's decision, so a page well above it is still listed.
    fake_ocr_engine.confidence = 99.0
    pipeline = _pipeline_reading_scans_with(fake_ocr_engine, provider, fake_embeddings)

    report = pipeline.ingest(make_pdf([""]))

    assert report.ocr_confidences == ((1, 99.0),)


def test_a_report_cannot_be_edited_after_the_fact():
    report = IngestReport("a.pdf", 2, 5, 0, 0.1)

    with pytest.raises(dataclasses.FrozenInstanceError):
        report.chunk_count = 99


def test_the_chunk_count_is_what_was_indexed(pipeline, make_pdf):
    report = pipeline.ingest(make_pdf(["alpha", "beta", "gamma"], name="x.pdf"))

    assert report.chunk_count == len(pipeline._vector_store._store.docstore._dict)


def test_ingest_dispatches_to_the_right_loader_by_itself(pipeline, make_txt):
    # Nothing in the call says what kind of file this is — the factory decides.
    report = pipeline.ingest(make_txt("plain text notes about the budget"))

    assert report.document_name == "notes.txt"
    assert report.page_count == 1
    assert pipeline._vector_store.sources == ("notes.txt",)


def test_a_second_document_joins_the_same_index(pipeline, make_pdf):
    pipeline.ingest(make_pdf(["the budget forecast"], name="finance.pdf"))
    pipeline.ingest(make_pdf(["the safety procedures"], name="safety.pdf"))

    assert pipeline._vector_store.sources == ("finance.pdf", "safety.pdf")


def test_an_explicit_name_is_what_the_citation_will_show(pipeline, make_pdf):
    report = pipeline.ingest(
        make_pdf(["contents"], name="tmp_upload.pdf"), name="thesis.pdf"
    )

    assert report.document_name == "thesis.pdf"
    assert pipeline._vector_store.sources == ("thesis.pdf",)


def test_ingesting_an_unreadable_file_type_is_refused(pipeline, make_txt):
    with pytest.raises(UnsupportedFileError):
        pipeline.ingest(make_txt("contents", name="slides.pptx"))


def test_ingesting_an_empty_file_is_refused(pipeline, make_txt):
    with pytest.raises(EmptyDocumentError):
        pipeline.ingest(make_txt("   \n  ", name="blank.txt"))


def test_a_refused_upload_indexes_nothing(pipeline, make_txt):
    with pytest.raises(EmptyDocumentError):
        pipeline.ingest(make_txt("", name="blank.txt"))

    assert pipeline._vector_store.is_ready is False


# ── Asking ────────────────────────────────────────────────────────────────────

def test_ask_streams_the_providers_tokens(pipeline, make_pdf):
    pipeline.ingest(make_pdf(["the deadline is March first"]))

    assert "".join(pipeline.ask("When is the deadline?")) == (
        "The deadline is March 1 [1]."
    )


def test_ask_uses_the_provider_it_was_given(pipeline, provider, make_pdf):
    pipeline.ingest(make_pdf(["the deadline is March first"]))

    list(pipeline.ask("When is the deadline?"))

    # The only model call in the whole pipeline goes through this seam; nothing
    # here has reached for Ollama.
    assert len(provider.prompts) == 1


def test_ask_sends_the_question_and_the_retrieved_passage(pipeline, provider, make_pdf):
    pipeline.ingest(make_pdf(["the deadline is March first"], name="handbook.pdf"))

    list(pipeline.ask("When is the deadline?"))

    prompt = provider.prompts[0]
    assert "When is the deadline?" in prompt
    assert "the deadline is March first" in prompt
    assert "[1] handbook.pdf, p. 1" in prompt


def test_ask_sends_the_citation_rules(pipeline, provider, make_pdf):
    pipeline.ingest(make_pdf(["some content"]))

    list(pipeline.ask("anything?"))

    prompt = provider.prompts[0]
    assert "Cite the passages you used inline" in prompt
    assert "I couldn't find that information in the document." in prompt


def test_asking_before_anything_is_indexed_is_refused(pipeline, provider):
    with pytest.raises(NoDocumentsIndexed):
        pipeline.ask("When is the deadline?")

    # And the model was never asked to answer from nothing.
    assert provider.prompts == []


def test_the_refusal_is_a_message_the_ui_can_render(pipeline):
    # A FriendlyError, not the RuntimeError the store raises underneath — app.py
    # already knows how to show this one.
    with pytest.raises(FriendlyError) as raised:
        pipeline.ask("anything?")

    assert "nothing to search yet" in raised.value.render()


def test_retrieval_happens_before_the_first_token(pipeline, make_pdf):
    pipeline.ingest(make_pdf(["the deadline is March first"], name="handbook.pdf"))

    stream = pipeline.ask("When is the deadline?")

    # Nothing has been consumed from the stream yet, and the sources are already
    # there — which is what lets the UI render them next to a streaming answer.
    assert pipeline.last_sources
    assert list(stream)


# ── Saying what each document is, whatever the question ───────────────────────

def test_the_prompt_names_each_document_with_its_declared_title_and_authors(
    pipeline, provider, make_pdf
):
    pipeline.ingest(
        make_pdf(
            ["the deadline is March first"],
            name="paper.pdf",
            title="Deep Residual Learning",
            author="K. He, X. Zhang",
        )
    )

    list(pipeline.ask("When is the deadline?"))

    assert (
        "DOCUMENT: paper.pdf — Title: Deep Residual Learning — Authors: K. He, X. Zhang"
        in provider.prompts[0]
    )


def test_declared_title_and_authors_still_come_with_the_opening_lines(
    pipeline, make_pdf
):
    # The failure this exists for: "What is the first author's affiliation?"
    # The affiliation is on the title page, never in the Title/Author fields.
    pipeline.ingest(
        make_pdf(
            ["Deep Residual Learning\nK. He, Microsoft Research"],
            name="paper.pdf",
            title="Deep Residual Learning",
            author="K. He",
        )
    )

    assert pipeline.build_documents_block() == (
        "DOCUMENT: paper.pdf — Title: Deep Residual Learning — Authors: K. He"
        " — Opening lines: Deep Residual Learning K. He, Microsoft Research"
    )


def test_the_title_reaches_the_prompt_even_when_its_page_is_not_retrieved(
    pipeline, provider, make_pdf
):
    # The failure this exists for: the title page lost the similarity contest
    # to passages that merely shared more words with the question.
    pages = ["Deep Residual Learning\nK. He"] + [
        f"what is the title of this paper {n}" for n in range(8)
    ]
    pipeline.ingest(make_pdf(pages, name="paper.pdf"))

    list(pipeline.ask("what is the title of this paper"))

    assert all(source.page_number != 1 for source in pipeline.last_sources)
    assert "Opening lines: Deep Residual Learning K. He" in provider.prompts[0]


def test_without_declared_metadata_the_opening_lines_stand_in(pipeline, make_pdf):
    pipeline.ingest(make_pdf(["Deep Residual Learning\nK. He, X. Zhang"], name="p.pdf"))

    assert pipeline.build_documents_block() == (
        "DOCUMENT: p.pdf — Opening lines: Deep Residual Learning K. He, X. Zhang"
    )


def test_a_declared_title_without_authors_still_adds_the_opening_lines(
    pipeline, make_pdf
):
    pipeline.ingest(make_pdf(["Deep Residual Learning\nK. He"], name="p.pdf", title="ResNet"))

    assert pipeline.build_documents_block() == (
        "DOCUMENT: p.pdf — Title: ResNet — Opening lines: Deep Residual Learning K. He"
    )


def test_long_opening_lines_are_trimmed_to_the_opening_text_limit(pipeline, make_pdf):
    # Six-character words put a letter, not a space, at the cut, so trimming
    # the trailing whitespace leaves exactly OPENING_TEXT_LIMIT characters.
    pipeline.ingest(make_pdf(["words " * 100], name="p.pdf"))

    opening = pipeline.build_documents_block().split("Opening lines: ", 1)[1]

    assert opening.endswith("…")
    assert len(opening.removesuffix("…")) == OPENING_TEXT_LIMIT


def test_opening_lines_shorter_than_the_limit_are_kept_whole(pipeline, make_pdf):
    pipeline.ingest(make_pdf(["Budget 2026"], name="p.pdf", title="Budget", author="A"))

    assert pipeline.build_documents_block() == (
        "DOCUMENT: p.pdf — Title: Budget — Authors: A — Opening lines: Budget 2026"
    )


def test_every_indexed_document_gets_its_own_line(pipeline, make_pdf):
    pipeline.ingest(make_pdf(["budget text"], name="finance.pdf", title="Budget", author="A"))
    pipeline.ingest(make_pdf(["safety text"], name="safety.pdf", title="Safety", author="B"))

    assert pipeline.build_documents_block().splitlines() == [
        "DOCUMENT: finance.pdf — Title: Budget — Authors: A — Opening lines: budget text",
        "DOCUMENT: safety.pdf — Title: Safety — Authors: B — Opening lines: safety text",
    ]


def test_a_document_removed_from_the_store_is_no_longer_described(pipeline, make_pdf):
    pipeline.ingest(make_pdf(["budget text"], name="finance.pdf", title="Budget", author="A"))
    pipeline.ingest(make_pdf(["safety text"], name="safety.pdf", title="Safety", author="B"))

    pipeline._vector_store.remove("finance.pdf")

    assert pipeline.build_documents_block() == (
        "DOCUMENT: safety.pdf — Title: Safety — Authors: B — Opening lines: safety text"
    )


def test_the_prompt_tells_the_model_what_the_document_lines_are_for(pipeline):
    prompt = pipeline.build_rag_prompt("context", "question")

    assert "Lines starting with DOCUMENT:" in prompt
    assert "affiliations" in prompt


# ── The sources of the last answer ────────────────────────────────────────────

def test_there_are_no_sources_before_the_first_question(pipeline):
    assert pipeline.last_sources == ()


def test_last_sources_holds_the_retrieved_chunks(pipeline, make_pdf):
    pipeline.ingest(
        make_pdf(["intro", "filler", "the deadline is March first"], name="h.pdf")
    )

    list(pipeline.ask("deadline March first"))

    assert all(isinstance(source, Chunk) for source in pipeline.last_sources)
    assert pipeline.last_sources[0].source_document == "h.pdf"
    assert pipeline.last_sources[0].page_number == 3


def test_last_sources_is_an_immutable_tuple(pipeline, make_pdf):
    pipeline.ingest(make_pdf(["the deadline is March first"]))
    list(pipeline.ask("deadline"))

    with pytest.raises(AttributeError):
        pipeline.last_sources.append(_chunk("smuggled in"))


def test_last_sources_is_replaced_by_the_next_question(pipeline, make_pdf):
    pipeline.ingest(make_pdf(["the budget forecast"], name="finance.pdf"))
    list(pipeline.ask("budget"))
    first = pipeline.last_sources

    pipeline.ingest(make_pdf(["the safety procedures"], name="safety.pdf"))
    list(pipeline.ask("safety procedures"))

    assert pipeline.last_sources != first
    assert pipeline.last_sources[0].source_document == "safety.pdf"


def test_a_refused_question_leaves_no_stale_sources(pipeline, make_pdf, provider):
    pipeline.ingest(make_pdf(["the budget forecast"], name="finance.pdf"))
    list(pipeline.ask("budget"))

    # A fresh pipeline over an empty store: the refusal must not leave the
    # previous answer's citations standing under it.
    pipeline._vector_store = VectorStore(AppConfig(), embeddings=None)
    with pytest.raises(NoDocumentsIndexed):
        pipeline.ask("budget")

    assert pipeline.last_sources == ()


def test_the_numbering_in_the_prompt_matches_last_sources(pipeline, provider, make_pdf):
    pipeline.ingest(
        make_pdf(["budget forecast quarter", "safety procedures lab"], name="m.pdf")
    )

    list(pipeline.ask("budget forecast quarter"))

    prompt = provider.prompts[0]
    for index, source in enumerate(pipeline.last_sources, start=1):
        assert f"[{index}] {pipeline.format_citation(source)}" in prompt


# ── Citations and the prompt, ported from rag_chain.py ────────────────────────

def test_format_citation_includes_the_page(pipeline):
    assert pipeline.format_citation(_chunk("x", "report.pdf", 4)) == "report.pdf, p. 4"


def test_format_citation_without_a_page_falls_back_to_the_filename(pipeline):
    # page 0 is how the vector store records "no page was stored".
    assert pipeline.format_citation(_chunk("x", "report.pdf", 0)) == "report.pdf"


def test_format_citation_without_a_source_does_not_crash(pipeline):
    assert pipeline.format_citation(_chunk("x", "", 0)) == "document"


def test_context_block_numbers_passages_and_labels_their_pages(pipeline):
    context = pipeline.build_context_block(
        [_chunk("first passage", "a.pdf", 1), _chunk("second passage", "b.pdf", 9)]
    )

    assert "[1] a.pdf, p. 1" in context
    assert "[2] b.pdf, p. 9" in context
    assert "first passage" in context
    assert "second passage" in context


def test_sources_markdown_lists_each_passage(pipeline):
    markdown = pipeline.format_sources_markdown(
        [_chunk("first passage", "a.pdf", 1), _chunk("second passage", "b.pdf", 9)]
    )

    assert "[1] a.pdf, p. 1" in markdown
    assert "[2] b.pdf, p. 9" in markdown


def test_sources_markdown_truncates_long_excerpts(pipeline):
    markdown = pipeline.format_sources_markdown([_chunk("word " * 200)])

    assert markdown.endswith("…")
    assert len(markdown) < 400


def test_sources_markdown_handles_no_results(pipeline):
    assert "No sources" in pipeline.format_sources_markdown([])


def test_sources_markdown_defaults_to_the_last_answers_sources(pipeline, make_pdf):
    pipeline.ingest(make_pdf(["the deadline is March first"], name="handbook.pdf"))
    list(pipeline.ask("deadline"))

    assert "[1] handbook.pdf, p. 1" in pipeline.format_sources_markdown()


def test_sources_markdown_before_any_question_says_so(pipeline):
    assert "No sources" in pipeline.format_sources_markdown()


def test_prompt_carries_context_question_and_the_citation_rule(pipeline):
    prompt = pipeline.build_rag_prompt(
        "[1] a.pdf, p. 1\nthe deadline is March", "When is it?"
    )

    assert "[1] a.pdf, p. 1" in prompt
    assert "When is it?" in prompt
    assert "Cite the passages you used inline" in prompt
    assert "I couldn't find that information in the document." in prompt


# ── Answering in the question's language ──────────────────────────────────────

def test_a_cyrillic_question_asks_for_a_macedonian_answer(pipeline):
    prompt = pipeline.build_rag_prompt("context", "Колку е висок кошот?")

    assert AppConfig().macedonian.instruction in prompt
    assert AppConfig().english.instruction not in prompt


def test_a_latin_question_asks_for_an_english_answer(pipeline):
    prompt = pipeline.build_rag_prompt("context", "How high is the basket?")

    assert AppConfig().english.instruction in prompt
    assert AppConfig().macedonian.instruction not in prompt


def test_the_language_instruction_sits_directly_before_answer(pipeline):
    # llama3 ignored the same request when it sat up in the rules; only right
    # before ANSWER: was it followed (DECISIONS.md #21).
    prompt = pipeline.build_rag_prompt("context", "Колку е висок кошот?")

    assert prompt.endswith(f"{AppConfig().macedonian.instruction}\n\nANSWER:")


def test_a_mostly_cyrillic_question_with_a_latin_term_is_still_macedonian(pipeline):
    prompt = pipeline.build_rag_prompt("context", "Што е FIBA и кога е основана?")

    assert AppConfig().macedonian.instruction in prompt


def test_a_question_with_no_letters_defaults_to_english(pipeline):
    prompt = pipeline.build_rag_prompt("context", "1 + 1 = ?")

    assert AppConfig().english.instruction in prompt


def test_an_even_split_of_alphabets_defaults_to_english(pipeline):
    prompt = pipeline.build_rag_prompt("context", "abc где")

    assert AppConfig().english.instruction in prompt


def test_a_macedonian_question_gets_the_not_found_message_in_macedonian(pipeline):
    prompt = pipeline.build_rag_prompt("context", "Колку е висок кошот?")

    assert AppConfig().macedonian.not_found_message in prompt
    assert AppConfig().english.not_found_message not in prompt


def test_an_english_question_gets_the_not_found_message_in_english(pipeline):
    prompt = pipeline.build_rag_prompt("context", "How high is the basket?")

    assert AppConfig().english.not_found_message in prompt
    assert AppConfig().macedonian.not_found_message not in prompt


def test_the_answer_languages_come_from_the_config(provider, fake_embeddings):
    config = dataclasses.replace(
        AppConfig(),
        macedonian=AnswerLanguage(
            instruction="CUSTOM MK INSTRUCTION", not_found_message="CUSTOM MK MISSING"
        ),
    )
    pipeline = RagPipeline(
        config=config,
        loader_factory=LoaderFactory(config),
        splitter=TextSplitter(config),
        vector_store=VectorStore(config, embeddings=fake_embeddings),
        provider=provider,
    )

    prompt = pipeline.build_rag_prompt("context", "Колку е висок кошот?")

    assert "CUSTOM MK INSTRUCTION" in prompt
    assert "CUSTOM MK MISSING" in prompt


# ── The whole thing, end to end ───────────────────────────────────────────────

def test_a_real_pdf_becomes_a_cited_answer(fake_embeddings, make_pdf):
    """
    Upload → loader → splitter → FAISS → prompt → streamed answer, with real
    components throughout and only the two models faked.
    """
    config = AppConfig()
    provider = FakeProvider(tokens=["The deadline is March first [1]."])
    pipeline = RagPipeline(
        config=config,
        loader_factory=LoaderFactory(config),
        splitter=TextSplitter(config),
        vector_store=VectorStore(config, embeddings=fake_embeddings),
        provider=provider,
    )

    report = pipeline.ingest(
        make_pdf(
            ["intro boilerplate", "unrelated filler", "the deadline is March first"],
            name="handbook.pdf",
        )
    )
    answer = "".join(pipeline.ask("When is the deadline?"))

    assert report.page_count == 3
    assert answer == "The deadline is March first [1]."
    assert "[1] handbook.pdf, p. 3" in provider.prompts[0]
    assert "[1] handbook.pdf, p. 3" in pipeline.format_sources_markdown()


def test_two_documents_are_answered_from_together(fake_embeddings, make_pdf):
    config = AppConfig()
    provider = FakeProvider()
    pipeline = RagPipeline(
        config=config,
        loader_factory=LoaderFactory(config),
        splitter=TextSplitter(config),
        vector_store=VectorStore(config, embeddings=fake_embeddings),
        provider=provider,
    )

    pipeline.ingest(make_pdf(["the budget forecast quarter"], name="finance.pdf"))
    pipeline.ingest(make_pdf(["the safety procedures lab"], name="safety.pdf"))

    list(pipeline.ask("safety procedures lab"))

    assert pipeline.last_sources[0].source_document == "safety.pdf"
    assert "safety.pdf, p. 1" in provider.prompts[0]


def test_the_caller_never_sees_a_library_object(pipeline, make_pdf):
    # Chunks out, markdown out, tokens out — no FAISS, LangChain or Ollama type
    # crosses this class's surface.
    pipeline.ingest(make_pdf(["the deadline is March first"]))

    tokens = list(pipeline.ask("deadline"))

    assert all(isinstance(token, str) for token in tokens)
    assert all(isinstance(source, Chunk) for source in pipeline.last_sources)
    assert isinstance(pipeline.format_sources_markdown(), str)
