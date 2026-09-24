# Setting up Macedonian OCR (the `mkd` Tesseract language pack)

`AppConfig.ocr_language` defaults to `"mkd+eng"`, but Tesseract only ships
with `eng` and `osd` out of the box. Without the extra step below, Macedonian
scans will still run through OCR, but Tesseract will try to read Cyrillic
text using the English model and produce garbled output (confidence in the
50s instead of the 80s–90s).

## Windows (what this machine uses)

Tesseract's own `tessdata` folder lives under `C:\Program Files\Tesseract-OCR\`,
which needs admin rights to write to. The simpler path is to point Tesseract
at a second, user-writable folder instead, via the `TESSDATA_PREFIX`
environment variable — Tesseract reads whichever folder that variable points
to, in addition to checking its own install folder.

1. Create a folder for your own language data, e.g. `C:\Users\<you>\.tessdata\`.
2. Copy `eng.traineddata` and `osd.traineddata` into it from
   `C:\Program Files\Tesseract-OCR\tessdata\` (these are just being copied,
   not moved — the original install is untouched).
3. Download `mkd.traineddata` from the official Tesseract language-data repo
   and place it in the same folder:
   https://github.com/tesseract-ocr/tessdata_fast/raw/main/mkd.traineddata
   (the "fast" variant — smaller and quicker than "best", and accurate
   enough in testing: ~89–92% confidence on real Macedonian scans).
4. Set `TESSDATA_PREFIX` permanently, from any terminal (no admin needed):
   ```
   setx TESSDATA_PREFIX "C:\Users\<you>\.tessdata"
   ```
5. Restart any terminal, IDE, or running `streamlit` process so it picks up
   the new environment variable, then confirm with:
   ```
   tesseract --list-langs
   ```
   should list `eng`, `mkd`, and `osd`.

## Docker

The `model-init` / `app` service setup (DECISIONS.md #12) should install the
`tesseract-ocr-mkd` package (Debian/Ubuntu base images) alongside the base
`tesseract-ocr` package in the Dockerfile, which places `mkd.traineddata`
directly into the image's own `tessdata` folder — no `TESSDATA_PREFIX`
workaround needed there, since the container is built with root access.
**Not yet verified** — the Docker image itself is still unbuilt per
DECISIONS.md #12, so this is the intended approach, not a tested one.

## Why not the custom-trained model in `mkd-ocr-training/`

That folder holds a `tesstrain`-based fine-tuning pipeline for a custom
Macedonian model. Measured against two real Macedonian scans (Wikipedia
screenshots), it scored *lower* (82.5%, 85.7%) than the generic
`tessdata_fast` model (89.4%, 92.2%) — likely a domain mismatch between
whatever ground truth it was trained on and rendered web-page text. The
generic model is what's configured for now. If the custom model is later
tested against genuinely scanned/photographed documents (its more likely
target domain) and it wins there, that would be the case to switch — but
that hasn't been measured yet.
