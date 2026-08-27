"""
Shared test fixtures.

Two things every test here needs and neither of which should require a
running Ollama or a checked-in binary sample:

1. `make_pdf` — builds a real, minimal PDF in memory from page strings, so
   tests can assert on page numbers they chose themselves.
2. `FakeEmbeddings` — a deterministic, dependency-free stand-in for
   OllamaEmbeddings, so the FAISS tests exercise real indexing and real
   similarity search without a live model.
"""

import io
import math
import sys
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

# Make the project modules importable when pytest is run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ocr  # noqa: E402 — must follow the sys.path fix above


# ── A minimal PDF writer ───────────────────────────────────────────────────────

def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build_pdf_bytes(pages: list[str]) -> bytes:
    """
    Returns the bytes of a valid PDF, one page per entry in `pages`.
    Newlines inside a page become separate text lines on that page.
    """
    objects: list[bytes] = []          # objects[i] is object number i + 1
    page_object_numbers: list[int] = []

    # 1 = catalog, 2 = page tree, 3 = font; pages start at 4
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"")                # page tree, filled in once kids are known
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for page_text in pages:
        lines = "".join(
            f"({_escape(line)}) Tj T*\n" for line in page_text.split("\n")
        )
        stream = f"BT\n/F1 12 Tf\n72 720 Td\n14 TL\n{lines}ET".encode("latin-1")

        content_number = len(objects) + 2  # this page's object is first
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
            + str(content_number).encode() + b" 0 R >>"
        )
        page_object_numbers.append(len(objects))
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
            + stream + b"\nendstream"
        )

    kids = b" ".join(f"{n} 0 R".encode() for n in page_object_numbers)
    objects[1] = (
        b"<< /Type /Pages /Kids [" + kids + b"] /Count "
        + str(len(page_object_numbers)).encode() + b" >>"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(number).encode() + b" 0 obj\n" + body + b"\nendobj\n"

    xref_offset = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size " + str(len(objects) + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode() + b"\n%%EOF\n"
    )
    return bytes(out)


class UploadedPdf(io.BytesIO):
    """Mimics the Streamlit UploadedFile duck type: bytes plus a .name."""

    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


@pytest.fixture
def make_pdf():
    """make_pdf(["page one text", "page two text"], name="report.pdf")"""

    def _make(pages: list[str], name: str = "test.pdf") -> UploadedPdf:
        return UploadedPdf(build_pdf_bytes(pages), name)

    return _make


# ── A fake embedding model ─────────────────────────────────────────────────────

class FakeEmbeddings(Embeddings):
    """
    Deterministic bag-of-words embedding: each text becomes a normalised
    vector over a fixed hashed vocabulary. Texts sharing words end up close
    together, which is all the retrieval tests need — and it runs offline.
    """

    dimensions = 64

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for word in text.lower().split():
            cleaned = "".join(ch for ch in word if ch.isalnum())
            if cleaned:
                vector[hash(cleaned) % self.dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@pytest.fixture
def fake_embeddings():
    return FakeEmbeddings()


# ── Machine-independent OCR ────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def ocr_disabled_by_default(monkeypatch):
    """
    Force OCR off for every test unless the test turns it back on.

    Without this the suite would behave differently on a machine that happens to
    have Tesseract installed: pages with a thin text layer would be OCR'd instead
    of skipped. Tests that exercise OCR re-patch `is_available` themselves, and
    because they do so after this fixture, theirs wins.
    """
    monkeypatch.setattr(ocr, "is_available", lambda: False)
