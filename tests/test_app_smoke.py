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
from config import CHAT_MODE, PDF_MODE

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
