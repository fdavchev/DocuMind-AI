# errors.py
#
# WHAT THIS FILE DOES:
# Turns the four failure modes a user actually hits into messages they can act
# on, instead of a Python traceback rendered inside the Streamlit page:
#
#   1. Ollama isn't running
#   2. A required model hasn't been pulled
#   3. The uploaded PDF is too big to index in reasonable time
#   4. The uploaded file is corrupt, or is a scanned image with no text layer
#
# WHY A SEPARATE MODULE?
# The UI should not contain the knowledge of what an httpx.ConnectError means.
# Keeping the translation here means every call site handles failure the same
# way — catch FriendlyError, render it — and the mapping itself is unit-testable
# without a running server.

import os

import httpx
import ollama

# Indexing time scales with page count. Past this size the "10-30 seconds"
# promise in the UI stops being true, so we refuse it up front rather than
# leaving the user watching a spinner with no idea whether it will finish.
MAX_PDF_MB = 25

# The models each tab needs, so the readiness check can name the missing one.
CHAT_MODELS = ["llava"]
PDF_MODELS = ["llama3", "nomic-embed-text"]

# ollama.list() wraps connection failures in a plain ConnectionError, but a
# streaming ollama.chat() connects lazily and surfaces the raw httpx error.
# Both mean the same thing to a user.
_CONNECTION_ERRORS = (
    ConnectionError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
)


class FriendlyError(Exception):
    """
    An error we can explain. `message` says what went wrong, `hint` says what
    to do about it — usually a command the user can copy.
    """

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def render(self) -> str:
        """Markdown for st.error()."""
        return f"{self.message}\n\n{self.hint}" if self.hint else self.message


def ollama_host() -> str:
    """Where we expect to find Ollama — the compose setup overrides this."""
    return os.getenv("OLLAMA_HOST", "http://localhost:11434")


class OllamaUnavailable(FriendlyError):
    def __init__(self):
        super().__init__(
            "**Ollama isn't running.** This app talks to a local Ollama server "
            f"and can't reach one at `{ollama_host()}`.",
            "Start it with `ollama serve` (or launch the Ollama desktop app), "
            "then try again.",
        )


class ModelNotPulled(FriendlyError):
    def __init__(self, model: str):
        super().__init__(
            f"**The model `{model}` isn't installed.** Ollama is running, but "
            "this model hasn't been downloaded yet.",
            f"Pull it with `ollama pull {model}` — then reload this page.",
        )
        self.model = model


class PdfTooLarge(FriendlyError):
    def __init__(self, filename: str, size_mb: float):
        super().__init__(
            f"**{filename} is {size_mb:.1f} MB**, over the {MAX_PDF_MB} MB limit. "
            "Indexing a file this large would take many minutes.",
            "Split it into smaller PDFs, or raise `MAX_PDF_MB` in `errors.py` "
            "if you're willing to wait.",
        )


class UnreadablePdf(FriendlyError):
    def __init__(self, filename: str):
        super().__init__(
            f"**{filename} couldn't be read.** The file appears to be corrupt, "
            "password-protected, or not a PDF.",
            "Try opening it in a PDF reader to confirm it's intact, then "
            "re-upload it.",
        )


class NoTextInPdf(FriendlyError):
    def __init__(self, filename: str):
        super().__init__(
            f"**No text could be extracted from {filename}.** It's most likely a "
            "scanned document — an image of a page rather than text.",
            "OCR isn't supported yet. Try a PDF that was exported from a text "
            "document rather than scanned.",
        )


# ── Translation ────────────────────────────────────────────────────────────────

def translate(exc: Exception, filename: str | None = None) -> FriendlyError:
    """
    Maps any exception raised by the pipeline onto a FriendlyError.

    Anything we don't recognise is passed through with its own text — better a
    terse unknown error than a swallowed one, and the type name is still there
    for a bug report.
    """
    if isinstance(exc, FriendlyError):
        return exc

    if isinstance(exc, _CONNECTION_ERRORS):
        return OllamaUnavailable()

    if isinstance(exc, ollama.ResponseError):
        text = str(exc).lower()
        if "not found" in text or "try pulling" in text:
            model = _model_name_from_error(str(exc))
            return ModelNotPulled(model or "the requested model")
        return FriendlyError(
            f"**Ollama returned an error.** {exc}",
            "Check the terminal running `ollama serve` for details.",
        )

    # pdfplumber wraps parsing failures in PdfminerException; match on the name
    # so we don't take a hard dependency on pdfminer's exception hierarchy.
    if "pdf" in type(exc).__name__.lower():
        return UnreadablePdf(filename or "The file")

    # A ValueError/OSError is only read as a bad file when we were handling one —
    # otherwise it could have come from anywhere in the pipeline and calling it
    # a corrupt PDF would send the user chasing the wrong problem.
    if filename is not None and isinstance(exc, (ValueError, OSError)):
        return UnreadablePdf(filename)

    return FriendlyError(
        f"**Something went wrong.** `{type(exc).__name__}: {exc}`",
        "If this keeps happening, please report it with the message above.",
    )


def _model_name_from_error(text: str) -> str | None:
    """Pulls the model name out of Ollama's "model 'x' not found" message."""
    for quote in ('"', "'"):
        if text.count(quote) >= 2:
            return text.split(quote)[1]
    return None


# ── Pre-flight checks ──────────────────────────────────────────────────────────

def installed_models() -> list[str]:
    """
    Names of the models Ollama has locally, without the `:latest` suffix.
    Raises OllamaUnavailable if the server can't be reached.
    """
    try:
        response = ollama.list()
    except Exception as exc:
        raise translate(exc) from exc

    # ollama>=0.4 returns a ListResponse object; older versions returned a dict.
    entries = getattr(response, "models", None)
    if entries is None and isinstance(response, dict):
        entries = response.get("models")

    names = []
    for model in entries or []:
        name = getattr(model, "model", None) or model.get("model", "")
        if name:
            names.append(name.split(":")[0])
    return names


def check_models(required: list[str]) -> None:
    """
    Raises OllamaUnavailable if the server is down, or ModelNotPulled naming the
    first missing model. Returns None when everything needed is present.
    """
    available = installed_models()
    for model in required:
        if model not in available:
            raise ModelNotPulled(model)


def readiness(required: list[str]) -> FriendlyError | None:
    """Non-raising form of check_models, for rendering a status panel."""
    try:
        check_models(required)
    except FriendlyError as exc:
        return exc
    return None


def validate_pdf_upload(uploaded_file) -> None:
    """Size gate, run before we spend time parsing. Raises PdfTooLarge."""
    size_bytes = getattr(uploaded_file, "size", None)
    if size_bytes is None:
        position = uploaded_file.tell()
        uploaded_file.seek(0, 2)
        size_bytes = uploaded_file.tell()
        uploaded_file.seek(position)

    size_mb = size_bytes / (1024 * 1024)
    if size_mb > MAX_PDF_MB:
        raise PdfTooLarge(getattr(uploaded_file, "name", "The file"), size_mb)


def guarded_stream(stream, filename: str | None = None):
    """
    Wraps a token generator so a mid-stream failure surfaces as a FriendlyError
    rather than a traceback in the middle of the chat bubble.
    """
    try:
        for token in stream:
            yield token
    except Exception as exc:
        raise translate(exc, filename) from exc
