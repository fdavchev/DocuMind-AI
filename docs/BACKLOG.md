# Backlog

Bugs and ideas noticed during work but not worth blocking on. Pick up when convenient.

## Bugs

### Flaky test: `test_rag_pipeline.py::test_last_sources_holds_the_retrieved_chunks`

**Found:** 2026-09-24, during Phase 7 (OCR confidence scoring) verification, on `feat/07-ocr-confidence`.

Failed once in an early `pytest` run during that session, with no code change of its own in flight at the time. Unreproducible across 88 subsequent runs (80 with `PYTHONHASHSEED` varied 1-80, 8 full-suite reruns) — all passed. Cause unknown; predates Phase 7 and wasn't caused by it. Worth a proper investigation (likely a test-ordering or fixture-isolation issue, since chunk/source ordering is the kind of thing hash-seed variation would expose) next time someone's in `tests/test_rag_pipeline.py`.
