# documind/documents/models.py
#
# WHAT THIS FILE DOES:
# Defines the three small objects the document pipeline passes around:
#   ExtractedPage — one page of a PDF after extraction
#   Document      — a whole uploaded file: its name plus every page read from it
#   Chunk         — one retrievable passage, tagged with the page it came from
#
# WHY OBJECTS INSTEAD OF TUPLES AND DICTIONARIES:
# Extraction used to hand back (page_number, page_text) tuples and chunking used
# to hand back LangChain Documents carrying metadata={"source": ..., "page": ...}.
# Both shapes are invisible to the reader and to the editor: nothing tells you
# that element [0] is the page number, and a typo in "page" fails silently at
# retrieval time rather than loudly where it was written. A named field cannot be
# misread, cannot be misspelled without an error, and can be extended — which is
# why ExtractedPage already has room for an OCR confidence score that no code
# produces yet.
#
# WHY FROZEN:
# These objects describe what was read from a file. Nothing downstream has any
# business editing them, so nothing downstream is allowed to: a Chunk handed to
# the vector store is the same Chunk that was created by the splitter.

from dataclasses import dataclass

# Pages are joined with a blank line so the boundary between two pages survives
# in the plain-text view the way it does in the PDF.
PAGE_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class ExtractedPage:
    """
    One page of a PDF after extraction, and how its text was obtained.

    `number` is 1-based, matching what a human sees in a PDF reader.
    `used_ocr` records whether the text came from the page's own text layer or
    from Tesseract, which is the difference between text we can trust and text
    a machine guessed at.
    """

    number: int
    text: str
    used_ocr: bool

    # No confidence scoring exists yet; the field is here so a later phase can
    # fill it in without changing the shape every other module already reads.
    ocr_confidence: float | None = None


@dataclass(frozen=True)
class Document:
    """
    A whole uploaded document: the filename it arrived under and its pages.

    `pages` is a tuple rather than a list so the frozen document cannot be
    mutated through it.
    """

    name: str
    pages: tuple[ExtractedPage, ...]

    @property
    def text(self) -> str:
        """Every page's text, joined — the plain-text view of the document."""
        return PAGE_SEPARATOR.join(page.text for page in self.pages)

    @property
    def page_count(self) -> int:
        """How many pages yielded usable text."""
        return len(self.pages)

    @property
    def ocr_page_count(self) -> int:
        """How many of those pages had to be read by OCR."""
        return sum(1 for page in self.pages if page.used_ocr)

    @property
    def is_empty(self) -> bool:
        """True when nothing readable came out of the file at all."""
        return not self.text.strip()


@dataclass(frozen=True)
class Chunk:
    """
    One passage of a document, small enough to embed and to put in a prompt.

    `page_number` and `source_document` are what make a citation possible: they
    travel with the passage into the vector store and come back with it at
    retrieval time, so an answer can say "p. 7 of report.pdf" and be right.
    """

    text: str
    page_number: int
    source_document: str
