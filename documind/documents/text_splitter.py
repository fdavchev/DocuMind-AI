# documind/documents/text_splitter.py
#
# WHAT THIS FILE DOES:
# Cuts a Document into Chunks — the small, overlapping passages that get
# embedded, stored in FAISS, and put into a prompt. Every Chunk it produces
# knows which document and which page it came from.
#
# WHY CHUNKS?
# A PDF might be 100 pages. We can't send all of it to the LLM at once (too
# many tokens). Instead we cut it into ~500-character pieces, store them, and
# only send the 3-5 most relevant pieces per question.
#
# WHY OVERLAP?
# If a sentence is split across two chunks, the overlap (50 chars) ensures
# neither chunk loses context at its edges.
#
# WHY SPLIT PAGE-BY-PAGE INSTEAD OF ONE BIG STRING?
# Because a chunk that straddles a page boundary can't be cited honestly: it
# has no single true page number, so "p. 4" in an answer would be a guess. The
# splitter is run once per page and never sees two pages at the same time, so
# the invariant holds by construction rather than by care — there is no code
# path here that could produce a chunk spanning a boundary. The cost is a few
# extra short chunks at page ends, cheap compared to a wrong citation.
# (DECISIONS.md #1, pinned by test_no_chunk_spans_two_pages.)
#
# WHY A CLASS AROUND SOMEONE ELSE'S SPLITTER:
# RecursiveCharacterTextSplitter belongs to LangChain, and this is the only
# place in the project allowed to name it. The rest of the app asks for Chunks
# and gets Chunks; it never learns which library produced them, what arguments
# it takes, or that split_text() returns bare strings with no provenance
# attached. Swapping the splitter — for a token-aware one, or a sentence-aware
# one — is then a change inside this class and nowhere else, and the page
# tagging that makes citations work cannot be lost in the swap, because it is
# written here and not at the call sites.

from langchain_text_splitters import RecursiveCharacterTextSplitter

from documind.config import AppConfig
from documind.documents.models import Chunk, Document

# Tried in order: break on a paragraph if possible, then a line, then a
# sentence, then a word — so chunk edges land on natural boundaries instead of
# mid-word.
SEPARATORS = ["\n\n", "\n", ".", " "]


class TextSplitter:
    """Splits a Document into page-tagged, citation-ready Chunks."""

    def __init__(self, config: AppConfig):
        self._config = config
        # chunk_size    → how many characters each chunk holds
        # chunk_overlap → how many characters consecutive chunks share
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=SEPARATORS,
        )

    def split(self, document: Document) -> list[Chunk]:
        """
        Every page of the document, cut into Chunks carrying its name and the
        page number the passage was found on.

        That provenance is what survives into the vector store and comes back at
        retrieval time, which is how an answer can say "p. 4 of report.pdf".
        Each page is split on its own, so no chunk can span two pages.
        """
        chunks: list[Chunk] = []

        for page in document.pages:
            for text in self.split_text(page.text):
                if not text.strip():
                    continue
                chunks.append(
                    Chunk(
                        text=text,
                        page_number=page.number,
                        source_document=document.name,
                    )
                )

        return chunks

    def split_text(self, text: str) -> list[str]:
        """
        One string cut into overlapping pieces, with no provenance attached.

        The raw form of the split, used by split() a page at a time and by the
        plain-text path that has no page numbers to carry.
        """
        return self._splitter.split_text(text)
