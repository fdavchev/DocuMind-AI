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

import pytest
from streamlit.testing.v1 import AppTest

import errors

APP = str((__import__("pathlib").Path(__file__).resolve().parent.parent / "app.py"))


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


def test_both_tabs_render(app_with_ollama_down):
    at = app_with_ollama_down.run()

    assert len(at.tabs) == 2


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

    # With no vector store, the PDF tab's input must be inert rather than
    # throwing when someone types into it during a demo.
    placeholders = [element.placeholder for element in at.chat_input]
    assert any("Upload a PDF above" in text for text in placeholders)
