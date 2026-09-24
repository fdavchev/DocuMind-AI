# Phase 8 (Hardening) — Session Report

**Date:** 2026-09-24
**Branch:** `feat/08-hardening` (created off `main` at `d94230ee`, after `feat/07-ocr-confidence` was merged via PR #7)

## What this session covered

Read section 6 of `docs/project-report-2.md` ("Phase 3 — Hardening" in the
thesis doc's numbering) and all of `DECISIONS.md` before writing anything, per
instructions. Verified each claimed-done item against the actual code rather
than assuming.

## Verification of items claimed already done

| Item | Status | Evidence |
|---|---|---|
| Exception hierarchy (Ollama down, model not pulled, corrupt/password-protected PDF, empty document, unsupported file type, Tesseract missing) | **VERIFIED by reading code** | `errors.py` — `FriendlyError` base with `OllamaUnavailable`, `ModelNotPulled`, `PdfTooLarge`, `UnreadablePdf`, `NoTextInPdf`, `EmptyDocumentError`, `UnsupportedFileError`, `NoDocumentsIndexed`, `OcrUnavailable`, `ScannedPdfTooLong`, plus pre-flight checks (`readiness`, `check_models`) and `guarded_stream` for mid-stream failures |
| Every `AppConfig` value injected, no literals left in logic files | **VERIFIED by reading code** | `documind/config.py` — all model names, chunk size, `k`, temperature, max_tokens, system_prompt, OCR language/confidence/page-limit are fields, consumed via constructor injection throughout |
| Multi-document support | **VERIFIED by reading code** | `documind/rag/vector_store.py` — `add()`, `remove()`, `sources` property, and `_default_k()` widening (DECISIONS.md #3) |

## The one real open item: FAISS persistence

Section 6 asks for FAISS index save/load keyed by a file hash. `vector_store.py`'s
own header comment says "There is deliberately no save/load here," documented
in `DECISIONS.md #9` as the app's privacy promise (no index file to leak).

**Asked Filip before writing any code.** He asked for my recommendation; I
recommended dropping it (marginal benefit — only saves 10–30s on a same-file
re-upload, which isn't how the demo or evaluation runs — against the cost of
contradicting a documented privacy guarantee and adding hash/cache-invalidation
complexity). Filip agreed: **dropped from scope.**

**Action taken:** added a dated addendum to `DECISIONS.md #9` recording that
persistence was reconsidered during Phase 3 hardening and declined for the
same reason as the original decision.

## Gap found and fixed: temperature/max_tokens not applied in `stream_answer`

While verifying "system_prompt and temperature genuinely applied," found that
`OllamaProvider.stream_answer` — the PDF/RAG answer path — called `ollama.chat()`
with no `options` dict at all. `stream_chat` and `stream_vision` both pass
`temperature`/`num_predict`; `stream_answer` passed neither. This was a real
gap, not something already done.

Asked Filip whether to also prepend `config.system_prompt` to the RAG prompt.
He chose temperature/max_tokens only (matches my recommendation) — the RAG
prompt already carries its own tailored instructions, and the generic
vision-assistant system prompt doesn't fit that context.

**Fix applied:** `documind/llm/ollama_provider.py` — `stream_answer` now passes
`options={"temperature": config.temperature, "num_predict": config.max_tokens}`.

## Branch discrepancy found and resolved

The task instructions assumed `feat/07-ocr-confidence` was already merged into
`main`. It was not — local `main` was 5 commits behind `origin/main`. Flagged
this to Filip rather than branching off a stale base (which would have dropped
all the OCR-confidence work this hardening phase depends on). Filip confirmed
it should already be merged; a `git fetch` showed it had just been merged on
GitHub via PR #7. Fast-forwarded local `main` to `origin/main`, then created
`feat/08-hardening` from the updated `main`, carrying the two pending edits
over.

## Verification of the fix

- **VERIFIED by automated test:** `pytest -q` — 255 passed, 0 failed, on
  `feat/08-hardening` after the branch move.
- **VERIFIED by live run:** `streamlit run app.py --server.headless true
  --server.port 8599`, then `GET /_stcore/health` → `200`. App boots cleanly
  with the change applied.

## Not verified / not done this session

- No answer-quality comparison was run (i.e., whether temperature actually
  changes RAG answer behavior in practice) — that's a manual/qualitative check
  outside what an automated test or a health check can confirm. **NOT VERIFIED.**
- No further Phase 3 items were started this session; the above was the
  complete list of open work once the persistence item was dropped.

## Files changed

- `DECISIONS.md` — addendum to decision #9
- `documind/llm/ollama_provider.py` — `stream_answer` now applies temperature/max_tokens
- `docs/class-notes.md` — new entry explaining the fix
- `docs/reports/2026-09-24-phase-08-hardening-start.md` — this report

## Commit message for Filip to use

```
Apply temperature and max_tokens to RAG answer generation in OllamaProvider.stream_answer, and drop FAISS persistence from Phase 3 scope with a note in DECISIONS.md #9.
```

Nothing committed — waiting for Filip to review and commit.
