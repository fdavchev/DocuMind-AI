# documind/rag/rag_pipeline.py
#
# WHAT THIS FILE DOES:
# Runs the two things the PDF side of the app does, end to end. `ingest` takes
# an uploaded file and makes it searchable; `ask` takes a question and streams a
# cited answer. Everything between those two calls — picking a loader, cutting
# pages into chunks, embedding them, retrieving the closest passages, writing the
# prompt around them — happens in here, so the UI never has to name a step.
#
# WHY IT OWNS ALMOST NO WORK ITSELF:
# It is built out of the four objects the earlier steps produced: a
# LoaderFactory, a TextSplitter, a VectorStore and an LLMProvider. It reads a
# file by asking the factory for a loader, chunks by asking the splitter, indexes
# and retrieves by asking the store, and generates by asking the provider. What
# is genuinely its own is the order of those calls and the prompt built around
# what came back — the RAG idea itself. Every collaborator arrives through the
# constructor, which is why the whole pipeline can be exercised offline: the
# tests hand it a fake embedding model and a provider that replays canned tokens,
# and nothing in this file notices.
#
# WHY THE PROMPT AND THE CITATIONS LIVE HERE:
# They used to be four module-level functions in `rag_chain.py`. They belong to
# whoever did the retrieving, because they depend on the order the passages came
# back in: the `[n]` markers the model is told to cite are positions in the list
# this class retrieved, and the Sources panel underneath the answer has to number
# the same passages the same way. Keeping both on the object that holds that
# list is what makes the two sides impossible to get out of step; a separate
# prompt-builder class would only have been handed the list right back.
#
# WHY `last_sources`:
# The answer streams token by token, so the UI cannot wait for it to finish
# before rendering the Sources panel. Retrieval has already happened by the time
# `ask` returns its iterator, so the passages are available immediately and stay
# available until the next question replaces them.

import time
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from documind.config import AnswerLanguage, AppConfig
from documind.documents.loader_factory import LoaderFactory
from documind.documents.models import Chunk, Document
from documind.documents.text_splitter import TextSplitter
from documind.llm.llm_provider import LLMProvider
from documind.rag.vector_store import VectorStore
from errors import EmptyDocumentError, NoDocumentsIndexed

# How much of a passage the Sources panel shows before trimming it. Long enough
# to recognise the passage, short enough that four of them still fit on screen.
EXCERPT_LIMIT = 200

# How much of a document's first passage goes into its DOCUMENT line. A title
# page's opening holds the title, the authors and their affiliations; 400
# characters fits two authors' affiliations where 200 cut the second one off.
# It never needs to exceed `chunk_size`, since it is taken from one chunk.
OPENING_TEXT_LIMIT = 400


@dataclass(frozen=True)
class IngestReport:
    """
    What one upload turned out to be: the numbers the UI reports back.

    These were computed inline in the upload handler and then thrown away — the
    chunk count survived only as far as the success message, and how long the
    indexing took was never measured at all even though the spinner promises
    "~10-30 seconds". Returning them as one object means the caller gets the
    whole outcome of an ingest rather than a loose `len(chunks)`, and a later
    phase measuring performance already has the numbers it needs.

    `ocr_confidences` holds one `(page_number, confidence)` pair per page that
    was read by OCR, in page order. It is every such page, not only the
    doubtful ones: what counts as too low to trust is the UI's call, made with
    `AppConfig.ocr_min_confidence`, so the pipeline reports the facts and needs
    no threshold of its own.
    """

    document_name: str
    page_count: int
    chunk_count: int
    ocr_page_count: int
    elapsed_seconds: float
    ocr_confidences: tuple[tuple[int, float], ...] = ()

    @property
    def used_ocr(self) -> bool:
        """True when any page had to be read by OCR rather than extracted."""
        return self.ocr_page_count > 0


class RagPipeline:
    """Uploads in, cited answers out — the whole document pipeline as one object."""

    def __init__(
        self,
        config: AppConfig,
        loader_factory: LoaderFactory,
        splitter: TextSplitter,
        vector_store: VectorStore,
        provider: LLMProvider,
    ):
        self._config = config
        self._loader_factory = loader_factory
        self._splitter = splitter
        self._vector_store = vector_store
        self._provider = provider
        self._last_sources: tuple[Chunk, ...] = ()
        # One DOCUMENT line per ingested file, keyed by its name. Kept here
        # rather than in the index so it needs no embedding and cannot lose a
        # similarity contest; `ask` sends only the lines of files the store
        # still holds, so a file removed from the store drops out with it.
        self._document_lines: dict[str, str] = {}

    # ── Making a document answerable ──────────────────────────────────────────

    def ingest(self, file, name: str | None = None) -> IngestReport:
        """
        Reads an uploaded file, chunks it, and adds it to the searchable index.

        `name` overrides the name the file arrived under, which is what a
        citation shows; left out, the file's own `.name` is used.

        Raises the same failures the steps themselves raise — `UnsupportedFileError`
        for a file type no loader claims, `EmptyDocumentError` for a file that
        yielded no text, `ScannedPdfTooLong` for a scan too long to OCR — all of
        them `FriendlyError`s the UI already knows how to render.
        """
        started = time.perf_counter()

        filename = name or getattr(file, "name", None) or ""
        loader = self._loader_factory.create_loader(filename)
        document = loader.load(file, name=filename or None)

        chunks = self._splitter.split(document)
        if not chunks:
            # The file had text, but none of it was a passage worth indexing —
            # nothing but page numbers or stray symbols. Saying so plainly beats
            # indexing nothing and reporting success.
            raise EmptyDocumentError(document.name)

        # `add` builds the index when there is nothing to add to, so the first
        # upload and the tenth are the same call here.
        self._vector_store.add(chunks)
        self._document_lines[document.name] = self._describe_document(
            document, chunks[0]
        )

        return IngestReport(
            document_name=document.name,
            page_count=document.page_count,
            chunk_count=len(chunks),
            ocr_page_count=document.ocr_page_count,
            elapsed_seconds=time.perf_counter() - started,
            ocr_confidences=tuple(
                (page.number, page.ocr_confidence)
                for page in document.pages
                if page.used_ocr and page.ocr_confidence is not None
            ),
        )

    # ── Answering a question about them ───────────────────────────────────────

    def ask(self, question: str) -> Iterator[str]:
        """
        Retrieves the passages that answer the question and streams the answer.

        Retrieval and prompt building happen before this returns; only the
        generation is deferred to the iterator. That ordering is deliberate: a
        failure to reach the embedding model raises here, where the caller can
        show an error, rather than halfway through a chat bubble — and
        `last_sources` is already filled in by the time the first token arrives,
        so the UI can render the Sources panel alongside the streaming answer.

        Raises `NoDocumentsIndexed` if nothing has been ingested yet.
        """
        # Cleared first, so a question that fails to retrieve cannot leave the
        # previous answer's sources standing under it.
        self._last_sources = ()

        if not self._vector_store.is_ready:
            raise NoDocumentsIndexed()

        chunks = self._vector_store.search(question)
        self._last_sources = tuple(chunks)

        # The DOCUMENT lines go first and do not depend on the question, so
        # "what is this paper called?" is answerable even when the title page
        # ranks nowhere near the top passages.
        documents = self.build_documents_block()
        passages = self.build_context_block(chunks)
        context = f"{documents}\n\n---\n\n{passages}" if documents else passages

        prompt = self.build_rag_prompt(context, question)
        return self._provider.stream_answer(prompt)

    @property
    def last_sources(self) -> tuple[Chunk, ...]:
        """
        The passages the most recent `ask` retrieved, in the order they were
        numbered in the prompt — so `last_sources[0]` is the `[1]` the answer
        cites. A tuple, because the answer was generated from exactly these
        passages and nothing downstream may edit the record of that.
        """
        return self._last_sources

    # ── Citations and the prompt ──────────────────────────────────────────────

    def format_citation(self, chunk: Chunk) -> str:
        """
        One passage's provenance as human-readable text:
        "report.pdf, p. 4" — or just the filename if the page is unknown.
        """
        source = chunk.source_document or "document"
        page = chunk.page_number
        return f"{source}, p. {page}" if page else source

    def build_context_block(self, chunks: Sequence[Chunk]) -> str:
        """
        Turns retrieved chunks into the CONTEXT section of the prompt, with each
        passage numbered so the model has a concrete marker to cite.

            [1] report.pdf, p. 4
            <chunk text>
        """
        blocks = []
        for index, chunk in enumerate(chunks, start=1):
            blocks.append(f"[{index}] {self.format_citation(chunk)}\n{chunk.text}")
        return "\n\n---\n\n".join(blocks)

    def build_documents_block(self) -> str:
        """
        One line per document the store currently holds, saying what it is:

            DOCUMENT: paper.pdf — Title: Attention Is All You Need — Authors: … — Opening lines: …

        Only files ingested through this pipeline have a line; an empty string
        means there is nothing to describe.
        """
        return "\n".join(
            self._document_lines[name]
            for name in self._vector_store.sources
            if name in self._document_lines
        )

    def _describe_document(self, document: Document, first_chunk: Chunk) -> str:
        """
        The DOCUMENT line for one file: its name, the title and authors it
        declares, and the opening of its first passage. The opening is added
        even when both are declared, because it carries what the metadata
        fields never do, such as the authors' affiliations.
        """
        parts = [f"DOCUMENT: {document.name}"]
        if document.metadata.title:
            parts.append(f"Title: {document.metadata.title}")
        if document.metadata.authors:
            parts.append(f"Authors: {document.metadata.authors}")

        opening = " ".join(first_chunk.text.split())
        if len(opening) > OPENING_TEXT_LIMIT:
            opening = opening[:OPENING_TEXT_LIMIT].rstrip() + "…"
        parts.append(f"Opening lines: {opening}")

        return " — ".join(parts)

    def format_sources_markdown(self, chunks: Sequence[Chunk] | None = None) -> str:
        """
        The "Sources" list shown under an answer in the UI, matching the [n]
        markers the model cites.

        Defaults to the passages of the most recent answer, which is what the UI
        wants every time — it is numbering the list it was just given.
        """
        chunks = self._last_sources if chunks is None else chunks

        if not chunks:
            return "_No sources retrieved._"

        lines = []
        for index, chunk in enumerate(chunks, start=1):
            excerpt = " ".join(chunk.text.split())
            if len(excerpt) > EXCERPT_LIMIT:
                excerpt = excerpt[:EXCERPT_LIMIT].rstrip() + "…"
            lines.append(f"**[{index}] {self.format_citation(chunk)}** — {excerpt}")
        return "\n\n".join(lines)

    def build_rag_prompt(self, context: str, question: str) -> str:
        """
        Builds the full prompt that gets sent to the LLM.

        The prompt has four parts:
        1. Instruction — tells the model its role and rules, citations included
        2. Context     — a DOCUMENT line per file, then the numbered passages
                         retrieved from the vector store
        3. Question    — the user's actual question
        4. Language    — which language to answer in, picked from the question's
                         alphabet and placed right before ANSWER:, the only spot
                         where llama3 reliably obeys it
        """
        language = self._answer_language_for(question)
        prompt = f"""You are a helpful assistant that answers questions strictly based on the provided document context.

Rules:
- Only use information from the CONTEXT below to answer.
- Lines starting with DOCUMENT: give each file's name, its title and authors when declared, and its opening lines. Use them for questions about the document itself, such as its title, authors or the authors' affiliations.
- Each passage is labelled [n] with its source file and page number.
- Cite the passages you used inline, e.g. "the deadline is March 1 [1]".
- If the answer is not in the context, say "{language.not_found_message}"
- Be concise and direct.
- Do not make up information, and never cite a passage number that is not listed below.

CONTEXT:
{context}

QUESTION:
{question}

{language.instruction}

ANSWER:"""

        return prompt

    def _answer_language_for(self, question: str) -> AnswerLanguage:
        """
        Macedonian when most of the question's letters are Cyrillic, otherwise
        English — including a question with no letters or an even split, since
        English is what llama3 falls back to anyway.
        """
        cyrillic_letters = 0
        latin_letters = 0
        for character in question:
            if not character.isalpha():
                continue
            unicode_name = unicodedata.name(character, "")
            if unicode_name.startswith("CYRILLIC"):
                cyrillic_letters += 1
            elif unicode_name.startswith("LATIN"):
                latin_letters += 1

        if cyrillic_letters > latin_letters:
            return self._config.macedonian
        return self._config.english
