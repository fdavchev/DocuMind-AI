# ocr.py
#
# WHAT THIS FILE DOES:
# Recovers text from PDF pages that have no text layer — scanned documents,
# where each page is an image of a page rather than characters.
#
# HOW:
# The page is rendered to a bitmap and passed to Tesseract, which returns its
# best reading of the characters in the image.
#
# WHY IT IS OPTIONAL:
# Tesseract is a native binary, not a Python package. Requiring it would turn a
# `pip install` into a platform-specific system install and break the project's
# one-command setup promise. So OCR is a *fallback*: if Tesseract is present the
# pipeline uses it, and if it isn't, text-based PDFs (the common case) keep
# working and the user gets a message explaining what to install.
#
# WHY A MINIMUM CHARACTER COUNT RATHER THAN "NO TEXT AT ALL":
# Scanned pages are rarely completely empty. They often carry a few stray
# characters from a header, a stamped page number, or an OCR pass someone else
# ran badly. A page with nine characters on it has no usable text layer even
# though `extract_text()` returned something.

import functools

# Rendering resolution for OCR. 300 DPI is the accuracy/speed knee for
# Tesseract: below roughly 200 accuracy falls off sharply, above 400 the cost
# grows without a matching gain.
OCR_RESOLUTION = 300

# A page whose text layer is shorter than this is treated as not having one.
MIN_CHARS_FOR_TEXT_LAYER = 20

# OCR costs roughly a second or two per page. Past this many pages the wait
# stops being reasonable for an interactive upload, so we refuse rather than
# leave the user watching a spinner for ten minutes.
MAX_OCR_PAGES = 50


@functools.lru_cache(maxsize=1)
def is_available() -> bool:
    """
    True when both the pytesseract wrapper and the Tesseract binary are usable.

    Cached: the answer cannot change while the process runs, and the check
    spawns a subprocess.
    """
    return tesseract_version() is not None


@functools.lru_cache(maxsize=1)
def tesseract_version() -> str | None:
    """The installed Tesseract version, or None if it isn't available."""
    try:
        import pytesseract
    except ImportError:
        return None

    try:
        return str(pytesseract.get_tesseract_version())
    except Exception:
        # pytesseract raises TesseractNotFoundError when the binary is missing,
        # but a broken install can fail in other ways. Either way: unavailable.
        return None


def page_needs_ocr(page_text: str | None) -> bool:
    """Whether a page's extracted text is too thin to be a real text layer."""
    return len(page_text.strip()) < MIN_CHARS_FOR_TEXT_LAYER if page_text else True


def ocr_page(page) -> str:
    """
    Renders one pdfplumber page to a bitmap and returns Tesseract's reading.

    Returns "" if OCR is unavailable or the page yields nothing, so callers can
    treat a failed OCR the same as a page with no text.
    """
    if not is_available():
        return ""

    import pytesseract

    try:
        image = page.to_image(resolution=OCR_RESOLUTION).original
        return pytesseract.image_to_string(image).strip()
    except Exception:
        # A page that fails to render or OCR is a page with no text, not a
        # reason to abandon the rest of the document.
        return ""


def unavailable_hint() -> str:
    """Platform-agnostic install instructions, shown when OCR is needed but absent."""
    return (
        "Install Tesseract to enable OCR — `winget install UB-Mannheim.TesseractOCR` "
        "on Windows, `brew install tesseract` on macOS, or "
        "`apt install tesseract-ocr` on Linux. The Docker image already includes it."
    )
