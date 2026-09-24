# Finding documents for the Phase 4 evaluation (section 7.2)

Plain steps to get the ~7 documents we need: 3–4 native-text PDFs, 2–3 scanned
PDFs, and 1–2 Macedonian documents. No downloading needed yet — just gather
the links first, we'll pull the files together after.

## 1. Native-text PDFs (3–4 of them)

These need a real text layer (not a scan) and enough content to ask 3–5
questions about each.

- **arXiv** (https://arxiv.org) — any paper. Open one, click "PDF" or "Download PDF".
  These always have a real text layer. Pick something readable, not too
  math-heavy, so the questions are easy to write.
- **EU publications** (https://op.europa.eu/en/web/general-publications) —
  official reports and guides, free to download, public documents.
- **Wikipedia → PDF export** — open any English Wikipedia article, in the left
  sidebar under "Tools" (or "Print/export" on older layouts) click
  "Download as PDF". Works for any article with a few paragraphs of content.

## 2. Scanned PDFs (2–3 of them)

These must have **no text layer** — the OCR fallback only triggers when
`extract_text()` comes back empty. **Update after checking two candidates:**
archive.org is unreliable for this — it auto-runs OCR on nearly everything it
hosts, so the "PDF" download usually has a text layer baked in even when the
original item was a scan, and you can't tell from the listing. Both PDFs
tried this way turned out to have full extractable text. So: print-and-photograph
is now the recommended path, not the fallback.

- **Recommended — make your own (reliable):**
  1. Print any page (a Wikipedia article, a form, anything with real text).
  2. Take a plain photo of it with your phone camera app — the regular camera,
     **not** a "scan" or "document scanner" app/mode. Many of those run their
     own OCR and would defeat the point the same way archive.org did.
  3. Convert the photo to a PDF without any text-recognition step: on iPhone,
     open the photo → Share → Print → pinch-zoom out on the print preview →
     Share → Save to Files as PDF. On Android, open the photo → Print →
     "Save as PDF". On a computer, just insert the photo into a blank Word/
     Google Doc page and export as PDF — no OCR happens at any point in
     either path, so the PDF is a picture with zero extractable text.
- **If you still want to try archive.org:** on an item's "DOWNLOAD OPTIONS"
  list, avoid anything labelled "PDF" if a "Full text" or `_djvu.txt` file
  also exists next to it (that means OCR ran on this item — the PDF likely
  has a text layer). After downloading anything from there, always verify
  it yourself before sending it over: open it in a PDF reader and try to
  select/copy a sentence of body text. If you can select real words, it has
  a text layer and won't work here — I'll double check on my end too, but
  it saves a round trip if you catch it first.

## 3. Macedonian documents (1–2 of them)

This is the one that matters most for your title's claim — try to get at
least one text and one scanned.

- **Macedonian Wikipedia** (https://mk.wikipedia.org) — pick any article,
  same "Download as PDF" export as step 1. This gives you a native-text
  Macedonian PDF.
- **A scanned Macedonian document** — options, easiest first:
  - Print a Macedonian Wikipedia article and re-scan/photograph it (same
    trick as step 2, guarantees no text layer).
  - Search archive.org for Macedonian or Cyrillic-language scanned items.
  - Any Macedonian government or institutional PDF that's actually a scan
    (open it and check you can't select the text) — many older official forms
    are scanned rather than typeset.

## 4. What to send me

Once you have candidates, either:
- paste the links here, or
- download them into a folder and tell me the path,

and I'll pull them into an `eval/` folder in the repo (kept separate from the
`samples/` folder pytest uses), verify each one actually triggers the code
path it's meant to (native-text skips OCR, scanned triggers it), and then
hand it back to you to draft the 20–30 question/answer pairs against.

## Licensing note

These get committed to your public GitHub repo, so stick to sources that are
fine to redistribute: arXiv papers, EU public documents, Wikipedia exports
(CC-BY-SA), archive.org public-domain items, or anything you scan yourself.
Avoid pirated textbooks or anything without a clear right to share.
