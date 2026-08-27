# pdf_handler.py
#
# WHAT THIS FILE DOES:
# 1. Takes a PDF file uploaded by the user
# 2. Extracts the text of every page, KEEPING the page number
# 3. Splits that text into small overlapping "chunks", each one tagged
#    with the file it came from and the page it was found on
#
# WHY CHUNKS?
# A PDF might be 100 pages. We can't send all of it to the LLM at once
# (too many tokens). Instead we cut it into ~500-character pieces, store
# them in FAISS, and only send the 3-5 most relevant pieces per question.
#
# WHY OVERLAP?
# If a sentence is split across two chunks, the overlap (50 chars) ensures
# neither chunk loses context at its edges.
#
# WHY SPLIT PAGE-BY-PAGE INSTEAD OF ONE BIG STRING?
# Because a chunk that straddles a page boundary can't be cited honestly.
# Splitting each page on its own means every chunk belongs to exactly one
# page, so "p. 4" in an answer is always accurate. The cost is a few extra
# short chunks at page ends — cheap compared to a wrong citation.

import pdfplumber
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import ocr
from errors import ScannedPdfTooLong

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def extract_pages_from_pdf(
    uploaded_file, use_ocr: bool = True
) -> list[tuple[int, str]]:
    """
    Reads the PDF and returns [(page_number, page_text), ...].

    Page numbers are 1-based, matching what a human sees in a PDF reader.
    Pages with no usable text layer fall back to OCR when Tesseract is
    available; pages that yield nothing either way are skipped.
    `uploaded_file` is the object Streamlit gives us from st.file_uploader.

    Set use_ocr=False to force the text-layer-only path.
    """
    pages: list[tuple[int, str]] = []

    with pdfplumber.open(uploaded_file) as pdf:
        ocr_pages = [
            page for page in pdf.pages if ocr.page_needs_ocr(page.extract_text())
        ]
        ocr_wanted = use_ocr and ocr_pages and ocr.is_available()

        # Refuse up front rather than starting an OCR pass we know will take
        # minutes — the same principle as the upload size gate.
        if ocr_wanted and len(ocr_pages) > ocr.MAX_OCR_PAGES:
            raise ScannedPdfTooLong(
                getattr(uploaded_file, "name", "The file"), len(ocr_pages)
            )

        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text()

            if ocr.page_needs_ocr(page_text) and ocr_wanted:
                page_text = ocr.ocr_page(page)

            if page_text and page_text.strip():  # image-only pages return None
                pages.append((page_number, page_text))

    return pages


def scanned_page_count(uploaded_file) -> int:
    """
    How many pages lack a usable text layer.

    Used to tell "this PDF is scanned and we need OCR" apart from "this PDF is
    genuinely empty", which are different problems with different remedies.
    """
    with pdfplumber.open(uploaded_file) as pdf:
        return sum(1 for page in pdf.pages if ocr.page_needs_ocr(page.extract_text()))


def extract_text_from_pdf(uploaded_file) -> str:
    """
    Reads every page of the PDF and returns one big string of text.

    Kept for the plain text path (and for callers that don't need citations);
    the citation pipeline uses extract_pages_from_pdf instead.
    """
    pages = extract_pages_from_pdf(uploaded_file)
    return "\n".join(text for _, text in pages)


def _make_splitter() -> RecursiveCharacterTextSplitter:
    """
    chunk_size=500   → each chunk is ~500 characters
    chunk_overlap=50 → consecutive chunks share 50 characters at the border
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " "],  # try to split on natural boundaries
    )


def split_text_into_chunks(text: str) -> list[str]:
    """Splits a plain string into overlapping chunks (no metadata)."""
    return _make_splitter().split_text(text)


def split_pages_into_chunks(
    pages: list[tuple[int, str]], source: str
) -> list[Document]:
    """
    Splits each page separately and returns LangChain Documents carrying
    metadata = {"source": <filename>, "page": <1-based page number>}.

    That metadata is what survives into FAISS and comes back at retrieval
    time, which is how an answer can say "p. 4 of report.pdf".
    """
    splitter = _make_splitter()
    documents: list[Document] = []

    for page_number, page_text in pages:
        for chunk in splitter.split_text(page_text):
            if not chunk.strip():
                continue
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={"source": source, "page": page_number},
                )
            )

    return documents


def load_pdf_as_documents(
    uploaded_file, source: str | None = None, use_ocr: bool = True
) -> list[Document]:
    """
    One-call convenience: uploaded PDF → citation-ready Documents.

    `source` defaults to the uploaded file's name, which is what the UI
    shows next to the page number. Returns [] when nothing could be read —
    callers use no_text_error() to turn that into the right message.
    """
    if source is None:
        source = getattr(uploaded_file, "name", "document.pdf")

    pages = extract_pages_from_pdf(uploaded_file, use_ocr=use_ocr)
    return split_pages_into_chunks(pages, source)
