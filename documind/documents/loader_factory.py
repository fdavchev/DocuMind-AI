# documind/documents/loader_factory.py
#
# WHAT THIS FILE DOES:
# Picks the right loader for an uploaded filename and builds it. It is the one
# place in the project that knows the full list of file types the app can read;
# everywhere else just holds a DocumentLoader and calls load() on it.
#
# WHY A FACTORY AND NOT AN IF-CHAIN:
# Without it the type decision leaks into the upload handler — `if name ends in
# .pdf: PdfLoader(...) elif .txt or .md: TextLoader(...) else: error` — and that
# chain has to be repeated by every caller that ever loads a file, each copy
# free to forget a format or to word the refusal differently. Here it is written
# once, and the caller never learns which kind of file it uploaded.
#
# WHY IT ASKS THE LOADERS INSTEAD OF DECIDING ITSELF:
# The factory does not contain a single extension string. Each loader already
# declares what it handles and answers `supports()` for itself, so dispatch is
# just walking the registry and asking. That is what keeps this class closed to
# modification: a new format is a new DocumentLoader subclass added to LOADERS,
# one line, and the method below does not change — it cannot, because there is
# nothing in it that is specific to any format.

from documind.config import AppConfig
from documind.documents.document_loader import DocumentLoader
from documind.documents.pdf_loader import PdfLoader
from documind.documents.text_loader import TextLoader
from errors import UnsupportedFileError


class LoaderFactory:
    """Builds the DocumentLoader that handles a given filename."""

    # The registry: every loader the app can dispatch to. This tuple is the
    # single place a new file type gets registered.
    LOADERS: tuple[type[DocumentLoader], ...] = (PdfLoader, TextLoader)

    def __init__(self, config: AppConfig):
        self._config = config

    @classmethod
    def supported_extensions(cls) -> tuple[str, ...]:
        """
        Every extension any registered loader handles, in registry order.

        Read off the loaders rather than listed here, so it cannot drift out of
        date when a loader changes what it claims.
        """
        extensions: list[str] = []
        for loader in cls.LOADERS:
            extensions.extend(
                extension
                for extension in loader.SUPPORTED_EXTENSIONS
                if extension not in extensions
            )
        return tuple(extensions)

    def create_loader(self, filename: str) -> DocumentLoader:
        """
        The loader for that filename, built with this factory's config.

        A fresh instance each call: loaders are cheap, and handing every caller
        its own means one caller's loader can never be left holding another
        caller's half-read upload.

        Raises UnsupportedFileError if no registered loader claims the file —
        naming the formats that would have worked, so the message tells the user
        what to do instead of only what failed.
        """
        for loader in self.LOADERS:
            if loader.supports(filename):
                return loader(self._config)

        raise UnsupportedFileError(filename, supported=self.supported_extensions())
