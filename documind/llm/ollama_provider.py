# documind/llm/ollama_provider.py
#
# WHAT THIS FILE DOES:
# Talks to a local Ollama server, and is the only file in the project that does
# so for generation. It replaces llm_chain.py: build_llm and stream_response
# became stream_chat, stream_vision_response became stream_vision, and the
# ollama.chat call that rag_chain.py used to make itself became stream_answer.
#
# WHY THE THREE METHODS USE THREE DIFFERENT MODELS:
# Chat runs on whichever model the sidebar has selected, images always go to
# llava because it is the only model here that can see one, and document
# answers always go to llama3 because a vision model is not optimised for long
# document reasoning. Those choices live in AppConfig; `model_name` overrides
# the chat model only, which is what the sidebar switches.

import io
from collections.abc import Iterator, Sequence

import ollama
from PIL import Image
from langchain_ollama import OllamaLLM

import errors
from documind.chat.message import Message
from documind.config import AppConfig
from documind.llm.llm_provider import LLMProvider


class OllamaProvider(LLMProvider):
    """Generation backed by a local Ollama server."""

    def __init__(self, config: AppConfig, model_name: str | None = None):
        self._config = config
        self._model_name = model_name or config.default_model

        # OllamaLLM, not langchain_community's Ollama: that class is deprecated
        # and slated for removal, and emitted a warning on every app start.
        self._llm = OllamaLLM(
            model=self._model_name,
            temperature=config.temperature,
            num_predict=config.max_tokens,
        )

    @property
    def model_name(self) -> str:
        """The chat model this provider was built for."""
        return self._model_name

    def is_available(self) -> bool:
        """
        True when Ollama is reachable and this provider's chat model is pulled.

        The judgement of what a connection failure or an Ollama error means is
        already made in errors.py, so this asks that module rather than
        catching httpx exceptions a second time.
        """
        return errors.readiness([self._model_name]) is None

    def stream_chat(self, messages: Sequence[Message]) -> Iterator[str]:
        """Continues the conversation, yielding the reply piece by piece."""
        # OllamaLLM has no system-message parameter, so the system prompt is the
        # first line of the prompt itself.
        prompt_parts = [self._config.system_prompt, ""]
        for message in messages:
            role_label = "User" if message.role == "user" else "Assistant"
            prompt_parts.append(f"{role_label}: {message.content}")
        prompt_parts.append("Assistant:")

        for chunk in self._llm.stream("\n".join(prompt_parts)):
            yield chunk

    def stream_vision(self, image: bytes, prompt: str) -> Iterator[str]:
        """Answers a question about an image, yielding the reply piece by piece."""
        # Convert any format (WebP, PNG, etc.) → JPEG bytes, which LLaVA always accepts
        picture = Image.open(io.BytesIO(image)).convert("RGB")
        buffer = io.BytesIO()
        picture.save(buffer, format="JPEG")
        jpeg_bytes = buffer.getvalue()

        response = ollama.chat(
            model=self._config.vision_model,
            messages=[
                {"role": "system", "content": self._config.system_prompt},
                {
                    "role": "user",
                    "content": prompt or "Describe this image in detail.",
                    "images": [jpeg_bytes],
                },
            ],
            stream=True,
            options={
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        )
        for chunk in response:
            yield chunk["message"]["content"]

    def stream_answer(self, prompt: str) -> Iterator[str]:
        """Answers one fully written prompt, yielding the reply piece by piece."""
        stream = ollama.chat(
            model=self._config.answer_model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in stream:
            token = chunk["message"]["content"]
            if token:
                yield token
