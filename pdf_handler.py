# pdf_handler.py
#
# WHAT THIS FILE DOES:
# Splits a Document into small overlapping Chunks, each one carrying the file it
# came from and the page it was found on.
#
# The reading half of this file — page extraction, the OCR fallback, and
# bundling pages into a Document — now lives in documind/documents/pdf_loader.py
# as PdfLoader. What is left here are the chunking functions and thin wrappers
# that keep the old call sites working until the splitter moves out too; then
# this file goes away entirely.
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

from langchain_text_splitters import RecursiveCharacterTextSplitter

from documind.config import AppConfig
from documind.documents.models import Chunk, Document, ExtractedPage
from documind.documents.pdf_loader import PdfLoader
from errors import EmptyDocumentError


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
    return list(
        load_pdf_as_document(uploaded_file, use_ocr=use_ocr, config=config).pages
    )


def scanned_page_count(uploaded_file) -> int:
    """
    How many pages lack a usable text layer.

    Used to tell "this PDF is scanned and we need OCR" apart from "this PDF is
    genuinely empty", which are different problems with different remedies.
    """
    return PdfLoader(AppConfig()).scanned_page_count(uploaded_file)


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

    An unreadable PDF comes back as an empty Document rather than as an error,
    because app.py's upload handler answers that case itself: it asks
    no_text_error() whether the file was scanned or genuinely blank, which is a
    distinction the loader cannot make. PdfLoader.load() raises
    EmptyDocumentError instead, and the pipeline moves onto that behaviour when
    RagPipeline takes over the upload flow.
    """
    if name is None:
        name = getattr(uploaded_file, "name", "document.pdf")

    try:
        return PdfLoader(config, use_ocr=use_ocr).load(uploaded_file, name=name)
    except EmptyDocumentError:
        return Document(name=name, pages=())


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
