"""
The one class that talks to Ollama, tested without Ollama.

Every call the provider makes goes through two seams — `OllamaLLM` for chat and
`ollama.chat` for images and document answers — and both are replaced here with
fakes that record what they were handed and replay a canned token stream. So
these tests pin the exact model, prompt and options each path sends, which is
what a live server would otherwise be needed to observe.
"""

import io
from datetime import datetime

import pytest
from PIL import Image

import errors
from documind.chat.message import Message
from documind.config import AppConfig
from documind.llm import ollama_provider
from documind.llm.llm_provider import LLMProvider
from documind.llm.ollama_provider import OllamaProvider


# ── Fakes ──────────────────────────────────────────────────────────────────────

class FakeLLM:
    """Stands in for OllamaLLM: records its settings, replays canned tokens."""

    built = []

    def __init__(self, model, temperature, num_predict):
        self.model = model
        self.temperature = temperature
        self.num_predict = num_predict
        self.prompts = []
        FakeLLM.built.append(self)

    def stream(self, prompt):
        self.prompts.append(prompt)
        return iter(["Hello ", "there", "."])


class FakeOllamaChat:
    """Records the call and replays a canned token stream."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return ({"message": {"content": token}} for token in self.tokens)


class FakeListResponse:
    def __init__(self, names):
        self.models = [type("M", (), {"model": name})() for name in names]


@pytest.fixture
def fake_llm(monkeypatch):
    FakeLLM.built = []
    monkeypatch.setattr(ollama_provider, "OllamaLLM", FakeLLM)
    return FakeLLM


@pytest.fixture
def fake_chat(monkeypatch):
    fake = FakeOllamaChat(["Some ", "answer", "."])
    monkeypatch.setattr(ollama_provider.ollama, "chat", fake)
    return fake


def turn(role: str, content: str) -> Message:
    return Message(role=role, content=content, timestamp=datetime.now())


def png_bytes(colour=(10, 20, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), colour).save(buffer, format="PNG")
    return buffer.getvalue()


# ── is_available ───────────────────────────────────────────────────────────────

def test_is_available_is_true_when_ollama_has_the_model(monkeypatch, fake_llm):
    monkeypatch.setattr(errors.ollama, "list", lambda: FakeListResponse(["llama3"]))

    assert OllamaProvider(AppConfig(), "llama3").is_available() is True


def test_is_available_is_false_when_ollama_is_not_running(monkeypatch, fake_llm):
    def refuse():
        raise ConnectionError("Failed to connect to Ollama.")

    monkeypatch.setattr(errors.ollama, "list", refuse)

    assert OllamaProvider(AppConfig(), "llama3").is_available() is False


def test_is_available_is_false_when_the_model_was_never_pulled(monkeypatch, fake_llm):
    monkeypatch.setattr(errors.ollama, "list", lambda: FakeListResponse(["llava"]))

    assert OllamaProvider(AppConfig(), "llama3").is_available() is False


def test_is_available_reports_rather_than_raises(monkeypatch, fake_llm):
    """A provider that cannot be reached must not blow up the status panel."""
    def explode():
        raise RuntimeError("something unexpected")

    monkeypatch.setattr(errors.ollama, "list", explode)

    assert OllamaProvider(AppConfig()).is_available() is False


# ── stream_chat ────────────────────────────────────────────────────────────────

def test_stream_chat_yields_the_model_tokens(fake_llm):
    provider = OllamaProvider(AppConfig(), "llama3")

    tokens = list(provider.stream_chat([turn("user", "hi")]))

    assert "".join(tokens) == "Hello there."


def test_stream_chat_puts_the_system_prompt_and_the_turns_in_the_prompt(fake_llm):
    config = AppConfig()
    provider = OllamaProvider(config, "llama3")

    list(
        provider.stream_chat(
            [
                turn("user", "what is in the image"),
                turn("assistant", "a cat"),
                turn("user", "what colour"),
            ]
        )
    )

    prompt = fake_llm.built[0].prompts[0]
    assert prompt.startswith(config.system_prompt)
    assert "User: what is in the image" in prompt
    assert "Assistant: a cat" in prompt
    assert prompt.endswith("Assistant:")


def test_stream_chat_uses_the_selected_model_and_the_configured_limits(fake_llm):
    config = AppConfig(temperature=0.1, max_tokens=64)

    OllamaProvider(config, "mistral")

    built = fake_llm.built[0]
    assert built.model == "mistral"
    assert built.temperature == 0.1
    assert built.num_predict == 64


def test_a_provider_without_a_model_name_uses_the_configured_default(fake_llm):
    provider = OllamaProvider(AppConfig(default_model="phi3"))

    assert provider.model_name == "phi3"
    assert fake_llm.built[0].model == "phi3"


# ── stream_vision ──────────────────────────────────────────────────────────────

def test_stream_vision_yields_the_model_tokens(fake_llm, fake_chat):
    provider = OllamaProvider(AppConfig(), "llama3")

    tokens = list(provider.stream_vision(png_bytes(), "what is this?"))

    assert "".join(tokens) == "Some answer."


def test_stream_vision_always_uses_the_vision_model(fake_llm, fake_chat):
    """The sidebar can select any chat model; only llava can read an image."""
    config = AppConfig()
    provider = OllamaProvider(config, "mistral")

    list(provider.stream_vision(png_bytes(), "what is this?"))

    assert fake_chat.calls[0]["model"] == config.vision_model


def test_stream_vision_sends_the_system_prompt_the_question_and_a_jpeg(
    fake_llm, fake_chat
):
    config = AppConfig()

    list(OllamaProvider(config).stream_vision(png_bytes(), "what is this?"))

    call = fake_chat.calls[0]
    system, user = call["messages"]
    assert system == {"role": "system", "content": config.system_prompt}
    assert user["content"] == "what is this?"
    # LLaVA always accepts JPEG, so a PNG upload is converted first.
    assert user["images"][0].startswith(b"\xff\xd8")
    assert call["stream"] is True
    assert call["options"] == {
        "temperature": config.temperature,
        "num_predict": config.max_tokens,
    }


def test_stream_vision_falls_back_to_a_default_question(fake_llm, fake_chat):
    list(OllamaProvider(AppConfig()).stream_vision(png_bytes(), ""))

    assert fake_chat.calls[0]["messages"][1]["content"] == "Describe this image in detail."


# ── stream_answer ──────────────────────────────────────────────────────────────

def test_stream_answer_yields_the_model_tokens(fake_llm, fake_chat):
    tokens = list(OllamaProvider(AppConfig()).stream_answer("CONTEXT\nQUESTION"))

    assert "".join(tokens) == "Some answer."


def test_stream_answer_sends_the_prompt_unchanged_to_the_answer_model(
    fake_llm, fake_chat
):
    config = AppConfig()

    list(OllamaProvider(config, "llava").stream_answer("the built prompt"))

    call = fake_chat.calls[0]
    # Document answers use llama3 whatever the chat model is.
    assert call["model"] == config.answer_model
    assert call["messages"] == [{"role": "user", "content": "the built prompt"}]
    assert call["stream"] is True


def test_stream_answer_skips_empty_tokens(fake_llm, monkeypatch):
    monkeypatch.setattr(
        ollama_provider.ollama, "chat", FakeOllamaChat(["Answer", "", " text"])
    )

    assert list(OllamaProvider(AppConfig()).stream_answer("p")) == ["Answer", " text"]


# ── The abstraction itself ─────────────────────────────────────────────────────

def test_ollama_provider_is_an_llm_provider(fake_llm):
    assert isinstance(OllamaProvider(AppConfig()), LLMProvider)


def test_a_test_double_can_stand_in_for_the_real_provider():
    """
    The point of the ABC: anything implementing the four methods is accepted
    wherever OllamaProvider is, with no server anywhere in sight.
    """

    class FakeProvider(LLMProvider):
        def is_available(self):
            return True

        def stream_chat(self, messages):
            yield "chat"

        def stream_vision(self, image, prompt):
            yield "vision"

        def stream_answer(self, prompt):
            yield "answer"

    provider = FakeProvider()

    assert isinstance(provider, LLMProvider)
    assert list(provider.stream_answer("anything")) == ["answer"]


def test_a_provider_missing_a_method_cannot_be_built():
    class Incomplete(LLMProvider):
        def is_available(self):
            return True

    with pytest.raises(TypeError):
        Incomplete()
