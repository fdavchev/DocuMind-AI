# documind/llm/__init__.py
#
# The language-model side of the app: the contract every provider implements,
# and the one implementation that talks to a local Ollama server.

from documind.llm.llm_provider import LLMProvider
from documind.llm.ollama_provider import OllamaProvider

__all__ = ["LLMProvider", "OllamaProvider"]
