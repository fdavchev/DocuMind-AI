# documind/llm/llm_provider.py
#
# WHAT THIS FILE DOES:
# Describes what the application needs from a language model, and nothing about
# where that model comes from. Four things: say whether you are usable, hold a
# conversation, look at an image, and answer one already-written prompt.
#
# WHY AN ABSTRACT CLASS WHEN THERE IS ONLY ONE IMPLEMENTATION:
# Because "only one" is a fact about today, not about the design. Every module
# above this one is written against these four method names, so a second
# implementation — a different backend, or a test double that returns canned
# tokens without a server — is accepted everywhere the real one is, with no
# change above it. The abstract methods are what make that promise checkable:
# a subclass that forgets one cannot be instantiated at all.

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence

from documind.chat.message import Message


class LLMProvider(ABC):
    """The four things the application asks of a language model."""

    @abstractmethod
    def is_available(self) -> bool:
        """
        True when this provider could answer right now.

        Never raises: a provider that cannot be reached is a `False`, not an
        exception, so the caller can render a status panel instead of a
        traceback.
        """

    @abstractmethod
    def stream_chat(self, messages: Sequence[Message]) -> Iterator[str]:
        """Continues a conversation, yielding the reply piece by piece."""

    @abstractmethod
    def stream_vision(self, image: bytes, prompt: str) -> Iterator[str]:
        """Answers a question about an image, yielding the reply piece by piece."""

    @abstractmethod
    def stream_answer(self, prompt: str) -> Iterator[str]:
        """
        Answers one fully written prompt, yielding the reply piece by piece.

        This is the generation half of the RAG pipeline. It takes the finished
        prompt rather than the question and the retrieved passages, so the
        provider never has to know what retrieval or citations are — assembling
        that prompt stays with the pipeline that did the retrieving.
        """
