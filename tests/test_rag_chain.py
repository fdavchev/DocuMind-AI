"""Prompt construction and citation rendering."""

import pytest
from langchain_core.documents import Document

import rag_chain
from rag_chain import (
    build_context_block,
    build_rag_prompt,
    format_citation,
    format_sources_markdown,
    stream_rag_answer,
)


def _doc(text, source="report.pdf", page=4):
    metadata = {"source": source}
    if page is not None:
        metadata["page"] = page
    return Document(page_content=text, metadata=metadata)


def test_format_citation_includes_the_page():
    assert format_citation(_doc("x", "report.pdf", 4)) == "report.pdf, p. 4"


def test_format_citation_without_a_page_falls_back_to_the_filename():
    assert format_citation(_doc("x", "report.pdf", None)) == "report.pdf"


def test_format_citation_without_metadata_does_not_crash():
    assert format_citation(Document(page_content="x")) == "document"


def test_context_block_numbers_passages_and_labels_their_pages():
    context = build_context_block(
        [_doc("first passage", "a.pdf", 1), _doc("second passage", "b.pdf", 9)]
    )

    assert "[1] a.pdf, p. 1" in context
    assert "[2] b.pdf, p. 9" in context
    assert "first passage" in context
    assert "second passage" in context


def test_sources_markdown_lists_each_passage():
    markdown = format_sources_markdown(
        [_doc("first passage", "a.pdf", 1), _doc("second passage", "b.pdf", 9)]
    )

    assert "[1] a.pdf, p. 1" in markdown
    assert "[2] b.pdf, p. 9" in markdown


def test_sources_markdown_truncates_long_excerpts():
    markdown = format_sources_markdown([_doc("word " * 200)])

    assert markdown.endswith("…")
    assert len(markdown) < 400


def test_sources_markdown_handles_no_results():
    assert "No sources" in format_sources_markdown([])


def test_prompt_carries_context_question_and_the_citation_rule():
    prompt = build_rag_prompt("[1] a.pdf, p. 1\nthe deadline is March", "When is it?")

    assert "[1] a.pdf, p. 1" in prompt
    assert "When is it?" in prompt
    assert "Cite the passages you used inline" in prompt
    assert "I couldn't find that information in the document." in prompt


# ── The one test that touches the LLM boundary — stubbed, so it runs in CI ─────

class FakeOllamaChat:
    """Records the call and replays a canned token stream."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.calls = []

    def __call__(self, model, messages, stream):
        self.calls.append({"model": model, "messages": messages, "stream": stream})
        return ({"message": {"content": token}} for token in self.tokens)


@pytest.fixture
def fake_chat(monkeypatch):
    fake = FakeOllamaChat(["The deadline ", "is March 1 ", "[1]."])
    monkeypatch.setattr(rag_chain.ollama, "chat", fake)
    return fake


def test_stream_rag_answer_yields_the_model_tokens(fake_chat):
    tokens = list(stream_rag_answer("[1] a.pdf, p. 1\ndeadline March 1", "When?"))

    assert "".join(tokens) == "The deadline is March 1 [1]."


def test_stream_rag_answer_sends_the_built_prompt_to_ollama(fake_chat):
    list(stream_rag_answer("[1] a.pdf, p. 1\ndeadline March 1", "When?"))

    call = fake_chat.calls[0]
    assert call["model"] == rag_chain.ANSWER_MODEL
    assert call["stream"] is True
    assert "[1] a.pdf, p. 1" in call["messages"][0]["content"]
    assert "When?" in call["messages"][0]["content"]


def test_stream_rag_answer_skips_empty_tokens(monkeypatch):
    monkeypatch.setattr(
        rag_chain.ollama, "chat", FakeOllamaChat(["Answer", "", " text"])
    )

    assert list(stream_rag_answer("context", "question")) == ["Answer", " text"]
