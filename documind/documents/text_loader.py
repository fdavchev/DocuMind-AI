# documind/documents/text_loader.py
#
# WHAT THIS FILE DOES:
# Reads a plain text or Markdown upload into the same Document every other
# loader produces. There is nothing to extract — the file is already text — so
# the only real work is deciding which encoding it was written in.
#
# WHY IT EXISTS:
# A single subclass cannot demonstrate polymorphism; it only asserts it. With a
# second loader the claim becomes checkable: the same `load()` written once on
# DocumentLoader serves a 200-page scanned PDF and a .txt file, and the caller
# that holds one of them cannot tell from its side which it is holding.
#
# WHY A SECOND ENCODING:
# UTF-8 is what anything written this decade uses, and it is tried first. Older
# Macedonian documents were written in Windows-1251, whose bytes are a valid
# file but not valid UTF-8 — decoding one as UTF-8 raises rather than producing
# nonsense, which is what makes the fallback safe to attempt in that order.
#
# WHY ONE PAGE:
# A text file has no pages. Rather than invent boundaries the file does not
# have, everything in it is page 1 — so a citation from a .txt says page 1 and
# is honest, instead of pointing at a page number nobody could go and check.

from documind.documents.document_loader import DocumentLoader
from documind.documents.models import ExtractedPage

# Tried in order; the first that decodes wins.
ENCODINGS = ("utf-8", "cp1251")


class TextLoader(DocumentLoader):
    """Reads .txt and .md uploads."""

    SUPPORTED_EXTENSIONS = (".txt", ".md")
    DEFAULT_NAME = "document.txt"

    def _extract_pages(self, file) -> list[ExtractedPage]:
        """The whole file as a single page, or no pages if it is blank."""
        text = self._read_text(file)

        if not text.strip():
            return []

        return [ExtractedPage(number=1, text=text, used_ocr=False)]

    @staticmethod
    def _read_text(file) -> str:
        """Decodes the upload, trying each supported encoding in turn."""
        if hasattr(file, "seek"):
            # The same upload may have been read once already — by a size check,
            # or by a loader that was asked first and did not match.
            file.seek(0)

        data = file.read() if hasattr(file, "read") else file

        if isinstance(data, str):
            return data

        for encoding in ENCODINGS:
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue

        # cp1251 maps every byte, so this is unreachable with the current list —
        # it is here so adding a stricter encoding later cannot silently return
        # nothing at all.
        return data.decode(ENCODINGS[-1], errors="replace")
