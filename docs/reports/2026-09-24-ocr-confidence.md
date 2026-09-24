# Session report — OCR confidence scoring (Phase 7)

**Date:** 2026-09-24
**Branch:** `feat/07-ocr-confidence` (off `main`, which has Phase 6's OOP refactor merged via PR #6)
**Scope:** the remaining part of `docs/project-report-2.md` §5 — confidence scoring, wiring it through an `OcrEngine`, surfacing low confidence in the UI, and greyscale/deskew preprocessing. Sections 3 commits, all pending your review and commit (nothing has been committed by an agent — you commit each one yourself).

## What was built, in commit order

### 1. `f267b7ea` — `Add OcrEngine and OcrResult, recognising text with confidence and preprocessing`
- New `documind/ocr/` package: `OcrResult(text, confidence)` and `OcrEngine(config)`.
- `OcrEngine.recognise(image)` — greyscale conversion, then a numpy-based deskew (rotation search, -5°..+5°, picks the angle that maximizes the row-projection variance; no new dependency), then `pytesseract.image_to_data` in `config.ocr_language`.
- `AppConfig` gained `ocr_language: str = "eng"` (Macedonian's `mkd` pack is not installed on this machine — confirmed via `tesseract --list-langs`, only `eng`/`osd` present) and `ocr_min_confidence: float = 60.0`.
- **VERIFIED by automated test:** pytest 239 passed (unchanged — nothing wired in yet).
- **VERIFIED by live run:** app boots, `/_stcore/health` → 200. Hand-check on a synthetic image: clean text → confidence 95.57; the same image tilted 3° → deskew correctly found -3°, confidence 95.43.

### 2. `3138688f` — `Wire OcrEngine into PdfLoader, filling in ExtractedPage.ocr_confidence`
- `PdfLoader` now renders a scanned page to an image itself and hands it to an injected/lazily-built `OcrEngine`, instead of calling the old `ocr.ocr_page()` module function.
- `ExtractedPage.ocr_confidence` is filled in for the first time.
- Created real sample files: `samples/text.pdf` (native text layer) and `samples/scanned.pdf` (image-only, synthetic — low-DPI, blurred, noised, JPEG-compressed text so the confidence number is realistic rather than a trivial ~99%).
- **VERIFIED by automated test:** pytest 244 passed (+5 new: confidence threading, native-text pages stay `None`, broken-render pages don't crash, render resolution, empty-OCR-result pages skipped).
- **VERIFIED by live run**, real Tesseract 5.4.0, run twice with identical output:
  - `samples/text.pdf` → `used_ocr=False`, `ocr_confidence=None` on its one page, text reads perfectly.
  - `samples/scanned.pdf` → `used_ocr=True`, **confidence 83.30952380952381**. Recognised text has 3 genuine misreadings (budyet/duc/chancter for budget/due/character) — a believable number for the evaluation chapter, not a rigged one.
  - Bug found here, fixed in step 3: `recognise()`'s confidence average included Tesseract layout-box entries with empty text, which could inflate confidence on a page with little real text (one test image scored `("", 95.0)`). Didn't affect `scanned.pdf`'s measured 83.3 — all 42 counted entries there were real words.

### 3. (pending commit) — `Surface low-confidence OCR pages as warnings, fixing empty-text bias in OcrEngine's confidence`
- Fixed the bug above: confidence average now only counts entries with non-empty recognised text.
- `IngestReport` (on `RagPipeline`) gained `ocr_confidences: tuple[tuple[int, float], ...]` — every OCR'd page's `(page_number, confidence)`, unfiltered. The pipeline reports facts; it doesn't hold an `AppConfig` and shouldn't need one just to decide what's "low".
- `app.py` reads `config.ocr_min_confidence` (already in scope as the existing module-level `config`) and shows `st.warning("Page N was recognised with X% confidence — the answer may be unreliable.")` for each page below threshold, right under the upload success message.
- **VERIFIED by automated test:** pytest **251 passed** (+7 new — confidence-average fix at the `OcrEngine` unit level, `IngestReport.ocr_confidences` for mixed OCR/native-text documents, two `AppTest`-driven UI tests that upload the real `samples/scanned.pdf` through the actual `app.py` script and assert the warning text appears/doesn't appear).
- **VERIFIED by live run:** app boots, `/_stcore/health` → 200. Re-measured `samples/scanned.pdf` after the fix: confidence unchanged at 83.30952380952381 (the fix only matters when empty-text boxes have `conf >= 0`, which wasn't the case on this page — all non-word entries had `conf == -1`). `samples/text.pdf` confirmed `ocr_confidences=()`, so it can never trigger a warning.
- **One-off test flake, not caused by this work:** a single early `pytest` run showed one failure in `tests/test_rag_pipeline.py::test_last_sources_holds_the_retrieved_chunks`, unreproducible across 88 subsequent runs (80 with varied `PYTHONHASHSEED`, 8 full-suite). Cause unknown, predates this session, not investigated further. Worth a backlog entry if you want it tracked.

## Section 5 checklist status (`docs/project-report-2.md`)

Covered by this session:
- [x] `OcrEngine.recognise()` returning text **and** confidence
- [x] Fallback wired into `PdfLoader`
- [x] Preprocess before OCR — greyscale, and deskew
- [x] Surface low confidence in the UI

**Not covered by this session** (confirmed, not silently dropped):
- [ ] Cyrillic (`mkd`) language data — **not installed** on this machine (`tesseract --list-langs` shows only `eng`/`osd`). `ocr_language` defaults to `"eng"`; switching to `mkd+eng` once the pack is installed is a one-line config change, no code change needed.
- [ ] `ImageLoader` for uploaded images — was already cut from this repo's Phase 6 scope (`docs/phase-06-progress.md`), never in scope for this session either.
- [ ] Handling Tesseract-not-installed gracefully — pre-existing behavior from earlier phases (`ocr.is_available()`, the sidebar's `ocr_status()`), untouched and unaffected by this session's changes.
- [ ] Measuring the preprocessing improvement (§7.2, evaluation) and the defence demo — explicitly your own work; no figures were produced or fabricated by any agent this session.

## What's still on disk, uncommitted-by-you

Three commits exist on `feat/07-ocr-confidence` locally (`f267b7ea`, `3138688f`, and the pending confidence-warning commit) — you make every commit yourself, per your standing rule. Commit messages are in each step's report above. Since this is the branch's first work after Phase 6, and Phase 6 already used its own body+PR-description pattern, the same applies here if you want a PR description when you open one — happy to draft it once you tell me you're ready.
