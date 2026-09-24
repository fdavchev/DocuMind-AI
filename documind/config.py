# documind/config.py
#
# WHAT THIS FILE DOES:
# Holds every value the application can be tuned with in a single object, so no
# module has to reach out to a global constant to find out how it should behave.
#
# WHY A FROZEN DATACLASS INSTEAD OF A MODULE OF CONSTANTS:
# A module of constants can only be changed by editing the file. A config object
# is passed in, which means a test (or a future settings screen) can hand any
# part of the pipeline a different chunk size or model without touching the
# source. "Frozen" means the values cannot be reassigned after the object is
# built, so a config handed to five modules cannot be quietly changed by one of
# them — and an immutable object is safe to use as a default argument value,
# which a mutable one would not be.

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """The settings the whole pipeline runs on."""

    app_title: str = "DocuMind AI"
    app_icon: str = "🤖"

    # Models offered in the sidebar. A tuple, not a list, so the frozen config
    # cannot be mutated through it.
    available_models: tuple[str, ...] = ("llama3", "mistral", "phi3", "llava")
    default_model: str = "llava"

    # llava is the only model here that can read an image.
    vision_model: str = "llava"

    # PDF answers use llama3 rather than llava: a vision model is not optimised
    # for long document reasoning.
    answer_model: str = "llama3"

    # Turns text into vectors for FAISS. It has no LLM capability of its own.
    embedding_model: str = "nomic-embed-text"

    chunk_size: int = 500
    chunk_overlap: int = 50

    # How many chunks are retrieved per question. With several documents indexed
    # the window is widened, so one long file cannot crowd the others out.
    retrieval_k: int = 4
    retrieval_k_multi_document: int = 6

    temperature: float = 0.7
    max_tokens: int = 512

    system_prompt: str = (
        "You are a helpful, friendly, local vision-language AI assistant. "
        "You can analyze both text and images accurately and concisely. "
        "Be direct, avoid fluff, and clearly state if you cannot see an image "
        "or don't know an answer."
    )

    # OCR costs roughly a second or two per page, so a document needing more
    # than this many scanned pages is refused rather than started.
    max_ocr_pages: int = 50

    # The Tesseract language pack(s) OCR reads with. "mkd+eng" needs the
    # Macedonian traineddata installed (TESSDATA_PREFIX must point at a
    # tessdata folder containing mkd.traineddata) — see docs/guides/ for setup.
    ocr_language: str = "mkd+eng"

    # Mean word confidence (0-100) below which a recognised page is treated as
    # unreliable.
    ocr_min_confidence: float = 90.0
