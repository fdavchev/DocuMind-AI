# documind/documents/__init__.py
#
# Everything to do with turning an uploaded file into citable passages: the
# value objects a document is made of, the loaders that read one, the factory
# that picks the right loader, and the splitter that cuts a document into chunks.

from documind.documents.document_loader import DocumentLoader
from documind.documents.loader_factory import LoaderFactory
from documind.documents.models import Chunk, Document, ExtractedPage
from documind.documents.pdf_loader import PdfLoader
from documind.documents.text_loader import TextLoader
from documind.documents.text_splitter import TextSplitter

__all__ = [
    "Chunk",
    "Document",
    "DocumentLoader",
    "ExtractedPage",
    "LoaderFactory",
    "PdfLoader",
    "TextLoader",
    "TextSplitter",
]
