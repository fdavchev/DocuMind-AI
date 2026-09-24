# Phase 7 — manual test checklist (OCR confidence)

Run this before merging `feat/07-ocr-confidence`. The automated suite (251
pytest tests, including two that drive the real Streamlit script) already
passed. This checklist is you actually looking at the app, which is the one
thing the automated tests can't stand in for — especially the low-confidence
warning, since the real sample file scores *above* the warning threshold and
won't show it by default (step 4 explains how to see it anyway).

## 1. Start Ollama and the app

Same as always:

```powershell
ollama serve
```

In a second terminal, in the project folder:

```powershell
.\run.ps1
```

Wait for the sidebar to say **✅ System ready**.

## 2. Upload a normal PDF — confirm nothing changed

Switch to **📄 PDF Q&A** mode and upload `samples/text.pdf` (it's already in
the repo, in the `samples` folder).

- Confirm you get the usual success message, with **no** "page(s) needed
  OCR" note and **no** confidence warning underneath it. This file has a
  real text layer, so OCR should never run on it — that's the thing this
  step is checking.

## 3. Upload the scanned sample — confirm OCR runs and is reported

Upload `samples/scanned.pdf` (also already in `samples`).

- Confirm the success message **does** say "1 page(s) needed OCR."
- You should **not** see a low-confidence warning here — this file measures
  about 83% confidence, which is above the 60% warning threshold. Seeing no
  warning on a decent scan is the correct behaviour, not a bug.
- Ask a question about it (e.g. "What was approved in March?" or "When is
  the report due?"). Confirm you get a sensible answer even though this
  file has typos in it from the OCR reading ("budyet", "duc", "chancter") —
  the point is the answer still works despite imperfect OCR.

## 4. See the actual low-confidence warning

Since `samples/scanned.pdf` scores above the warning threshold, you won't
see the warning message in step 3. To actually see it fire, pick **one** of
these:

**Option A — lower the threshold temporarily (fastest, no new file needed)**

1. Open `documind/config.py`, find `ocr_min_confidence: float = 60.0`, and
   change it to something above 83, e.g. `90.0`.
2. Restart the app (`.\run.ps1`), clear any previously indexed documents,
   and re-upload `samples/scanned.pdf`.
3. Confirm you now see a warning like *"Page 1 was recognised with 83%
   confidence — the answer may be unreliable."* right under the success
   message.
4. **Change the `60.0` back afterwards** — this was just to see the warning
   fire, not a real setting change. Don't commit the `90.0` value.

**Option B — use a worse scan**

If you have a genuinely low-quality scan or photo of a printed page handy
(blurry, low-light, at an angle), upload that instead of the sample. If its
real confidence lands under 60%, the warning appears without touching any
config. This is closer to what a real low-quality scan in your evaluation
set will look like.

## 5. Confirm Tesseract-missing still degrades gracefully

This isn't new in this phase, but it's worth re-checking since `PdfLoader`
now goes through a different code path (`OcrEngine` instead of the old
`ocr.py` function) to get to the same Tesseract binary.

1. Temporarily rename the Tesseract install folder (commonly
   `C:\Program Files\Tesseract-OCR`) to something else, or remove it from
   your `PATH` for this test.
2. Restart the app and check the sidebar's system panel — it should explain
   OCR isn't available (with install instructions), not crash.
3. Upload `samples/scanned.pdf` again — confirm you get a clear, readable
   error message (not a traceback) rather than a silent empty result.
4. Rename the folder back / restore `PATH`, and confirm a restart brings
   OCR back.

## If all of this behaves

You're good to merge `feat/07-ocr-confidence`. Nothing above is expected to
fail — automated coverage already exercises the same logic — this is about
seeing the real UI wording and the real Tesseract binary agree with what the
tests assume.

## If something breaks

Note which step, what you saw (exact wording, or "Show traceback" if
Streamlit offers it), and bring that back before merging.
