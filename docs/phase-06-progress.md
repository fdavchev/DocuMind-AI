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
| 4 | `LLMProvider` (ABC), `OllamaProvider` | ✅ committed `3470a79` (check again Filip changed this manually) | `Add LLMProvider and OllamaProvider, replacing llm_chain.py` | 137 | 
| 5 | `DocumentLoader` (ABC), `PdfLoader`, `TextLoader` | ⬜ not started | — | — |
| 6 | `LoaderFactory` | ⬜ not started | — | — |
| 7 | `TextSplitter` | ⬜ not started | — | — |
| 8 | `VectorStore` | ⬜ not started | — | — |
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

### Item 4 — `LLMProvider`, `OllamaProvider` (built + verified, **not yet committed**)

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

**⚠️ Not committed yet — run `git status` to confirm current state before starting item 5.**

---

## Full spec for remaining items

### Item 5 — `DocumentLoader` (ABC), `PdfLoader`, `TextLoader`

Target files: `documind/documents/document_loader.py`, `documind/documents/pdf_loader.py`, `documind/documents/text_loader.py`.

```python
class DocumentLoader(ABC):
    SUPPORTED_EXTENSIONS: tuple[str, ...] = ()
    def __init__(self, config: AppConfig): ...
    @abstractmethod
    def _extract_pages(self, file) -> list[ExtractedPage]: ...
    def load(self, file) -> Document:          # template method: validate → _extract_pages → wrap in Document → raise EmptyDocumentError if empty
    @classmethod
    def supports(cls, filename: str) -> bool: ...
```

- `PdfLoader._extract_pages` absorbs `pdf_handler.extract_pages_from_pdf`'s per-page OCR-fallback logic **verbatim** — same 20-char (`MIN_CHARS_FOR_TEXT_LAYER`) threshold, same `config.max_ocr_pages` guard raising `ScannedPdfTooLong`. Calls `ocr.py`'s existing functions (`page_needs_ocr`, `ocr_page`) directly — no `OcrEngine` wrapper (cut from scope).
- `TextLoader` is new but trivial: `.txt`/`.md`, try UTF-8 first, fall back to cp1251 for older Macedonian files. Exists purely to give the ABC a second subclass so polymorphism/inheritance are demonstrated from two real implementations, not asserted from one (this reasoning is spelled out in `project-report-2.md` §4.4 — worth quoting in the class-notes entry).
- No `ImageLoader` (cut from scope).
- Define `EmptyDocumentError`, `UnsupportedFileError` **inside the existing `errors.py` hierarchy** (subclassing `FriendlyError`) — do not create a parallel exception hierarchy.
- Delete `pdf_handler.py` once `PdfLoader` fully covers it (grep-confirm no other importers first — `app.py` and possibly `vector_store.py` tests may still reference it).

### Item 6 — `LoaderFactory`

Target file: `documind/documents/loader_factory.py`. Dispatches by filename extension across `PdfLoader`/`TextLoader` (constructed with the same `AppConfig`). Raises `UnsupportedFileError` for anything else (e.g. `.docx`).

### Item 7 — `TextSplitter`

Target file: `documind/documents/text_splitter.py`. Wraps the existing per-page splitting logic from item 5/`pdf_handler.split_document_into_chunks` (or wherever it lands after item 5's rename) — wraps LangChain's `RecursiveCharacterTextSplitter` using `config.chunk_size`/`config.chunk_overlap`, split **per page**, tagging each resulting `Chunk` with its page number. **Must preserve the "no chunk spans two pages" invariant** — there is already a pinned test for this (`DECISIONS.md` #1), find it and keep it passing.

### Item 8 — `VectorStore`

Target file: `documind/rag/vector_store.py` (note: this is a NEW file in a new `documind/rag/` package — the old top-level `vector_store.py` stays for now and gets superseded, not necessarily deleted until item 9/10 confirm nothing else needs it).

```python
class VectorStore:
    def __init__(self, config: AppConfig): ...
    def build(self, chunks: Sequence[Chunk]) -> None: ...
    def add(self, chunks: Sequence[Chunk]) -> None: ...          # multi-document support — mirrors old add_documents
    def search(self, question: str, k: int | None = None) -> list[Chunk]: ...   # returns Chunk objects — this is where the Chunk→Document→Chunk round-trip conversion (noted as missing in item 2's record above) needs to be added
    @property
    def is_ready(self) -> bool: ...
```
Wraps the existing FAISS logic (`get_embeddings`, `build_vector_store`, `add_documents`, `retrieve_relevant_documents`, `list_sources`) from the old `vector_store.py`. **Do not implement `save`/`load` (persistence)** — explicitly deferred; `DECISIONS.md` #9 already has a reasoned decision not to have it yet. Don't relitigate that here.

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
