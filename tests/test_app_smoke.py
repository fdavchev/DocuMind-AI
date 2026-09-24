"""
Does the app actually start?

Every other test exercises a module in isolation. These run `app.py` itself
through Streamlit's own script runner, which is the only way to catch the
failures that matter for a live demo: an import that no longer resolves, a
Streamlit API misuse, or an unhandled exception on a path nobody unit-tests.

The Ollama API is monkeypatched at the module level, so these are deterministic
and make no network call — including the case that matters most on a strange
machine: the app must come up cleanly when Ollama is not running at all.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import documind.rag.vector_store
import errors
from config import CHAT_MODE, PDF_MODE
from conftest import FakeEmbeddings, build_pdf_bytes
from documind.llm import OllamaProvider
from documind.ocr.models import OcrResult
from documind.ocr.ocr_engine import OcrEngine

APP = str(Path(__file__).resolve().parent.parent / "app.py")


class FakeListResponse:
    def __init__(self, names):
        self.models = [type("M", (), {"model": name})() for name in names]


@pytest.fixture
def app_with_ollama_down(monkeypatch):
    def refuse():
        raise ConnectionError("Failed to connect to Ollama.")

    monkeypatch.setattr(errors.ollama, "list", refuse)
    return AppTest.from_file(APP, default_timeout=60)


@pytest.fixture
def app_with_ollama_ready(monkeypatch):
    monkeypatch.setattr(
        errors.ollama,
        "list",
        lambda: FakeListResponse(["llama3", "nomic-embed-text", "llava"]),
    )
    return AppTest.from_file(APP, default_timeout=60)


def test_app_starts_without_exceptions_when_ollama_is_down(app_with_ollama_down):
    at = app_with_ollama_down.run()

    # A missing dependency or a Streamlit misuse shows up here and nowhere else.
    assert not at.exception, [e.value for e in at.exception]


def test_both_modes_are_offered(app_with_ollama_down):
    at = app_with_ollama_down.run()

    # Streamlit strips a leading emoji from the label and renders it as the
    # option's icon, so assert on the text rather than the raw constant.
    labels = at.segmented_control[0].options
    assert len(labels) == 2
    assert labels == [CHAT_MODE.split(" ", 1)[1], PDF_MODE.split(" ", 1)[1]]


def test_selecting_a_mode_switches_what_the_input_does(app_with_ollama_ready):
    # The behaviour that matters: the option values still round-trip with their
    # emoji intact, so the mode comparison in app.py holds.
    at = app_with_ollama_ready.run()
    assert "just chat" in at.chat_input[0].placeholder

    at = at.segmented_control[0].set_value(PDF_MODE).run()
    assert "PDF" in at.chat_input[0].placeholder
    assert not at.exception


def test_ollama_being_down_is_reported_as_a_warning_not_a_crash(app_with_ollama_down):
    at = app_with_ollama_down.run()

    warnings = " ".join(w.value for w in at.warning)
    assert "Ollama isn't running" in warnings
    assert "ollama serve" in warnings
    assert not at.exception


def test_a_missing_model_is_reported_on_startup(monkeypatch):
    # Ollama is up, but the PDF tab's models were never pulled.
    monkeypatch.setattr(errors.ollama, "list", lambda: FakeListResponse(["llava"]))

    at = AppTest.from_file(APP, default_timeout=60).run()

    warnings = " ".join(w.value for w in at.warning)
    assert "ollama pull llama3" in warnings
    assert not at.exception


def test_app_starts_cleanly_when_everything_is_ready(app_with_ollama_ready):
    at = app_with_ollama_ready.run()

    assert not at.exception
    assert not at.warning, [w.value for w in at.warning]
    assert any("Ollama is running" in s.value for s in at.success)


def test_chat_input_is_disabled_until_a_pdf_is_uploaded(app_with_ollama_ready):
    at = app_with_ollama_ready.run()
    at = at.segmented_control[0].set_value(PDF_MODE).run()

    # With no vector store the input must be inert rather than throwing when
    # someone types into it during a demo.
    assert at.chat_input[0].proto.disabled
    assert "Upload a PDF above" in at.chat_input[0].placeholder
    assert not at.exception


def test_switching_modes_keeps_a_single_input(app_with_ollama_ready):
    at = app_with_ollama_ready.run()
    assert len(at.chat_input) == 1

    at = at.segmented_control[0].set_value(PDF_MODE).run()
    assert len(at.chat_input) == 1
    assert not at.exception


# ── Layout regressions ─────────────────────────────────────────────────────────

def test_the_readiness_check_is_rendered_exactly_once(app_with_ollama_ready):
    """
    The status panel used to be rendered per tab, so the user saw two competing
    "System ready" panels. There is one check for the whole app now.
    """
    at = app_with_ollama_ready.run()

    ready_messages = [s.value for s in at.success if "Ollama is running" in s.value]
    assert len(ready_messages) == 1, ready_messages


def test_one_status_panel_covers_every_model_the_app_needs(app_with_ollama_ready):
    at = app_with_ollama_ready.run()

    message = next(s.value for s in at.success if "Ollama is running" in s.value)
    for model in ("llava", "llama3", "nomic-embed-text"):
        assert model in message


def test_a_model_missing_for_either_tab_is_reported_once(monkeypatch):
    # Only the chat model is installed; the PDF models are not.
    monkeypatch.setattr(errors.ollama, "list", lambda: FakeListResponse(["llava"]))

    at = AppTest.from_file(APP, default_timeout=60).run()

    warnings = [w.value for w in at.warning]
    assert len(warnings) == 1, warnings
    assert "ollama pull llama3" in warnings[0]


def test_the_input_is_top_level_so_streamlit_pins_it(monkeypatch, app_with_ollama_ready):
    """
    Streamlit pins st.chat_input to the viewport only when it is created with
    the MAIN root container and no ancestor blocks (see chat.py: it picks
    position="bottom" under exactly that condition, "inline" otherwise). Inside
    st.tabs the input scrolled away with the page. This asserts the condition
    itself rather than the symptom, so nesting the input again fails here.
    """
    import streamlit as st

    captured = {}
    real_chat_input = st.chat_input

    def spy(*args, **kwargs):
        active = st._main._active_dg
        captured["root"] = active._root_container
        captured["ancestors"] = set(active._ancestor_block_types)
        return real_chat_input(*args, **kwargs)

    monkeypatch.setattr(st, "chat_input", spy)
    app_with_ollama_ready.run()

    assert captured, "chat_input was never created"
    assert captured["ancestors"] == set(), (
        f"input is nested inside {captured['ancestors']} — Streamlit will render "
        "it inline and it will scroll away"
    )
    assert captured["root"] == st._main._root_container


# ── Sidebar and document list stay in step with what just happened ────────────

def test_save_chat_includes_the_turn_that_was_just_sent(monkeypatch, app_with_ollama_ready):
    """
    The sidebar draws the Save chat button before the chat turn at the bottom
    of the script runs. Without a rerun after the answer, the export lagged one
    turn behind: the first message only appeared after a second was sent.
    """
    import streamlit as st

    monkeypatch.setattr(
        OllamaProvider, "stream_chat", lambda self, messages: iter(["Hello ", "there"])
    )
    exports = []
    real_download_button = st.download_button

    def spy(*args, **kwargs):
        exports.append(kwargs["data"])
        return real_download_button(*args, **kwargs)

    monkeypatch.setattr(st, "download_button", spy)

    at = app_with_ollama_ready.run()
    at = at.chat_input[0].set_value("what is FAISS?").run()

    assert not at.exception
    assert "what is FAISS?" in exports[-1]
    assert "Hello there" in exports[-1]


def _pdf(name: str, text: str) -> tuple[str, bytes, str]:
    return (name, build_pdf_bytes([text]), "application/pdf")


FINANCE_PDF = _pdf("finance.pdf", "the budget forecast for the quarter")
SAFETY_PDF = _pdf("safety.pdf", "the safety procedures for the lab")


@pytest.fixture
def pdf_mode_app(monkeypatch, app_with_ollama_ready):
    # Real indexing, with the offline embedding model in place of Ollama's.
    monkeypatch.setattr(
        documind.rag.vector_store, "OllamaEmbeddings", lambda **kwargs: FakeEmbeddings()
    )
    at = app_with_ollama_ready.run()
    return at.segmented_control[0].set_value(PDF_MODE).run()


def test_deselecting_a_pdf_removes_it_from_the_index(pdf_mode_app):
    at = pdf_mode_app.file_uploader[0].set_value([FINANCE_PDF, SAFETY_PDF]).run()
    assert at.session_state.vector_store.sources == ("finance.pdf", "safety.pdf")

    # The uploader's own "x" on finance.pdf leaves only safety.pdf in the widget.
    at = at.file_uploader[0].set_value([SAFETY_PDF]).run()

    assert not at.exception
    assert at.session_state.vector_store.sources == ("safety.pdf",)
    assert any("1 indexed" in expander.label for expander in at.expander)


def test_deselecting_the_last_pdf_empties_the_index_but_keeps_the_chat(pdf_mode_app):
    at = pdf_mode_app.file_uploader[0].set_value([FINANCE_PDF]).run()
    at.session_state.pdf_chat_history = [
        {"role": "user", "content": "earlier question", "sources": None}
    ]

    at = at.file_uploader[0].set_value(None).run()

    assert not at.exception
    assert at.session_state.vector_store.is_ready is False
    assert len(at.session_state.pdf_chat_history) == 1


def test_a_mode_switch_does_not_read_as_deselecting_every_pdf(pdf_mode_app):
    # Streamlit empties the uploader when chat mode stops drawing it; the
    # indexed documents must survive that.
    at = pdf_mode_app.file_uploader[0].set_value([FINANCE_PDF]).run()

    at = at.segmented_control[0].set_value(CHAT_MODE).run()
    at = at.segmented_control[0].set_value(PDF_MODE).run()

    assert not at.exception
    assert at.session_state.vector_store.sources == ("finance.pdf",)


# ── OCR confidence is surfaced after an upload ────────────────────────────────

SCANNED_PDF = (
    "scanned.pdf",
    (Path(__file__).resolve().parent.parent / "samples" / "scanned.pdf").read_bytes(),
    "application/pdf",
)


def _ocr_reads_every_page_with(monkeypatch, confidence: float) -> None:
    # The real OcrEngine class, with Tesseract replaced, so the app script
    # builds its loaders exactly as it does live and only the reading is faked.
    monkeypatch.setattr(OcrEngine, "is_available", lambda self: True)
    monkeypatch.setattr(
        OcrEngine,
        "recognise",
        lambda self, image: OcrResult("the invoice total is due in March", confidence),
    )


def test_a_low_confidence_scanned_page_is_warned_about(monkeypatch, pdf_mode_app):
    _ocr_reads_every_page_with(monkeypatch, 42.0)

    at = pdf_mode_app.file_uploader[0].set_value([SCANNED_PDF]).run()

    assert not at.exception
    assert [w.value for w in at.warning] == [
        "Page 1 was recognised with 42% confidence — the answer may be unreliable."
    ]


def test_a_confidently_read_scanned_page_is_not_warned_about(monkeypatch, pdf_mode_app):
    _ocr_reads_every_page_with(monkeypatch, 95.0)

    at = pdf_mode_app.file_uploader[0].set_value([SCANNED_PDF]).run()

    assert not at.exception
    assert at.session_state.vector_store.sources == ("scanned.pdf",)
    assert not at.warning, [w.value for w in at.warning]


def test_clearing_documents_empties_the_uploader_so_nothing_is_reindexed(pdf_mode_app):
    # The uploader kept the cleared files selected, so the rerun after Clear
    # saw them as new and indexed them all over again.
    at = pdf_mode_app.file_uploader[0].set_value([FINANCE_PDF]).run()
    assert at.session_state.vector_store.sources == ("finance.pdf",)

    clear_button = next(b for b in at.button if "Clear documents" in b.label)
    at = clear_button.click().run()
    at = at.run()

    assert not at.exception
    assert at.session_state.vector_store.sources == ()
    assert at.session_state.vector_store.is_ready is False
    assert not at.file_uploader[0].value
