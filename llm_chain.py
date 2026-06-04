# llm_chain.py

import ollama
from langchain_community.llms import Ollama
from langchain_ollama import ChatOllama
from config import DEFAULT_MODEL


def build_llm(model_name: str = DEFAULT_MODEL):
    return Ollama(model=model_name)


def stream_response(llm, history: list):
    prompt_parts = []
    for msg in history:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        prompt_parts.append(f"{role_label}: {msg['content']}")
    prompt_parts.append("Assistant:")
    prompt = "\n".join(prompt_parts)
    for chunk in llm.stream(prompt):
        yield chunk


def stream_vision_response(image_bytes: bytes, user_prompt: str, model_name: str = "llava"):
    import ollama
    from PIL import Image
    import io

    # Convert any format (WebP, PNG, etc.) → JPEG bytes, which LLaVA always accepts
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    jpeg_bytes = buffer.getvalue()

    response = ollama.chat(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": user_prompt or "Describe this image in detail.",
                "images": [jpeg_bytes],
            }
        ],
        stream=True,
    )
    for chunk in response:
        yield chunk["message"]["content"]