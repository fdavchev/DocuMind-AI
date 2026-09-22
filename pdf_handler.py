# pdf_handler.py
#
# WHAT THIS FILE DOES:
# Nothing of its own any more. Every function here is a thin wrapper that keeps
# an old call site working while the classes it now delegates to take over.
#
# The reading half — page extraction, the OCR fallback, and bundling pages into
# a Document — lives in documind/documents/pdf_loader.py as PdfLoader. The
# chunking half — cutting a Document into page-tagged Chunks — lives in
# documind/documents/text_splitter.py as TextSplitter, including the
# page-by-page splitting that keeps a citation honest. This file goes away
# entirely once app.py and the remaining callers talk to RagPipeline instead.

from documind.config import AppConfig
from documind.documents.models import Chunk, Document, ExtractedPage
from documind.documents.pdf_loader import PdfLoader
from documind.documents.text_splitter import TextSplitter
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


def split_text_into_chunks(text: str, config: AppConfig = AppConfig()) -> list[str]:
    """Splits a plain string into overlapping chunks (no provenance)."""
    return TextSplitter(config).split_text(text)


def split_document_into_chunks(
    document: Document, config: AppConfig = AppConfig()
) -> list[Chunk]:
    """
    Splits each page of a Document separately and returns Chunks carrying the
    document's name and the page number the passage was found on.

    That provenance is what survives into FAISS and comes back at retrieval
    time, which is how an answer can say "p. 4 of report.pdf".
    """
    return TextSplitter(config).split(document)


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
