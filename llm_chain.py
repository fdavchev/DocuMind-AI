# llm_chain.py

import io
from collections.abc import Sequence

import ollama
from PIL import Image
from langchain_ollama import OllamaLLM

from documind.chat.message import Message
from documind.config import AppConfig


def build_llm(model_name: str | None = None, config: AppConfig = AppConfig()):
    # OllamaLLM, not langchain_community's Ollama: that class is deprecated and
    # slated for removal, and emitted a warning on every app start.
    return OllamaLLM(
        model=model_name or config.default_model,
        temperature=config.temperature,
        num_predict=config.max_tokens,
    )


def stream_response(
    llm, messages: Sequence[Message], config: AppConfig = AppConfig()
):
    # OllamaLLM has no system-message parameter, so the system prompt is the
    # first line of the prompt itself.
    prompt_parts = [config.system_prompt, ""]
    for message in messages:
        role_label = "User" if message.role == "user" else "Assistant"
        prompt_parts.append(f"{role_label}: {message.content}")
    prompt_parts.append("Assistant:")
    prompt = "\n".join(prompt_parts)
    for chunk in llm.stream(prompt):
        yield chunk


def stream_vision_response(
    image_bytes: bytes,
    user_prompt: str,
    model_name: str | None = None,
    config: AppConfig = AppConfig(),
):
    # Convert any format (WebP, PNG, etc.) → JPEG bytes, which LLaVA always accepts
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    jpeg_bytes = buffer.getvalue()

    response = ollama.chat(
        model=model_name or config.vision_model,
        messages=[
            {"role": "system", "content": config.system_prompt},
            {
                "role": "user",
                "content": user_prompt or "Describe this image in detail.",
                "images": [jpeg_bytes],
            },
        ],
        stream=True,
        options={
            "temperature": config.temperature,
            "num_predict": config.max_tokens,
        },
    )
    for chunk in response:
        yield chunk["message"]["content"]
