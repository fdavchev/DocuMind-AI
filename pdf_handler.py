# pdf_handler.py
#
# WHAT THIS FILE DOES:
# 1. Takes a PDF file uploaded by the user
# 2. Extracts the text of every page as an ExtractedPage, KEEPING the page
#    number and recording whether the page had to be read by OCR
# 3. Bundles those pages into a Document — the file's name plus its pages
# 4. Splits that document into small overlapping Chunks, each one carrying the
#    file it came from and the page it was found on
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
from langchain_text_splitters import RecursiveCharacterTextSplitter

import ocr
from documind.config import AppConfig
from documind.documents.models import Chunk, Document, ExtractedPage
from errors import ScannedPdfTooLong


def extract_pages_from_pdf(
    uploaded_file, use_ocr: bool = True, config: AppConfig = AppConfig()
) -> list[ExtractedPage]:
    """
    Reads the PDF and returns one ExtractedPage per readable page.

    Page numbers are 1-based, matching what a human sees in a PDF reader.
    Pages with no usable text layer fall back to OCR when Tesseract is
    available — those pages come back with used_ocr=True — and pages that yield
    nothing either way are skipped.
    `uploaded_file` is the object Streamlit gives us from st.file_uploader.

    Set use_ocr=False to force the text-layer-only path.
    """
    pages: list[ExtractedPage] = []

    with pdfplumber.open(uploaded_file) as pdf:
        ocr_pages = [
            page for page in pdf.pages if ocr.page_needs_ocr(page.extract_text())
        ]
        ocr_wanted = use_ocr and ocr_pages and ocr.is_available()

        # Refuse up front rather than starting an OCR pass we know will take
        # minutes — the same principle as the upload size gate.
        if ocr_wanted and len(ocr_pages) > config.max_ocr_pages:
            raise ScannedPdfTooLong(
                getattr(uploaded_file, "name", "The file"),
                len(ocr_pages),
                config.max_ocr_pages,
            )

        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text()
            used_ocr = False

            if ocr.page_needs_ocr(page_text) and ocr_wanted:
                page_text = ocr.ocr_page(page)
                used_ocr = True

            if page_text and page_text.strip():  # image-only pages return None
                pages.append(
                    ExtractedPage(
                        number=page_number, text=page_text, used_ocr=used_ocr
                    )
                )

    return pages


def scanned_page_count(uploaded_file) -> int:
    """
    How many pages lack a usable text layer.

    Used to tell "this PDF is scanned and we need OCR" apart from "this PDF is
    genuinely empty", which are different problems with different remedies.
    """
    with pdfplumber.open(uploaded_file) as pdf:
        return sum(1 for page in pdf.pages if ocr.page_needs_ocr(page.extract_text()))


def load_pdf_as_document(
    uploaded_file,
    name: str | None = None,
    use_ocr: bool = True,
    config: AppConfig = AppConfig(),
) -> Document:
    """
    Reads an uploaded PDF into a Document — its filename plus every page.

    `name` defaults to the uploaded file's own name, which is what the UI shows
    next to the page number in a citation.
    """
    if name is None:
        name = getattr(uploaded_file, "name", "document.pdf")

    pages = extract_pages_from_pdf(uploaded_file, use_ocr=use_ocr, config=config)
    return Document(name=name, pages=tuple(pages))


def extract_text_from_pdf(uploaded_file, config: AppConfig = AppConfig()) -> str:
    """
    Reads every page of the PDF and returns one big string of text.

    Kept for the plain text path (and for callers that don't need citations);
    the citation pipeline uses load_pdf_as_chunks instead.
    """
    return load_pdf_as_document(uploaded_file, config=config).text


def _make_splitter(config: AppConfig) -> RecursiveCharacterTextSplitter:
    """
    chunk_size   → how many characters each chunk holds
    chunk_overlap → how many characters consecutive chunks share at the border
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=["\n\n", "\n", ".", " "],  # try to split on natural boundaries
    )


def split_text_into_chunks(text: str, config: AppConfig = AppConfig()) -> list[str]:
    """Splits a plain string into overlapping chunks (no provenance)."""
    return _make_splitter(config).split_text(text)


def split_document_into_chunks(
    document: Document, config: AppConfig = AppConfig()
) -> list[Chunk]:
    """
    Splits each page of a Document separately and returns Chunks carrying the
    document's name and the page number the passage was found on.

    That provenance is what survives into FAISS and comes back at retrieval
    time, which is how an answer can say "p. 4 of report.pdf".
    """
    splitter = _make_splitter(config)
    chunks: list[Chunk] = []

    for page in document.pages:
        for text in splitter.split_text(page.text):
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


def load_pdf_as_chunks(
    uploaded_file,
    name: str | None = None,
    use_ocr: bool = True,
    config: AppConfig = AppConfig(),
) -> list[Chunk]:
    """
    One-call convenience: uploaded PDF → citation-ready Chunks.

    Returns [] when nothing could be read — callers use no_text_error() to turn
    that into the right message.
    """
    document = load_pdf_as_document(
        uploaded_file, name=name, use_ocr=use_ocr, config=config
    )
    return split_document_into_chunks(document, config=config)
