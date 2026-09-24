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
class AnswerLanguage:
    """
    One language a PDF answer can come back in, with the prompt text that asks
    for it.

    `instruction` goes directly before `ANSWER:` in the prompt, where llama3
    actually follows it; `not_found_message` is the sentence the model is told
    to give when the context does not hold the answer.
    """

    instruction: str
    not_found_message: str


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
    # The multilingual v2 model, because v1 is English-only and could not tell
    # Macedonian passages apart (DECISIONS.md #20).
    embedding_model: str = "nomic-embed-text-v2-moe"

    # nomic-embed-text-v2-moe was trained with a task prefix on every input,
    # and embeds more accurately when it gets one: passages are indexed as
    # documents and questions are embedded as queries. They belong to the model above, so a
    # different embedding model needs its own prefixes (or empty strings).
    embedding_document_prefix: str = "search_document: "
    embedding_query_prefix: str = "search_query: "

    # How many chunks go to the embedding model in one request. A single request
    # carrying hundreds of texts intermittently fails against a local Ollama on
    # Windows; batches of 64 were measured reliable (DECISIONS.md #17).
    embedding_batch_size: int = 64

    chunk_size: int = 500
    chunk_overlap: int = 50

    # A chunk with fewer letters than this is dropped rather than indexed. A
    # fragment such as a lone ")" left at a page end embeds as a vague,
    # all-purpose vector that sits close to many questions and crowds real
    # passages out of the results.
    min_chunk_letters: int = 3

    # How many chunks are retrieved per question. With several documents indexed
    # the window is widened, so one long file cannot crowd the others out.
    retrieval_k: int = 4
    retrieval_k_multi_document: int = 6

    temperature: float = 0.7
    max_tokens: int = 512

    # The two languages a PDF answer is written in, matching `ocr_language`
    # below. A question written mostly in Cyrillic is answered in Macedonian,
    # anything else in English. llama3 drifts into English unless the prompt
    # names the language outright, so each one carries its own instruction
    # rather than a generic "same language as the question" (DECISIONS.md #21).
    macedonian: AnswerLanguage = AnswerLanguage(
        instruction=(
            "Respond only in Macedonian (македонски јазик), the language of "
            "the question. Do not use English."
        ),
        not_found_message="Не можев да ја најдам таа информација во документот.",
    )
    english: AnswerLanguage = AnswerLanguage(
        instruction="Respond only in English, the language of the question.",
        not_found_message="I couldn't find that information in the document.",
    )

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
