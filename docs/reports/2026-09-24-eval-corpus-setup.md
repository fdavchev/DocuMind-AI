# Evaluation Corpus Setup — Session Report

**Date:** 2026-09-24

## What this covered

Assembling and verifying the document corpus for the section 7.2 evaluation
chapter, plus fixing a real bug in Macedonian OCR discovered along the way.
No evaluation numbers (retrieval accuracy, answer correctness, CER) were
computed this session — that's still pending the Q&A ground truth, which is
explicitly Filip's to write, not mine.

## Corpus assembled, in `pdfs/`

| Category | Files | Status |
|---|---|---|
| Native-text (English) | 2 arXiv papers, 2 EU publications (`Native test PDFs/`) | **VERIFIED** — real text layers, 2000+ chars/page |
| Native-text (Macedonian) | Кошарка.pdf, Одбојка.pdf (`Macedonian documents/`) | **VERIFIED** — real text layers, 2000+ chars/page |
| Scanned (rejected) | Stewart Calculus textbook, "The Rainbow" 1981 fanzine | **REJECTED** — both had real extractable text (not image-only), so neither triggers OCR. The Calculus file was also 42.1MB, over the app's own 25MB upload limit, and is a currently-sold copyrighted textbook — inappropriate for a public repo regardless of the other two problems. |
| Scanned (English) | ohrid-scanned-en.pdf | **VERIFIED** — screenshot of the English Wikipedia "Ohrid" article, converted to PDF via PIL image embed (no OCR at conversion time), 0 extractable chars confirmed with pdfplumber, confidence 86.6% |
| Scanned (Macedonian) | ohrid-scanned-mk.pdf, fudbal-scanned-mk.pdf | **VERIFIED** — screenshots of Macedonian Wikipedia "Охрид" and "Фудбал", same conversion process, 0 extractable chars confirmed, confidence 89.4% / 92.2% after the OCR language fix below |

All scanned files were run through the real `PdfLoader` + `OcrEngine` classes
(not just a text-layer check) to confirm `used_ocr=True` and a real
confidence score, so the verification reflects the actual pipeline, not a
proxy for it.

## Bug found and fixed: Macedonian OCR was unusable

`AppConfig.ocr_language` defaulted to `"eng"` only. Running the two Macedonian
scans through the real pipeline with that default produced garbled text —
Tesseract reading Cyrillic glyphs as look-alike Latin characters ("Oxpug"
instead of "Охрид") — at 50–53% confidence, well under the app's 90%
threshold. This is a real defect against the thesis's own OCR/Macedonian
claim, not a documentation gap.

**Fix:**
1. Downloaded the official `mkd.traineddata` (tessdata_fast variant) since
   the system Tesseract install (`C:\Program Files\Tesseract-OCR\tessdata\`)
   only had `eng`/`osd` and writing to it needs admin rights.
2. Built a user-writable tessdata folder at `C:\Users\Davchev\.tessdata\`
   with `eng`, `osd`, and the new `mkd` file, and pointed Tesseract at it via
   `TESSDATA_PREFIX` (`setx TESSDATA_PREFIX "C:\Users\Davchev\.tessdata"` —
   persisted as a Windows user environment variable, no admin needed).
3. Changed `AppConfig.ocr_language` from `"eng"` to `"mkd+eng"` in
   `documind/config.py`.
4. Documented the setup in `docs/guides/macedonian-ocr-setup.md`, including
   the still-untested Docker equivalent (install `tesseract-ocr-mkd` in the
   Dockerfile instead of the `TESSDATA_PREFIX` workaround, since the
   container has root).

**Result:** confidence went from 50.1%→89.4% and 52.5%→92.2% on the two
Macedonian scans — both now correctly recognized, verified by reading the
actual OCR output text, not just the confidence number.

## A model comparison that came up along the way

Filip had an existing Tesseract fine-tuning pipeline at
`Documents/mkd-ocr-training/` (a `tesstrain` setup with its own Dockerfile
and ground-truth generator). Tested its output (`work/output/mkd.traineddata`)
against the same two scans as a real comparison, not a courtesy check:
82.5% and 85.7% — **lower** than the generic model on this input type.
Reported both numbers to Filip rather than picking one silently; he chose
the generic model for now. Noted in the guide that the custom model's
ground truth likely targets a different input domain (scanned/photographed
print, not rendered web-page screenshots) and could still be worth testing
against real scans later.

## Verification

- **VERIFIED by automated test:** `pytest -q` — 252 passed, 0 failed, both
  before and after the `ocr_language` config change.
- **VERIFIED by live run:** all three scanned PDFs run through the real
  `PdfLoader`/`OcrEngine` classes, confidence and recognized text read
  directly, not assumed. `streamlit run app.py` boots clean
  (`/_stcore/health` → 200) with the new default.
- **NOT VERIFIED:** the Docker/Tesseract-mkd setup described in the new
  guide — consistent with DECISIONS.md #12's existing note that the Docker
  image itself has never been built on this machine.

## Still open for section 7.2

- Corpus is at 7 real documents (4 native-English, 2 native-Macedonian,
  1 scanned-English, 2 scanned-Macedonian — 9 total, covering every category
  the plan asks for). Could stop here or add 1–2 more for variety.
- The 20–30 question/answer pairs with known correct pages — Filip drafts,
  reports verify each one against the real pipeline output.
- OCR character-error-rate needs a hand-typed ground truth for a few scanned
  pages — not started.
- Latency-per-stage and retrieval-accuracy measurement scripts — not started.

## Files touched this session

- `pdfs/Scanned PDFs/ohrid-scanned-mk.pdf`, `fudbal-scanned-mk.pdf`,
  `ohrid-scanned-en.pdf` — new, converted from Filip's screenshots
- `pdfs/Scanned PDFs/` — Stewart Calculus and Rainbow PDFs removed by Filip
  before this session (confirmed gone, not removed by me)
- `documind/config.py` — `ocr_language` default changed to `"mkd+eng"`
- `docs/guides/macedonian-ocr-setup.md` — new
- `docs/reports/2026-09-24-eval-corpus-setup.md` — this report

Nothing committed — waiting for Filip's review.
