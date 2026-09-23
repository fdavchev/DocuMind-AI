# documind/rag/vector_store.py
#
# WHAT THIS FILE DOES:
# Holds the searchable index of everything the user has uploaded. Chunks go in,
# and the passages most similar to a question come back out — as Chunks again,
# still carrying the file and page they were found on.
#
# HOW THE SEARCH WORKS:
# Each chunk is turned into a vector (a list of ~768 numbers) by the
# nomic-embed-text model running locally in Ollama, and the vectors are kept in
# a FAISS index. A question is turned into a vector the same way, and FAISS
# returns the chunks whose vectors sit closest to it. Think of every chunk as a
# point in space: similar text lands nearby, and FAISS finds the nearest
# neighbours fast.
#
# WHY A CLASS AROUND FAISS:
# FAISS does not know what a Chunk is. It stores LangChain Documents: a string
# of page_content plus an untyped metadata dictionary. Something has to flatten
# a Chunk into that dictionary on the way in and rebuild it on the way out, and
# this class is the only place in the project allowed to do it. Callers hand it
# Chunks and receive Chunks; they never write the literal "source" or "page",
# never touch a FAISS object, and never find out that an index has to exist
# before it can be searched. Replacing FAISS with Chroma or pgvector is then a
# change inside this file, because no other file names the library at all.
#
# MULTI-DOCUMENT:
# One index holds the chunks of several documents at once. Each chunk keeps its
# source filename, so an answer can draw on the best passages across every file
# and still say which one each came from. `add()` is what makes that work: a
# second upload joins the existing index instead of replacing it. `remove()` is
# its counterpart: one file's chunks leave the index and the others stay.
#
# NO SAVING TO DISK:
# There is deliberately no save/load here. The index lives for as long as the
# session does, which is the documented decision in DECISIONS.md #9 — a
# persisted index would have to be invalidated whenever the embedding model or
# the chunk settings changed, and nothing in the app needs it yet.

from collections.abc import Sequence

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

from documind.config import AppConfig
from documind.documents.models import Chunk

# The two metadata keys FAISS stores for us. They are written once here and read
# once here, so a typo cannot survive a single test run — which is exactly what
# the dictionary form could not promise when these keys were spelled out at
# several call sites.
SOURCE_KEY = "source"
PAGE_KEY = "page"


class VectorStore:
    """The searchable index of the uploaded documents' chunks."""

    def __init__(self, config: AppConfig, embeddings=None):
        self._config = config
        # `embeddings` is injectable so the tests can index and search for real
        # without a running Ollama (DECISIONS.md #4). Left alone, the configured
        # embedding model is built on first use rather than in the constructor,
        # so creating a VectorStore never reaches for a model.
        self._embeddings = embeddings
        self._store: FAISS | None = None

    # ── Building the index ────────────────────────────────────────────────────

    def build(self, chunks: Sequence[Chunk]) -> None:
        """
        Embeds every chunk into a brand new index, replacing anything held.

        This is the first upload's path; it takes a few seconds to half a minute
        depending on the document's length and the machine.
        """
        self._store = FAISS.from_documents(
            documents=self._as_documents(chunks), embedding=self._resolve_embeddings()
        )

    def add(self, chunks: Sequence[Chunk]) -> None:
        """
        Adds another document's chunks to the index already held.

        This is what makes multi-document Q&A work: a second upload joins the
        same index rather than replacing it, so a question is answered from
        every file at once. Adding to a store that holds nothing yet simply
        builds it, so a caller never has to ask whether this upload is the first
        one — that question was the one branch the old procedural upload handler
        could get wrong.
        """
        if self._store is None:
            self.build(chunks)
            return

        self._store.add_documents(self._as_documents(chunks))

    def remove(self, source_name: str) -> None:
        """
        Takes one document's chunks out of the index, leaving the rest searchable.

        This is what lets the user drop a single file without clearing
        everything. The chunks are deleted by id rather than the index being
        rebuilt from what is left: a rebuild would send every remaining chunk
        back through the embedding model, which takes as long as the original
        uploads and needs Ollama to be running just to forget a file.

        Removing the last document returns the store to the "nothing indexed
        yet" state rather than keeping an empty index, so `is_ready` and
        `sources` read exactly as they did before the first upload. A name that
        is not indexed is a no-op, since there is nothing of it to remove.
        """
        if self._store is None:
            return

        ids_to_delete = [
            document_id
            for document_id, document in self._store.docstore._dict.items()
            if document.metadata.get(SOURCE_KEY) == source_name
        ]
        if not ids_to_delete:
            return

        if len(ids_to_delete) == len(self._store.docstore._dict):
            self._store = None
            return

        self._store.delete(ids_to_delete)

    # ── Searching it ──────────────────────────────────────────────────────────

    def search(self, question: str, k: int | None = None) -> list[Chunk]:
        """
        The `k` passages most similar to the question, as Chunks.

        The page number and filename come back with each passage, which is what
        makes a citation possible: they were stored alongside the text when it
        was indexed and are read back off the same two keys here.

        `k` is how many passages come back — more context, but a slower and
        longer prompt. Left unset it follows the configured default, which is
        wider once several documents are indexed (see `_default_k`).
        """
        if self._store is None:
            raise RuntimeError(
                "No documents are indexed yet — call build() or add() first."
            )

        documents = self._store.similarity_search(question, k=self._resolve_k(k))
        return [self._as_chunk(document) for document in documents]

    @property
    def is_ready(self) -> bool:
        """True once there is an index to search."""
        return self._store is not None

    @property
    def sources(self) -> tuple[str, ...]:
        """The filenames currently indexed, sorted — what the UI lists."""
        if self._store is None:
            return ()

        names = {
            document.metadata.get(SOURCE_KEY)
            for document in self._store.docstore._dict.values()
            if document.metadata.get(SOURCE_KEY)
        }
        return tuple(sorted(names))

    # ── The boundary with LangChain and FAISS ─────────────────────────────────

    def _as_documents(self, chunks: Sequence[Chunk]) -> list[Document]:
        """Our Chunks in the only shape FAISS understands."""
        return [
            Document(
                page_content=chunk.text,
                metadata={
                    SOURCE_KEY: chunk.source_document,
                    PAGE_KEY: chunk.page_number,
                },
            )
            for chunk in chunks
        ]

    def _as_chunk(self, document: Document) -> Chunk:
        """
        A retrieved LangChain Document back as one of our Chunks.

        The other half of the conversion: what went in as typed fields comes out
        of an untyped dictionary here, and nowhere else. The fallbacks cover a
        passage indexed without provenance — an empty filename and page 0 say
        "unknown" plainly rather than inventing a page a citation could claim.
        """
        return Chunk(
            text=document.page_content,
            page_number=document.metadata.get(PAGE_KEY, 0),
            source_document=document.metadata.get(SOURCE_KEY, ""),
        )

    # ── Small decisions the caller should not have to make ────────────────────

    def _resolve_embeddings(self):
        if self._embeddings is None:
            self._embeddings = OllamaEmbeddings(model=self._config.embedding_model)
        return self._embeddings

    def _resolve_k(self, k: int | None) -> int:
        return self._default_k() if k is None else k

    def _default_k(self) -> int:
        """
        How many passages to retrieve when the caller did not say.

        With one document, the configured window is a reasonable amount of
        context. With several, a single long file can plausibly fill every slot
        and crowd out the shorter one holding the answer, so the window widens
        (DECISIONS.md #3).
        """
        if len(self.sources) <= 1:
            return self._config.retrieval_k
        return self._config.retrieval_k_multi_document
