"""
The failure paths a user actually hits.

Every one of these is asserted without a running Ollama and without a real
corrupt file on disk — the point is that the *translation* is testable, so the
UI never has to grow its own knowledge of httpx exception types.
"""

import httpx
import ollama
import pytest

import errors
from errors import (
    MAX_PDF_MB,
    FriendlyError,
    ModelNotPulled,
    NoTextInPdf,
    OllamaUnavailable,
    PdfTooLarge,
    UnreadablePdf,
    check_models,
    guarded_stream,
    installed_models,
    readiness,
    translate,
    validate_pdf_upload,
)
from pdf_handler import extract_pages_from_pdf

from conftest import UploadedPdf


# ── Rendering ──────────────────────────────────────────────────────────────────

def test_friendly_error_renders_message_and_hint():
    rendered = FriendlyError("It broke.", "Try turning it off and on.").render()

    assert "It broke." in rendered
    assert "Try turning it off and on." in rendered


def test_friendly_error_without_a_hint_renders_just_the_message():
    assert FriendlyError("It broke.").render() == "It broke."


def test_every_error_tells_the_user_what_to_do():
    # A message with no remedy is a traceback with better grammar.
    for error in (
        OllamaUnavailable(),
        ModelNotPulled("llama3"),
        PdfTooLarge("huge.pdf", 99.0),
        UnreadablePdf("broken.pdf"),
        NoTextInPdf("scan.pdf"),
    ):
        assert error.hint, f"{type(error).__name__} has no hint"
        assert "Traceback" not in error.render()


def test_model_not_pulled_names_the_pull_command():
    assert "ollama pull llama3" in ModelNotPulled("llama3").render()


# ── Translation ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "exc",
    [
        ConnectionError("Failed to connect to Ollama."),
        httpx.ConnectError("[WinError 10061] actively refused"),
        httpx.ConnectTimeout("timed out"),
    ],
)
def test_connection_failures_all_become_ollama_unavailable(exc):
    # ollama.list() raises a plain ConnectionError, but a streaming chat()
    # connects lazily and leaks the raw httpx error. Same thing to a user.
    assert isinstance(translate(exc), OllamaUnavailable)


def test_missing_model_response_becomes_model_not_pulled():
    exc = ollama.ResponseError('model "llama3" not found, try pulling it first')

    result = translate(exc)

    assert isinstance(result, ModelNotPulled)
    assert result.model == "llama3"


def test_other_ollama_errors_are_reported_verbatim():
    result = translate(ollama.ResponseError("server overloaded"))

    assert isinstance(result, FriendlyError)
    assert not isinstance(result, ModelNotPulled)
    assert "server overloaded" in result.message


def test_pdf_parsing_errors_become_unreadable_pdf():
    class PDFSyntaxError(Exception):
        pass

    result = translate(PDFSyntaxError("No /Root object"), filename="broken.pdf")

    assert isinstance(result, UnreadablePdf)
    assert "broken.pdf" in result.message


def test_an_already_friendly_error_passes_straight_through():
    original = NoTextInPdf("scan.pdf")

    assert translate(original) is original


def test_an_unrecognised_error_keeps_its_type_name():
    result = translate(RuntimeError("something odd"))

    assert "RuntimeError" in result.message
    assert "something odd" in result.message


# ── Pre-flight checks ──────────────────────────────────────────────────────────

class FakeListResponse:
    def __init__(self, names):
        self.models = [type("M", (), {"model": name})() for name in names]


def test_installed_models_strips_the_latest_tag(monkeypatch):
    monkeypatch.setattr(
        errors.ollama, "list", lambda: FakeListResponse(["llama3:latest", "llava:7b"])
    )

    assert installed_models() == ["llama3", "llava"]


def test_installed_models_raises_friendly_error_when_server_is_down(monkeypatch):
    def boom():
        raise ConnectionError("Failed to connect to Ollama.")

    monkeypatch.setattr(errors.ollama, "list", boom)

    with pytest.raises(OllamaUnavailable):
        installed_models()


def test_check_models_passes_when_everything_is_installed(monkeypatch):
    monkeypatch.setattr(
        errors.ollama,
        "list",
        lambda: FakeListResponse(["llama3", "nomic-embed-text", "llava"]),
    )

    assert check_models(["llama3", "nomic-embed-text"]) is None


def test_check_models_names_the_missing_one(monkeypatch):
    monkeypatch.setattr(errors.ollama, "list", lambda: FakeListResponse(["llama3"]))

    with pytest.raises(ModelNotPulled) as caught:
        check_models(["llama3", "nomic-embed-text"])

    assert caught.value.model == "nomic-embed-text"


def test_readiness_returns_the_problem_instead_of_raising(monkeypatch):
    monkeypatch.setattr(errors.ollama, "list", lambda: FakeListResponse([]))

    problem = readiness(["llama3"])

    assert isinstance(problem, ModelNotPulled)


def test_readiness_returns_none_when_ready(monkeypatch):
    monkeypatch.setattr(errors.ollama, "list", lambda: FakeListResponse(["llama3"]))

    assert readiness(["llama3"]) is None


# ── Upload validation ──────────────────────────────────────────────────────────

def test_oversized_upload_is_refused_before_parsing():
    oversized = UploadedPdf(b"x" * ((MAX_PDF_MB + 1) * 1024 * 1024), "huge.pdf")

    with pytest.raises(PdfTooLarge) as caught:
        validate_pdf_upload(oversized)

    assert "huge.pdf" in caught.value.message


def test_a_normal_upload_passes_validation(make_pdf):
    assert validate_pdf_upload(make_pdf(["short document"])) is None


def test_validation_does_not_disturb_the_read_position(make_pdf):
    pdf = make_pdf(["page one text"])

    validate_pdf_upload(pdf)

    # The file must still be readable from the start afterwards.
    assert extract_pages_from_pdf(pdf) == [(1, "page one text")]


def test_a_corrupt_file_raises_something_we_can_translate():
    garbage = UploadedPdf(b"this is definitely not a PDF", "broken.pdf")

    with pytest.raises(Exception) as caught:
        extract_pages_from_pdf(garbage)

    assert isinstance(translate(caught.value, "broken.pdf"), UnreadablePdf)


# ── Streaming ──────────────────────────────────────────────────────────────────

def test_guarded_stream_passes_tokens_through_untouched():
    assert list(guarded_stream(iter(["a", "b", "c"]))) == ["a", "b", "c"]


def test_guarded_stream_translates_a_mid_stream_failure():
    def failing():
        yield "partial answer"
        raise httpx.ConnectError("connection lost")

    stream = guarded_stream(failing())

    assert next(stream) == "partial answer"
    with pytest.raises(OllamaUnavailable):
        next(stream)


def test_a_value_error_outside_file_handling_is_not_called_a_bad_pdf():
    # Without a filename we have no reason to think a ValueError came from the
    # file; mislabelling it would send the user chasing the wrong problem.
    result = translate(ValueError("index out of range"))

    assert not isinstance(result, UnreadablePdf)
    assert "ValueError" in result.message


def test_a_value_error_while_handling_a_file_is_a_bad_pdf():
    assert isinstance(translate(ValueError("bad xref"), "broken.pdf"), UnreadablePdf)
