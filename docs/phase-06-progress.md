# Phase 6 progress — OOP refactor

Tracks the OOP refactor described in [`docs/project-report-2.md`](project-report-2.md) §4 (called "Phase 1" in that document; renumbered to Phase 6 here to avoid colliding with this repo's existing `phase-01`…`phase-05` branches). The thesis plan doc now lives in this repo at `docs/project-report-2.md` — that's the canonical copy; treat it as source of truth over any other copy floating around (e.g. Desktop). **A new session working on this should read both files first, in full, before touching any code.** This file is written to be self-sufficient — everything decided so far is recorded here, not just referenced.

Branch: `phase-06-oop-refactor`, off `main` (which already has phase-01…phase-05 merged, confirmed 2026-09-21).

This file is the working tracker while the phase is in progress. Once all 10 items are done, its content gets folded into a proper phase entry in `docs/project-report.md` (matching how phases 0–5 are documented there), and this file can be deleted.

## How to resume in a new session

Say: *"Continue Phase 6 of DocuMind-AI, see docs/phase-06-progress.md."* Then:
1. Read this whole file.
2. Run `git status` and `git log --oneline -15` to confirm what's actually committed — the status table below is a snapshot and may be stale.
3. Pick up at the first item not marked ✅ committed.

## Naming note

The thesis plan document's own "Phase 1"–"Phase 5" (OOP refactor, OCR, hardening, tests, docs) is a different numbering scheme than this repo's `phase-01`…`phase-05` branches (citations, OCR fallback, error handling, docs, UI polish — already merged into `main`). This work continues the **repo's** numbering as **Phase 6**, even though it is "Phase 1" in the thesis document's own section numbers.

## Scope: 10 items, trimmed from the plan doc's ~12-class list

Went through every class in the plan doc against the thesis's OOP-principles table (§3 of `project-report-2.md`) with Filip and cut what doesn't earn a row there:

- **`ImageLoader` — cut.** Would be a new feature (OCR-searchable images), not a refactor of existing behavior. LLaVA vision already covers "understanding images" for the title's purposes.
- **`PromptBuilder` — cut.** Not tied to any principle in the table, pure code organization. Its would-be functions (`format_citation`, `build_context_block`, `format_sources_markdown`, `build_rag_prompt` — currently in `rag_chain.py`) get absorbed into `RagPipeline` at item 9 instead of a separate class.
- **`OcrEngine` — cut.** `ocr.py`'s existing functions (`is_available`, `page_needs_ocr`, `ocr_page`, `unavailable_hint`) aren't in the principles table either; `PdfLoader` (item 5) calls them directly.

## Working rules (do not deviate without asking Filip)

- **Git discipline:** the agent never runs `git add`/`commit`/`checkout`/`branch`/`reset`/`merge`/`stash`. Read-only git (`status`/`diff`/`log`) is fine. Filip commits every item himself, one commit per item.
- **Who codes:** each item is delegated to a `coder` subagent (Opus, high effort) with a detailed, self-contained prompt (the full prompt used for each completed item is summarized in that item's record below — reuse the same level of detail for remaining items). The orchestrating session relays results and waits for Filip's "committed, continue" before starting the next item.
- **Commit messages:** item 1 (first commit on this branch) got a subject + body, and a PR description was written at branch-creation time (see below). **Every commit since item 1 is a plain one-line subject only** — no `Phase 6:` prefix, no body, no `Co-Authored-By: Claude ...` trailer. Filip has said repeatedly he never wants Claude attribution in this repo's history (it leaked in once before across 9 commits and had to be fixed by force-pushing phase-01…phase-05).
- **No scope creep:** build only what's listed for the current item. Don't rename/restructure beyond what's specified. Don't add OCR confidence scoring, FAISS persistence, or anything from the thesis doc's later phases — those are future sessions (repo Phase 7+).
- **Tests are the safety net:** every item must leave `pytest -q` passing with the count flat or higher, never lower — no existing assertion gets deleted or weakened, only rewritten against new shapes when the underlying data shape changed.
- **App must keep booting:** `streamlit run app.py --server.headless true --server.port 8599`, check `/_stcore/health` → 200, after every item.
- **`docs/class-notes.md`** gets a new section per item as it's built — this is Filip's defence study material (3-5 plain sentences per class: what it does, why designed that way, which OO principle it demonstrates). Already has entries for items 1-4.

## PR description (written at branch creation, for when the PR opens)

```markdown
## Phase 6: OOP refactor

The thesis title claims "объектно-ориентирани принципи" (OOP
principles), but until now the codebase was 100% procedural — flat
modules, module-level functions and constants, zero domain classes
anywhere except the exception hierarchy in errors.py. This phase
closes that gap without changing what the app does: existing,
already-working behavior (RAG pipeline, OCR fallback, citations,
multi-document support, chat) moves into a class structure that maps
onto the OOP-principles table in the thesis plan document.

Scope was trimmed from ~12 classes to 10 (see docs/phase-06-progress.md
for the cut list and reasoning). Built incrementally, one class per
commit, each verified against the full pytest suite and a live
`streamlit run app.py` boot.
```

## Status

| # | Item | Status | Commit subject | Tests after |
|---|---|---|---|---|
| 1 | `AppConfig` | ✅ committed `f851d30c` | `Phase 6: Add AppConfig, replacing scattered config constants.` | 93 |
| 2 | `Document`, `ExtractedPage`, `Chunk` | ✅ committed `6f99aa85` | `Add Document, ExtractedPage and Chunk value objects.` | 102 |
| 3 | `Message`, `ChatSession` | ✅ committed `12a3236f` | `Add Message and ChatSession, replacing chat_history.py` | 119 |
| 4 | `LLMProvider` (ABC), `OllamaProvider` | ✅ committed `3470a79` | `Add LLMProvider and OllamaProvider, replacing llm_chain.py` | 137 | 
| 5 | `DocumentLoader` (ABC), `PdfLoader`, `TextLoader` | ✅ committed `1355696` | `Add DocumentLoader, PdfLoader and TextLoader, moving PDF loading out of pdf_handler.py` | 170 |
| 6 | `LoaderFactory` | ✅ committed `b2f93d0c` (⚠️ commit message says "DocumentLoader/PdfLoader/TextLoader" — item 5's message got reused by mistake; content is correct, message is wrong) | `Add LoaderFactory, dispatching uploads to PdfLoader or TextLoader by extension` | 190 |
| 7 | `TextSplitter` | ✅ committed `ad119feb` | `Add TextSplitter, moving page-by-page chunking out of pdf_handler.py` | 206 |
| 8 | `VectorStore` | ✅ built, awaiting commit | `Add VectorStore, wrapping FAISS behind a Chunk-in, Chunk-out interface` | 226 |
| 9 | `RagPipeline` | ⬜ not started | — | — |
| 10 | Strip `app.py`; delete `pdf_handler.py`/`rag_chain.py` | ⬜ not started | — | — |

---

## Detailed record — completed items

### Item 1 — `AppConfig` (committed `f851d30c`)

**Built:** `documind/__init__.py` (empty), `documind/config.py` — frozen dataclass `AppConfig` with fields: `app_title`, `app_icon`, `available_models` (tuple — immutable), `default_model`, `vision_model`, `answer_model`, `embedding_model`, `chunk_size`, `chunk_overlap`, `retrieval_k` (4), `retrieval_k_multi_document` (6 — `app.py` hardcoded `k=4 if one file else 6`, both numbers are real behavior so both became fields), `temperature`, `max_tokens`, `system_prompt`, `max_ocr_pages`.

**Deliberately excluded fields:** no `ocr_language`, no `ocr_min_confidence` — neither is implemented anywhere yet, adding them now would be the exact "decorative config" bug this step fixes. `OCR_RESOLUTION` and `MIN_CHARS_FOR_TEXT_LAYER` stayed local to `ocr.py` (only `ocr.py` reads them; only `MAX_OCR_PAGES` was genuinely cross-module, living in the wrong file, so only it moved).

**Bug fixed:** `temperature`/`max_tokens`/`system_prompt` were defined in the old `config.py` but never read anywhere. Now: `llm_chain.py`'s `build_llm` passes `temperature=config.temperature, num_predict=config.max_tokens` to `OllamaLLM`; `stream_response` prepends `config.system_prompt` to the prompt (langchain-ollama 1.1.0's `OllamaLLM` has no `system` field, confirmed by reading installed source); `stream_vision_response` sends a `{"role": "system"}` message plus `options={"temperature":..., "num_predict":...}` to `ollama.chat`, model from `config.vision_model` instead of a hardcoded `"llava"`.

**Deliberate non-change:** `rag_chain.py`'s `ollama.chat` call does NOT get `temperature`/`system_prompt` — the RAG prompt has its own grounding rules; injecting the vision-assistant persona/temperature there would regress document Q&A. Only `answer_model` comes from config on that path.

**Old `config.py`:** kept (still owns `CHAT_MODE`, `PDF_MODE`, `USER_AVATAR`, `ASSISTANT_AVATAR` — UI vocabulary), but migrated constants were deleted from it, not left duplicated.

**Files changed:** `app.py`, `pdf_handler.py`, `vector_store.py`, `rag_chain.py`, `llm_chain.py`, `ocr.py` (removed `MAX_OCR_PAGES`), `errors.py` (`ScannedPdfTooLong` now takes the limit as a constructor arg instead of reading `ocr.MAX_OCR_PAGES`), `config.py` (trimmed), `README.md`, plus test import fixes in `test_pdf_handler.py`/`test_rag_chain.py`/`test_ocr.py`.

### Item 2 — `Document`, `ExtractedPage`, `Chunk` (committed `6f99aa85`)

**Built:** `documind/documents/__init__.py`, `documind/documents/models.py`:
- `ExtractedPage(number: int, text: str, used_ocr: bool, ocr_confidence: float | None = None)` — `ocr_confidence` always `None` today, reserved shape for a future OCR-confidence phase.
- `Document(name: str, pages: tuple[ExtractedPage, ...])` with properties `.text` (pages joined with `"\n\n"`), `.page_count`, `.ocr_page_count`, `.is_empty`.
- `Chunk(text: str, page_number: int, source_document: str)`.

**Renames (deliberate, not accidental):**
- `pdf_handler.split_pages_into_chunks` → `split_document_into_chunks` (now takes a `Document`, since `Document` already carries the filename that used to be a second arg).
- `pdf_handler.load_pdf_as_documents` → `load_pdf_as_chunks` (it returns `Chunk`s, not `Document`s — the old name was misleading now that a real `Document` class exists with a different meaning; one call site in `app.py` updated).
- New: `pdf_handler.load_pdf_as_document(uploaded_file, name=None, ...) -> Document`.
- `extract_pages_from_pdf` now returns `list[ExtractedPage]` (was `list[tuple[int, str]]`), with `used_ocr=True` threaded through only on the branch that actually called `ocr.ocr_page` (this OCR-per-page tracking is genuinely new — nothing recorded it before).

**Vector-store boundary decision (important for item 8):** `Chunk` → LangChain `Document` conversion happens **only going in** to FAISS, inside a new `vector_store._as_documents` helper (`chunk.text` → `page_content`, `{"source": chunk.source_document, "page": chunk.page_number}` → metadata). Results coming **out** of FAISS are NOT converted back to `Chunk` — they stay as LangChain `Document`s, since that's honestly what FAISS stores. This means `rag_chain.py`'s citation functions (`format_citation` etc.) needed zero changes. **When item 8 (`VectorStore` class) is built, its `search()` method is specified to return `Chunk` objects** — so that conversion-on-the-way-out needs to be added then; it does not exist yet.

**Files changed:** `pdf_handler.py`, `vector_store.py` (`_as_documents` helper added, FAISS internals otherwise untouched), `app.py`, plus test updates in `test_pdf_handler.py`, `test_ocr.py`, `test_vector_store.py`, `test_integration.py`, `test_errors.py`. `rag_chain.py` and `test_rag_chain.py` were untouched by this item.

### Item 3 — `Message`, `ChatSession` (committed `12a3236f`)

**Built:** `documind/chat/__init__.py`, `documind/chat/message.py` (`Message(role: str, content: str, timestamp: datetime)` — plain `str` role, no `Role` enum, deliberately out of scope), `documind/chat/chat_session.py`:
```python
class ChatSession:
    def __init__(self, system_prompt: str | None = None)
    def add_user(self, content: str) -> None
    def add_assistant(self, content: str) -> None
    def clear(self) -> None
    def export(self) -> str          # format copied character-for-character from the old chat_history.export_history, pinned by an exact-string test
    @property
    def messages(self) -> tuple[Message, ...]   # builds a FRESH tuple every read
    @property
    def is_empty(self) -> bool
```
`_messages` is genuinely private: no constructor path accepts an existing list, `_messages` is never referenced outside the class, `.messages` never returns the live list. This is the thesis's **encapsulation** exhibit — contrast explicitly with old `chat_history.py`'s bare mutable list in the defence write-up. `_system_prompt` is stored but not yet read (there's a code comment pointing at the `OllamaProvider` step as where it starts being used).

**`llm_chain.stream_response` signature changed:** now takes `Sequence[Message]` directly instead of a list of role/content dicts (judgment call: smaller and more honest than converting back to dicts at the `app.py` boundary, since the dict shape was exactly what this step exists to remove). Internals read `.role`/`.content` off `Message` objects.

**Small behavior change (not a regression, but real):** `app.py` used to keep a hand-maintained `st.session_state.export_snapshot`, updated only after a successful assistant reply. This is gone — the Save button now calls `chat_session.export()` directly, live. Side effect: if a reply errors mid-stream, the Save button now exports the real partial conversation instead of showing stale/empty content from before the failed turn.

**`app.py` rendering split:** `render_message` → split into `render_chat_message(Message)` and `render_pdf_message(dict)`, since PDF-mode still uses dicts (that's `rag_chain.py`'s territory, unchanged until item 9) and one function couldn't honestly serve both shapes.

**Files changed:** `app.py`, `llm_chain.py`, `docs/architecture.md`, `README.md` (both had stale references to the now-deleted `chat_history.py`; README tree also gained `documind/`, missing since item 1). **Deleted:** `chat_history.py` (grep-confirmed zero importers first). **Created test:** `tests/test_chat_session.py`, including a test that `.messages` returns a copy — mutating the returned tuple/a list built from it does not affect session state.

### Item 4 — `LLMProvider`, `OllamaProvider` (committed `3470a79`)

**Built:** `documind/llm/__init__.py`, `documind/llm/llm_provider.py`:
```python
class LLMProvider(ABC):
    def is_available(self) -> bool
    def stream_chat(self, messages: Sequence[Message]) -> Iterator[str]
    def stream_vision(self, image: bytes, prompt: str) -> Iterator[str]
    def stream_answer(self, prompt: str) -> Iterator[str]   # takes an already-built prompt string — RagPipeline (item 9) builds the prompt, not a PromptBuilder (cut from scope)
```
`documind/llm/ollama_provider.py` — `OllamaProvider(config: AppConfig, model_name: str | None = None)` implementing all four methods.

**Absorbed:** `llm_chain.build_llm` + `stream_response` → `stream_chat`; `llm_chain.stream_vision_response` → `stream_vision` (JPEG conversion, system message, vision-model pin, temperature/max_tokens options all carried over unchanged); `rag_chain.stream_rag_answer`'s raw `ollama.chat` generation call → `stream_answer`.

**Boundary decision (matters for item 9):** everything citation/prompt-shaped **stayed in `rag_chain.py`** — `format_citation`, `build_context_block`, `format_sources_markdown`, `build_rag_prompt` were NOT touched. Only the underlying `ollama.chat` call moved. `rag_chain.stream_rag_answer` now reads:
```python
prompt = build_rag_prompt(context, question)
return (provider or OllamaProvider(config)).stream_answer(prompt)
```
Both `stream_rag_answer` and `stream_rag_answer_from_documents` gained an optional `provider: LLMProvider | None = None` kwarg (defaults to a fresh `OllamaProvider`) — **this is the exact seam a `FakeProvider` drops into for item 9's `RagPipeline` tests, no monkeypatching needed.** `rag_chain.py` no longer imports `ollama` at all.

**`is_available()`:** `errors.readiness([self._model_name]) is None` — reuses `errors.py`'s existing connection-error/model-not-pulled detection rather than duplicating it. Returns `False` for any unexpected exception too (covered by a test), never raises.

**Model-switching judgment call:** `app.py` previously kept one `st.session_state.llm`, rebuilt on sidebar model-switch. Preserved 1:1 as `st.session_state.provider = OllamaProvider(config, selected_model)`, rebuilt on switch — one instance at a time, not one per model. Vision and RAG-answer calls pin their own models from config regardless of the sidebar selection (`stream_vision` always uses `config.vision_model`, `stream_answer` always uses `config.answer_model`), pinned by two dedicated tests.

**Files changed:** `app.py`, `rag_chain.py`, `documind/chat/chat_session.py` (stale comment fix), `docs/architecture.md`, `README.md`, plus `test_rag_chain.py`/`test_integration.py` (their Ollama-monkeypatch target moved from `rag_chain.ollama.chat` to `documind.llm.ollama_provider.ollama` — same underlying module object). **Deleted:** `llm_chain.py` (grep-confirmed). **Created test:** `tests/test_ollama_provider.py` (18 tests) — includes one that builds a throwaway `FakeProvider` subclass and one asserting an incomplete `LLMProvider` subclass raises `TypeError` (proves the ABC actually enforces its contract).

---

### Item 5 — `DocumentLoader`, `PdfLoader`, `TextLoader` (committed `1355696`)

**Built:** `documind/documents/document_loader.py` — `DocumentLoader(ABC)`: `SUPPORTED_EXTENSIONS`, `DEFAULT_NAME`, `__init__(config)`, `supports(filename)` (classmethod, case-insensitive extension match), abstract `_extract_pages(file)`, and the `load(file, name=None)` template method (resolve name → `UnsupportedFileError` if extension unhandled → `_extract_pages` → wrap in `Document` → `EmptyDocumentError` if empty). `documind/documents/pdf_loader.py` — `PdfLoader(config, use_ocr=True)`, `.pdf` only, plus `scanned_page_count(file)` moved in from `pdf_handler`. `documind/documents/text_loader.py` — `TextLoader`, `.txt`/`.md`, UTF-8 then cp1251 fallback, whole file as page 1.

**OCR-fallback logic:** machine-diff confirmed `PdfLoader._extract_pages` is byte-identical to the old `pdf_handler.extract_pages_from_pdf` body (only self/param renames) — same 20-char `MIN_CHARS_FOR_TEXT_LAYER` threshold, same `len(ocr_pages) > config.max_ocr_pages` → `ScannedPdfTooLong` guard, same per-page OCR threading. Calls `ocr.page_needs_ocr`/`ocr.ocr_page` directly, no `OcrEngine` wrapper.

**New errors:** `EmptyDocumentError`, `UnsupportedFileError` added to `errors.py`'s existing `FriendlyError` hierarchy.

**`pdf_handler.py` — partially retained, not deleted.** Grep found live importers outside this item's scope (`app.py`'s `load_pdf_as_chunks`/`scanned_page_count`, plus several test files, and `split_document_into_chunks` which is item 7's job). So `pdf_handler.py`'s loading half now just delegates to `PdfLoader`'s public API: `load_pdf_as_document` calls `PdfLoader(config, use_ocr=use_ocr).load(uploaded_file, name=name)`, catching `EmptyDocumentError` to preserve the existing "return empty `Document`" behavior `app.py` depends on (it distinguishes "scanned, no OCR" from "genuinely blank" itself). `extract_pages_from_pdf` and `scanned_page_count` are now thin wrappers. `pdf_handler.py` no longer imports `pdfplumber` or `ocr` — only the LangChain splitter logic remains (item 7's territory), and its header comment says it goes away once that moves. **This is the seam items 7/9/10 need to know about.**

**One spec deviation:** `load()` takes an optional `name` param (`load(self, file, name=None)`) to preserve `load_pdf_as_document(pdf, name="thesis.pdf")`'s existing explicit-naming capability, pinned by existing tests. `load(file)` alone still works as specified.

**Files changed:** `errors.py`, `pdf_handler.py` (loading delegated, not deleted), `README.md`, `docs/architecture.md`, `docs/class-notes.md` (new item-5 section). **Created test:** `tests/test_document_loader.py` (33 tests, including 3 `test_both_loaders_*` tests running identical assertions over `PdfLoader`/`TextLoader` — the polymorphism exhibit — and an ABC-enforcement test).

**Tests:** 170 passing (137 + 33 new, nothing edited/deleted). **Streamlit:** boots clean, `/_stcore/health` → 200.

---

### Item 6 — `LoaderFactory` (committed `b2f93d0c`, commit message text is item 5's — content is correct)

**Built:** `documind/documents/loader_factory.py`:
```python
class LoaderFactory:
    LOADERS: tuple[type[DocumentLoader], ...] = (PdfLoader, TextLoader)   # the registry — one place
    def __init__(self, config: AppConfig)
    @classmethod
    def supported_extensions(cls) -> tuple[str, ...]      # deduped union, read off the loaders
    def create_loader(self, filename: str) -> DocumentLoader
```
`create_loader` walks `LOADERS`, returns `loader(self._config)` for the first whose `supports(filename)` is true, else raises `UnsupportedFileError(filename, supported=self.supported_extensions())`. Zero extension strings live in the factory itself — dispatch holds nothing format-specific.

**Naming deviation:** chose `create_loader` over the thesis plan doc's `for_file` sketch (that snippet is already non-literal — it references a cut `OcrEngine`/`ImageLoader`) to match this repo's verb-first method convention (`load`, `supports`, `add_user`, `stream_chat`, `ingest`).

**Added beyond the sketch:** `supported_extensions()` classmethod — needed anyway to fill `UnsupportedFileError`'s `supported=` arg, and can feed `st.file_uploader(type=...)` at item 10 without extra work.

**Judgment call:** returns a **fresh** loader per call rather than caching instances, because `PdfLoader`/`TextLoader` read from (and `TextLoader` seeks) the file object — a shared cached instance could hold another caller's half-read upload. Pinned by `test_each_call_returns_a_fresh_loader`.

**Open-closed exhibit for the defence:** tests define an `HtmlLoader` the factory has never seen, register it via a one-line subclass (`class HtmlAwareFactory(LoaderFactory): LOADERS = LoaderFactory.LOADERS + (HtmlLoader,)`), and show it dispatches correctly with zero edits to dispatch logic.

**Files changed:** `docs/class-notes.md` (new section), `README.md` (tree + test-coverage table), `docs/architecture.md` (documents/ row mentions LoaderFactory). No changes to `app.py`, `errors.py`, or `pdf_handler.py` — `LoaderFactory` isn't wired into the upload flow yet (that's item 10). **Created test:** `tests/test_loader_factory.py` (20 tests).

**Tests:** 190 passing (170 + 20 new, nothing edited/deleted). **Streamlit:** boots clean, `/_stcore/health` → 200.

---

### Item 7 — `TextSplitter` (committed `ad119feb`)

**Built:** `documind/documents/text_splitter.py`:
```python
class TextSplitter:
    def __init__(self, config: AppConfig)
    def split(self, document: Document) -> list[Chunk]
    def split_text(self, text: str) -> list[str]
```
`RecursiveCharacterTextSplitter` built once in `__init__` (not per call — safe, since it's stateless over strings, unlike item 6's loaders which hold file objects). `SEPARATORS = ["\n\n", "\n", ".", " "]` moved across unchanged as a module constant. `split()` body is the old `split_document_into_chunks` body verbatim, including the blank-chunk skip.

**Deviation from sketch:** added `split_text(text) -> list[str]` alongside `split()`, because `pdf_handler.split_text_into_chunks` exists and is pinned by an existing test — without it, `pdf_handler.py` would still need to import `RecursiveCharacterTextSplitter` itself, defeating the point (TextSplitter is now the only place in the project naming LangChain's splitter). `split()` calls `split_text()` per page internally.

**`pdf_handler.split_document_into_chunks`/`split_text_into_chunks`: kept as thin delegating wrappers**, matching item 5's pattern — live callers outside scope (`load_pdf_as_chunks` used by `app.py`, `test_vector_store.py`, `test_ocr.py`, `test_integration.py`; `test_pdf_handler.py` directly) meant full deletion wasn't possible yet. `pdf_handler.py` no longer imports `langchain_text_splitters` at all; header comment says the file holds nothing of its own now, only wrappers, and names item 10 as removal point.

**"No chunk spans two pages" invariant:** `DECISIONS.md` #1's `test_no_chunk_spans_two_pages` (`tests/test_pdf_handler.py:152`) is untouched and still passing (now exercises the invariant through the delegating wrapper). Also ported directly onto `TextSplitter` in the new test file, plus a stronger case (`test_no_chunk_spans_two_pages_even_when_pages_are_short`) — pinned at both levels now.

**Files changed:** `pdf_handler.py` (splitting delegated), `docs/class-notes.md` (new section), `README.md`, `docs/architecture.md`. **Created test:** `tests/test_text_splitter.py` (16 tests).

**Tests:** 206 passing (190 + 16 new, nothing edited/deleted). **Streamlit:** boots clean, `/_stcore/health` → 200.

---

### Item 8 — `VectorStore` (built + verified, **not yet committed**)

**Built:** `documind/rag/__init__.py`, `documind/rag/vector_store.py`:
```python
class VectorStore:
    def __init__(self, config: AppConfig, embeddings=None)
    def build(self, chunks: Sequence[Chunk]) -> None
    def add(self, chunks: Sequence[Chunk]) -> None
    def search(self, question: str, k: int | None = None) -> list[Chunk]
    @property
    def is_ready(self) -> bool
    @property
    def sources(self) -> tuple[str, ...]
```

**Deviations (deliberate):**
1. `embeddings=None` kwarg — keeps DECISIONS.md #4's injectable embedding model working without needing a live Ollama in tests; built lazily on first `build()`.
2. `sources` property added (wraps old `list_sources`) — needed by `_default_k` to know document count, and by item 10 to replace `st.session_state.pdf_filenames`. Returns sorted `tuple[str, ...]`.
3. `add()` on an empty store now builds it instead of failing — removes the `if store is None: build else add` branch currently in `app.py:259-264`. `build()` still replaces the index outright.

**Behavior flag for item 9:** `search()` on a not-ready store **raises** `RuntimeError`, doesn't return `[]` — an empty context would get a confidently wrong LLM answer; `app.py` already disables input until a store exists, so this is unreachable from the UI today but matters if `RagPipeline` calls `search()` directly.

**Chunk round-trip complete (item 2's missing half):** `_as_documents` (in, unchanged shape) and new `_as_chunk` (out): `document.page_content` → `text`, `metadata.get("page", 0)` → `page_number`, `metadata.get("source", "")` → `source_document`. Tested via dataclass-equality round-trip and a real generated-PDF end-to-end test (loader → splitter → index → search).

**`k` defaults:** `_resolve_k` uses `k` if given, else `_default_k()` reads `len(self.sources)`: `<=1` → `config.retrieval_k`, else → `config.retrieval_k_multi_document` — moves `app.py:351-355`'s rule inside the object, now reading the store's own indexed sources.

**No persistence added** — `test_there_is_no_persistence_yet` asserts no `save`/`load` attributes exist, citing DECISIONS.md #9.

**Old top-level `vector_store.py`:** untouched, still the only thing `app.py` imports (`build_vector_store`, `add_documents`, `retrieve_relevant_documents`) — rewiring is items 9/10.

**Files changed:** `docs/class-notes.md` (new section), `README.md`, `docs/architecture.md`. **Created test:** `tests/test_rag_vector_store.py` (20 tests — separate file so the existing `tests/test_vector_store.py` for the old module functions stays untouched).

**Tests:** 226 passing (206 + 20 new, nothing edited/deleted). **Streamlit:** boots clean, `/_stcore/health` → 200.

**⚠️ Not committed yet — run `git status` to confirm current state before starting item 9.**

---

## Full spec for remaining items

### Item 9 — `RagPipeline`

Target file: `documind/rag/rag_pipeline.py`.

```python
class RagPipeline:
    def __init__(self, loader_factory: LoaderFactory, splitter: TextSplitter,
                 vector_store: VectorStore, provider: LLMProvider): ...
    def ingest(self, file) -> IngestReport: ...
    def ask(self, question: str) -> Iterator[str]: ...
    @property
    def last_sources(self) -> tuple[Chunk, ...]: ...
```
`IngestReport` — small dataclass: page count, chunk count, OCR page count, elapsed seconds (values already loosely available in `app.py`'s current upload flow — formalize them here).

**Absorbs `rag_chain.py`'s prompt/citation functions** (`format_citation`, `build_context_block`, `format_sources_markdown`, `build_rag_prompt`) as `RagPipeline`'s own methods — there is no separate `PromptBuilder` (cut from scope). `RagPipeline.ask()` builds the prompt itself, then calls `self._provider.stream_answer(prompt)` — reusing the exact seam item 4 built (`provider` param on `stream_rag_answer`/`stream_rag_answer_from_documents`) means a `FakeProvider` test double should already be straightforward here; write one if it doesn't exist yet.

### Item 10 — Strip `app.py` to UI-only

Build `AppConfig`, `LoaderFactory`, `TextSplitter`, `VectorStore`, `OllamaProvider`, `RagPipeline` once at startup in `app.py`; the rest of `app.py` should only call methods on these objects plus Streamlit widget code. **Self-check:** `grep -nE "pdfplumber|ollama|faiss|langchain" app.py` must return nothing. Delete `rag_chain.py` and the old top-level `pdf_handler.py`/`vector_store.py` once `RagPipeline`/`VectorStore`/`PdfLoader` fully cover them (grep-confirm no other importers first).

---

## Verification checklist for the end of the whole phase

```
grep -nE "pdfplumber|ollama|faiss|langchain" app.py     → must return NOTHING
grep -rn "^class " documind/ | wc -l                    → 10+ classes/groups
grep -rn "ABC|abstractmethod" documind/                 → at least 2 ABCs
streamlit run app.py                                    → app starts
pytest -v                                                → all green
```
Plus manually confirm: chat tab streams, PDF tab answers with citations, model switching works, export works, and `chat_history.py` (✅ deleted), `llm_chain.py` (✅ deleted), `pdf_handler.py`, `rag_chain.py`, and the old top-level `vector_store.py` are all deleted by the end.

## Explicitly out of scope for this phase

- Thesis-plan document's Phases 2–5 (OCR confidence scoring, hardening/persistence, evaluation chapter, UML diagrams) — future sessions, would be repo Phase 7+.
- Any evaluation numbers — never fabricate these, that's Filip's own work (see `project-report-2.md` §11.6 — the plan doc itself calls fabricated evaluation numbers "the most dangerous possible failure in a thesis").
