# Two bug fixes: large-PDF uploads, and the PDF Q&A Clear button

**Date:** 2026-09-24
**Branch:** `fix/09-embedding-batches`

## 1. Large PDFs failed to upload

**Symptom:** uploading "working anytime anywhere" (93 pages) showed
*"Ollama returned an error. Post http://127.0.0.1:…/tokenize … actively
refused it"*. It kept happening after a PC restart.

**Cause:** the app sent every chunk of a document to Ollama's embedding model
in one request. This report splits into 792 chunks.
- Sending all 792 at once failed 2 times out of 3. **VERIFIED by live run.**
- Sending the same chunks in batches of 64 or 128 worked 6 out of 6 times,
  about 6 seconds each. **VERIFIED by live run.**
- Every 128-chunk slice of the document worked on its own, so no single chunk
  was at fault. **VERIFIED by live run.**
- Nothing in our code had changed. It only showed up because this was the
  first document with hundreds of chunks. **VERIFIED** by `git log` on
  `vector_store.py`, which was last changed in the Phase 6 refactor.
- Likely reason: Ollama turns one request into one internal connection per
  chunk, and Windows refuses the connections that overflow its waiting
  queue. **NOT VERIFIED.** This fits every observation but wasn't proven.

**Fix:** `VectorStore` now sends chunks in batches of 64
(`AppConfig.embedding_batch_size`). It collects every batch's vectors first
and adds them to the index in one step. If a batch fails partway, the index is
left exactly as it was, instead of holding half a document that the app would
never retry. Recorded in DECISIONS.md #17.

**Checks:**
- 5 new tests (batch sizes, every chunk indexed, rebuild still replaces the
  old index, a failed batch leaves the index untouched). **VERIFIED by
  automated test.**
- The 792-chunk report uploaded through the real `VectorStore` 3 times against
  the real Ollama: 3/3 passed (7.9s, 6.3s, 6.4s), then a search returned the
  right passage. **VERIFIED by live run.**

## 2. "Clear chat" did nothing in PDF Q&A

**Cause:** the sidebar's "🗑️ Clear chat" button only ever cleared Chat mode's
conversation. The real PDF reset button sat inside the Documents box, which
collapses as soon as a PDF is indexed, so it was effectively hidden.
**VERIFIED** by reading `app.py`.

**Fix:** the sidebar now has one reset button that follows the mode.
- In Chat mode it's "🗑️ Clear chat", same as before.
- In PDF Q&A it's "🗑️ Clear documents & chat". It clears the answers, the
  indexed PDFs and the uploader, back to how the page looks when first opened.

The hidden button was removed. Recorded in DECISIONS.md #18.

**Checks:**
- 6 new tests covering both labels, both resets, the first-open state after
  clearing, and exactly one clear button on the page. The 4 PDF-mode tests
  fail against the old `app.py` and pass against the new one. **VERIFIED by
  automated test.**
- The app starts and its health check returns 200. **VERIFIED by live run.**
- Clicking the button in a real browser: **NOT VERIFIED.** Filip should try
  it once.

## Test suite

263 passed, 0 failed (it was 252 at the start of the day). **VERIFIED by
automated test.**

## Loose ends

- Commit `d9709573` holds the whole embedding fix, but its message only
  mentions the test flake fix. Rewording it is optional; see the chat for the
  commands.
- Not fixed, only noticed: in PDF Q&A mode the sidebar's "💾 Save chat" button
  saves the *Chat* conversation, not the PDF questions and answers.
- `eval/qa_pairs.csv` rows 2–4 hold the app's own answers in the
  `correct_answer` column. They need re-checking against the PDFs, or the
  evaluation would grade the app against itself.
