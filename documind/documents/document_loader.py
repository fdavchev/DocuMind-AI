# documind/documents/document_loader.py
#
# WHAT THIS FILE DOES:
# Says what it means to read an uploaded file into a Document, without saying
# anything about what kind of file it is. Every loader answers the same three
# questions: which extensions do you handle, how do you turn one file into
# pages, and — inherited, written once here — what happens around that.
#
# WHY A TEMPLATE METHOD:
# Reading a PDF and reading a .txt file differ in exactly one step: how the
# bytes become pages. Everything either side of that step is identical — check
# the extension is one this loader handles, wrap the pages in a Document named
# after the upload, and refuse a file that turned out to contain no text at
# all. So that shared part lives in `load()` on the base class and the differing
# part is the one abstract method `_extract_pages`. A subclass supplies the step
# that is genuinely its own and inherits the rest; it cannot forget the empty
# check or name the document differently, because it never writes that code.
#
# WHY THE EXTRACTION HOOK IS PRIVATE:
# `_extract_pages` is the seam for subclasses, not an entry point for callers.
# Callers use `load()`, which is the only method that returns a validated
# Document — a caller reaching past it would get pages that had skipped every
# check.

from abc import ABC, abstractmethod
from pathlib import PurePath

from documind.config import AppConfig
from documind.documents.models import Document, ExtractedPage
from errors import EmptyDocumentError, UnsupportedFileError


class DocumentLoader(ABC):
    """Turns an uploaded file into a Document. One subclass per file type."""

    # The extensions this loader claims, lowercase and dotted (".pdf").
    SUPPORTED_EXTENSIONS: tuple[str, ...] = ()

    # Used when a file object arrives with no name of its own — a BytesIO from a
    # test, say. Each subclass names it with its own extension so the validation
    # step still has something honest to check.
    DEFAULT_NAME: str = "document"

    def __init__(self, config: AppConfig):
        self._config = config

    @classmethod
    def supports(cls, filename: str) -> bool:
        """
        Whether this loader handles that filename, judged by its extension.

        A classmethod because the answer depends on the loader's type, not on
        any particular instance — which is what lets a factory ask the question
        before deciding which loader to build (that factory is the next step).
        """
        return PurePath(filename).suffix.lower() in cls.SUPPORTED_EXTENSIONS

    def load(self, file, name: str | None = None) -> Document:
        """
        Reads `file` into a Document — the template method every loader shares.

        `name` defaults to the uploaded file's own name, which is what the UI
        shows next to the page number in a citation.

        Raises UnsupportedFileError if the name isn't one this loader handles,
        and EmptyDocumentError if the file yielded no text — an empty Document
        is not a result any caller can do anything with, and failing here means
        every caller gets the same message instead of inventing its own.
        """
        name = name or getattr(file, "name", None) or self.DEFAULT_NAME

        if not self.supports(name):
            raise UnsupportedFileError(name, self.SUPPORTED_EXTENSIONS)

        document = Document(name=name, pages=tuple(self._extract_pages(file)))

        if document.is_empty:
            raise EmptyDocumentError(name)

        return document

    @abstractmethod
    def _extract_pages(self, file) -> list[ExtractedPage]:
        """
        Reads the file's pages. The one step each file type does differently.

        Returns the pages that yielded usable text, in order, 1-based. Pages
        with nothing on them are left out rather than returned empty.
        """
