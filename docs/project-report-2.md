# DocuMind-AI — Detailed Implementation Plan for the Diploma Thesis

**Thesis title:** „Имплементација на AI чат-бот за анализа на документи и препознавање на текст со користење на објектно-ориентирани принципи"

**Repo:** https://github.com/fdavchev/DocuMind-AI
**Plan written:** 2026-09-09

---

## How to use this document

Sections 1–2 are the diagnosis: what is missing and why it matters. **Section 4 is the actual work** — it lists every file you need to create, every class inside it, every method signature, what moves out of your current code, and what to say about it at the defence.

Items marked **[CORE]** are required to make the title honest. Items marked **[OPTIONAL]** make the thesis stronger but can be dropped if you run out of time — decide on those with your mentor rather than building everything.

---

## 1. Where the project stands today

The title makes four promises. Two are kept, two are not.

| Claim in the title | Status | Evidence in the repo |
|---|---|---|
| AI чат-бот | **Done** | Streamlit UI, Ollama backend, multi-turn chat, token streaming, model switching, chat export |
| Анализа на документи | **Done** | Real RAG: pdfplumber → chunking (500/50) → nomic-embed-text → FAISS → grounded prompt |
| Препознавање на текст | **Missing** | `pdfplumber.extract_text()` reads an existing text layer, it does not recognise text. No Tesseract / EasyOCR / PaddleOCR anywhere |
| Објектно-ориентирани принципи | **Missing** | **Zero `class` statements in the entire repository.** All 7 files are module-level functions passing lists and dicts |

**Bottom line: keep the topic, keep the title, close the two gaps.** The hard part — a working local RAG pipeline — already exists.

### Why the OOP gap is the serious one

`chat_history.py` is the textbook *procedural* alternative to a class:

```python
def init_memory() -> list: return []
def add_message(history: list, role: str, content: str) -> list: ...
def clear_history(history: list) -> list: ...
```

Passing the state in as the first argument of every function is exactly what an object exists to avoid. Consequences:

- The first question at the defence will be *"which OO principles, show me where"* — and there is no answer.
- **You cannot draw a UML class diagram**, which a diplomski trud normally requires.

### Why the OCR gap is real, not cosmetic

Your own code documents the bug:

```python
page_text = page.extract_text()
if page_text:  # some pages are images and return None
```

A scanned PDF yields an empty string and the app silently answers nothing. That is precisely the case OCR solves. LLaVA reading text off an image is incidental vision-model behaviour — not something you designed, and not something you can measure.

---

## 2. Other things a committee will flag

- **`config.py` configures nothing.** `TEMPERATURE`, `MAX_TOKENS` and `SYSTEM_PROMPT` are defined and never used. The values that matter are hardcoded elsewhere: `ANSWER_MODEL` in `rag_chain.py`, `EMBEDDING_MODEL` in `vector_store.py`, `chunk_size=500` in `pdf_handler.py`.
- **Dead / deprecated imports.** `from langchain_community.llms import Ollama` is the legacy path; `ChatOllama` is imported but never used; `import ollama` appears twice in `llm_chain.py`.
- **No tests at all.**
- **No error handling.** A corrupt PDF, Ollama not running, or a missing model all crash raw.
- **No evaluation.** A thesis needs a results chapter with numbers.
- **No persistence** — the FAISS index is rebuilt from scratch on every upload.
- **9 commits over ~3 months.** Commit in small, meaningful steps from now on; the history is read as evidence the work is yours.

---

## 3. The OO principles you must be able to point at

Before writing code, know what you are aiming to demonstrate. At the defence you need one sentence and one class for each row. This table is the skeleton of your OOP chapter.

| Principle | Where it will live | What you say |
|---|---|---|
| **Abstraction** | `DocumentLoader`, `LLMProvider` (both ABCs) | "The pipeline depends on an interface, not on pdfplumber or Ollama." |
| **Inheritance** | `PdfLoader`, `ImageLoader`, `TextLoader` extend `DocumentLoader`; `OllamaProvider` extends `LLMProvider` | "Shared behaviour lives in the base class; each subclass supplies only what differs." |
| **Polymorphism** | `RagPipeline` calls `loader.load(file)` without knowing the concrete type | "Adding a DOCX loader requires no change to the pipeline." |
| **Encapsulation** | `ChatSession._messages`, `VectorStore._index` | "The history cannot be corrupted from outside; it is only reachable through `add_user()` / `clear()`." |
| **Composition** | `RagPipeline` holds a loader, splitter, store and provider | "Composition over inheritance — the pipeline *has* these parts, it is not one of them." |
| **Strategy pattern** | `LLMProvider` implementations | "Swapping Ollama for another backend is one constructor argument." |
| **Factory pattern** | `LoaderFactory.for_file()` | "Choosing the loader is one decision in one place, not an if-chain in the UI." |
| **Value objects** | `Message`, `Chunk`, `Document` | "Immutable data with meaning, instead of anonymous dicts." |

---

## 4. Phase 1 — Refactor to OOP  **[CORE — do this first]**

Everything else depends on this. Until it exists you cannot draw the class diagram, and you cannot write unit tests.

### 4.0 Target structure

```
documind/
├── __init__.py
├── config.py                   AppConfig
├── documents/
│   ├── models.py               Document, ExtractedPage, Chunk
│   ├── document_loader.py      DocumentLoader (ABC)
│   ├── pdf_loader.py           PdfLoader
│   ├── image_loader.py         ImageLoader
│   ├── text_loader.py          TextLoader
│   ├── loader_factory.py       LoaderFactory
│   └── text_splitter.py        TextSplitter
├── ocr/
│   ├── ocr_engine.py           OcrEngine
│   └── models.py               OcrResult
├── llm/
│   ├── llm_provider.py         LLMProvider (ABC)
│   ├── ollama_provider.py      OllamaProvider
│   └── prompt_builder.py       PromptBuilder
├── chat/
│   ├── message.py               Message
│   └── chat_session.py         ChatSession
├── rag/
│   ├── vector_store.py         VectorStore
│   └── rag_pipeline.py         RagPipeline
└── app.py                      Streamlit UI only — no logic
```

**Do it incrementally.** Build one class, wire it into the running app, hand over the commit message and wait for Filip to commit, then move on. Do not rewrite everything and then try to make it start.

---

### 4.1 `config.py` — `AppConfig`  **[CORE]**

**Problem it solves:** today `config.py` defines values nobody reads, while the real values are scattered as literals across three files.

**What to write:** a frozen dataclass holding every tunable value in the system, created once in `app.py` and passed into each object's constructor.

```python
@dataclass(frozen=True)
class AppConfig:
    app_title: str = "DocuMind AI"
    app_icon: str = "🤖"
    user_avatar: str = "🧑"
    assistant_avatar: str = "🤖"

    available_models: tuple[str, ...] = ("llama3", "mistral", "phi3", "llava")
    default_model: str = "llama3"
    vision_model: str = "llava"
    embedding_model: str = "nomic-embed-text"

    chunk_size: int = 500
    chunk_overlap: int = 50
    retrieval_k: int = 4

    temperature: float = 0.7
    max_tokens: int = 512
    system_prompt: str = "..."

    ocr_language: str = "mkd+eng"
    ocr_min_confidence: float = 60.0

    index_dir: Path = Path(".faiss_index")
```

**Work to do:**
- [ ] Move `ANSWER_MODEL` out of `rag_chain.py`
- [ ] Move `EMBEDDING_MODEL` out of `vector_store.py`
- [ ] Move `chunk_size` / `chunk_overlap` out of `pdf_handler.py`
- [ ] Move `k=4` out of the retrieval function signature
- [ ] Make `temperature`, `max_tokens` and `system_prompt` actually reach Ollama — right now they are decorative

**Why not just import a module of constants (what you have now)?** Because a global import cannot be substituted in a test. Passing config as a constructor argument lets a test build an `AppConfig(chunk_size=50)` and assert on the result. That is the argument to make at the defence.

---

### 4.2 `documents/models.py` — value objects  **[CORE]**

Three small immutable classes. They replace the raw strings and dicts you pass around today, and they are what makes page-level provenance possible.

```python
@dataclass(frozen=True)
class ExtractedPage:
    number: int
    text: str
    used_ocr: bool
    ocr_confidence: float | None = None

@dataclass(frozen=True)
class Document:
    name: str
    pages: tuple[ExtractedPage, ...]

    @property
    def text(self) -> str: ...            # all pages joined
    @property
    def page_count(self) -> int: ...
    @property
    def ocr_page_count(self) -> int: ...   # how many pages needed OCR
    @property
    def is_empty(self) -> bool: ...

@dataclass(frozen=True)
class Chunk:
    text: str
    page_number: int
    source_document: str
```

**Why `Chunk` carries a page number:** it lets the app answer *"…according to page 7"*. That single feature gives you something concrete to demo, and it gives your evaluation chapter a measurable quantity (was the cited page the correct one?). Your current code throws this information away by concatenating everything into one string.

**Work to do:**
- [ ] Write the three dataclasses
- [ ] Track `used_ocr` per page — you will report this number in the evaluation

---

### 4.3 `documents/document_loader.py` — `DocumentLoader` (ABC)  **[CORE]**

**This is the single most important class in the thesis.** It is where abstraction, inheritance and polymorphism all land.

```python
class DocumentLoader(ABC):
    SUPPORTED_EXTENSIONS: tuple[str, ...] = ()

    def __init__(self, config: AppConfig, ocr_engine: OcrEngine | None = None):
        self._config = config
        self._ocr = ocr_engine

    @abstractmethod
    def _extract_pages(self, file) -> list[ExtractedPage]:
        """Subclass supplies only this."""

    def load(self, file) -> Document:
        """Template method: validate → extract → wrap → verify non-empty."""
        self._validate(file)
        pages = self._extract_pages(file)
        document = Document(name=file.name, pages=tuple(pages))
        if document.is_empty:
            raise EmptyDocumentError(file.name)
        return document

    @classmethod
    def supports(cls, filename: str) -> bool:
        return filename.lower().endswith(cls.SUPPORTED_EXTENSIONS)
```

**Note the shape:** `load()` is concrete and shared; `_extract_pages()` is abstract. That is the **Template Method pattern** — the base class owns the algorithm, subclasses fill in one step. Mention it by name; it is a second pattern for free.

**Work to do:**
- [ ] Write the ABC with `abstractmethod`
- [ ] Define `EmptyDocumentError` and `UnsupportedFileError` in a small `exceptions.py`
- [ ] Make sure `load()` is the only public method — subclasses never override it

---

### 4.4 The three loaders  **[CORE]**

**`PdfLoader`** — replaces `pdf_handler.extract_text_from_pdf()`

```python
class PdfLoader(DocumentLoader):
    SUPPORTED_EXTENSIONS = (".pdf",)

    def _extract_pages(self, file) -> list[ExtractedPage]:
        # for each page:
        #   text = page.extract_text()
        #   if text is None or too short → rasterise and send to self._ocr
        #   record used_ocr and confidence
```

This is where the OCR fallback lives, and it is the fix for your current silent failure on scanned PDFs.

**`ImageLoader`** — new

```python
class ImageLoader(DocumentLoader):
    SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
    # one ExtractedPage, always used_ocr=True
```

This is what makes an uploaded photo of a document *searchable* rather than just describable by LLaVA. It is the clearest demonstration of „препознавање на текст" in the whole project.

**`TextLoader`** — new, trivial

```python
class TextLoader(DocumentLoader):
    SUPPORTED_EXTENSIONS = (".txt", ".md")
```

**Why write `TextLoader` at all when it is three lines?** Because it proves the abstraction is real: three subclasses with completely different internals, one identical call site. A single subclass would not demonstrate polymorphism. Say exactly that if asked.

**Work to do:**
- [ ] `PdfLoader` with per-page OCR fallback
- [ ] `ImageLoader`
- [ ] `TextLoader` (handle encoding — try UTF-8, fall back to cp1251 for older Macedonian files)
- [ ] Delete `pdf_handler.py`

---

### 4.5 `documents/loader_factory.py` — `LoaderFactory`  **[OPTIONAL but cheap]**

```python
class LoaderFactory:
    def __init__(self, config: AppConfig, ocr_engine: OcrEngine):
        self._loaders = [PdfLoader(config, ocr_engine),
                         ImageLoader(config, ocr_engine),
                         TextLoader(config)]

    def for_file(self, filename: str) -> DocumentLoader:
        for loader in self._loaders:
            if loader.supports(filename):
                return loader
        raise UnsupportedFileError(filename)
```

Twelve lines, and it gives you the **Factory pattern** to name in the thesis. Without it the type decision leaks into `app.py` as an if-chain.

---

### 4.6 `documents/text_splitter.py` — `TextSplitter`  **[CORE]**

Wraps LangChain's `RecursiveCharacterTextSplitter` but works per page so provenance survives.

```python
class TextSplitter:
    def __init__(self, config: AppConfig): ...
    def split(self, document: Document) -> list[Chunk]:
        # split each page separately, tag each chunk with its page number
```

**Work to do:**
- [ ] Split per page, not on the concatenated string
- [ ] Return `Chunk` objects, not bare strings

---

### 4.7 `ocr/ocr_engine.py` — `OcrEngine`  **[CORE — Phase 2 depends on it]**

```python
@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float

class OcrEngine:
    def __init__(self, config: AppConfig): ...
    def is_available(self) -> bool: ...      # is the Tesseract binary installed?
    def recognise(self, image: Image.Image) -> OcrResult: ...
```

Get confidence from `pytesseract.image_to_data(..., output_type=Output.DICT)` and average the per-word confidences. You need that number twice: to warn the user in the UI when a scan is poor, and as a measured result in your evaluation chapter.

---

### 4.8 `llm/llm_provider.py` and `ollama_provider.py`  **[CORE]**

```python
class LLMProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...
    @abstractmethod
    def stream(self, prompt: str) -> Iterator[str]: ...
    @abstractmethod
    def stream_chat(self, messages: Sequence[Message]) -> Iterator[str]: ...
    @abstractmethod
    def stream_vision(self, image: bytes, prompt: str) -> Iterator[str]: ...
```

```python
class OllamaProvider(LLMProvider):
    def __init__(self, config: AppConfig, model_name: str | None = None): ...
```

**Work to do:**
- [ ] Move the JPEG conversion (`PIL` → `BytesIO`) out of `llm_chain.py` into `stream_vision`
- [ ] Actually pass `temperature` and `max_tokens` through in the Ollama `options` dict
- [ ] `is_available()` should catch a connection error and return False, so the UI can say "Ollama is not running" instead of crashing
- [ ] Delete `llm_chain.py`, the duplicate `import ollama`, and the unused `ChatOllama` import

**Why the ABC matters practically, not just for the title:** it lets you write a `FakeProvider` in your tests that returns a fixed answer. Without it, every test needs a running Ollama and a pulled model — which means, in practice, no tests. This is the strongest possible answer to *"why did you add an interface for one implementation?"*

---

### 4.9 `llm/prompt_builder.py` — `PromptBuilder`  **[OPTIONAL]**

Moves the RAG prompt string out of `rag_chain.py`. Small, but it makes the prompt independently testable and gives you a clean place to run prompt experiments for the evaluation chapter.

```python
class PromptBuilder:
    def __init__(self, config: AppConfig): ...
    def build_rag_prompt(self, chunks: Sequence[Chunk], question: str) -> str: ...
    def build_chat_prompt(self, messages: Sequence[Message]) -> str: ...
```

---

### 4.10 `chat/message.py` and `chat/chat_session.py`  **[CORE]**

```python
@dataclass(frozen=True)
class Message:
    role: str            # consider a Role enum instead of a bare string
    content: str
    timestamp: datetime
```

```python
class ChatSession:
    def __init__(self, system_prompt: str | None = None):
        self._messages: list[Message] = []
        self._system_prompt = system_prompt

    def add_user(self, content: str) -> None: ...
    def add_assistant(self, content: str) -> None: ...
    def clear(self) -> None: ...
    def export(self) -> str: ...

    @property
    def messages(self) -> tuple[Message, ...]:      # a copy, not the live list
        return tuple(self._messages)

    @property
    def is_empty(self) -> bool: ...
```

**This class is your encapsulation exhibit.** Note the deliberate details:

- `_messages` is private; nothing outside can `append` to it or reorder it
- the `messages` property returns a **tuple** — a caller cannot mutate your internal list through it
- `add_user` / `add_assistant` instead of one `add(role, content)` — an invalid role becomes impossible to express

Contrast that with `chat_history.py`, where any caller can hand you a list and any caller can mutate it afterwards. That before/after comparison is a full page of your thesis, and it is honest.

**Work to do:**
- [ ] Write `ChatSession`, delete `chat_history.py`
- [ ] Store the session in `st.session_state` as a single object rather than a raw list

---

### 4.11 `rag/vector_store.py` — `VectorStore`  **[CORE]**

```python
class VectorStore:
    def __init__(self, config: AppConfig): ...
    def build(self, chunks: Sequence[Chunk]) -> None: ...
    def search(self, question: str, k: int | None = None) -> list[Chunk]: ...
    def save(self, path: Path) -> None: ...
    @classmethod
    def load(cls, path: Path, config: AppConfig) -> "VectorStore": ...
    @property
    def is_ready(self) -> bool: ...
```

**Work to do:**
- [ ] Hide the FAISS index and the embeddings object behind these methods
- [ ] Return `Chunk` objects from `search()`, not a pre-joined string — joining is the pipeline's job, not the store's
- [ ] Store page metadata alongside each text so it survives the round-trip through FAISS
- [ ] Implement `save` / `load` so re-uploading the same PDF is instant (Phase 3)

---

### 4.12 `rag/rag_pipeline.py` — `RagPipeline`  **[CORE]**

The orchestrator. This class is where composition and dependency injection are visible in one screen.

```python
class RagPipeline:
    def __init__(self,
                 loader_factory: LoaderFactory,
                 splitter: TextSplitter,
                 vector_store: VectorStore,
                 provider: LLMProvider,
                 prompt_builder: PromptBuilder): ...

    def ingest(self, file) -> IngestReport: ...
    def ask(self, question: str) -> Iterator[str]: ...

    @property
    def last_sources(self) -> tuple[Chunk, ...]: ...
```

`IngestReport` is a small dataclass: page count, chunk count, how many pages needed OCR, mean OCR confidence, elapsed seconds. Show it in the UI after upload — and reuse the same numbers in your results chapter.

**Note every constructor argument is an abstraction or a small class, and none of them is created inside.** That is dependency injection, and it is why the pipeline is testable.

---

### 4.13 `app.py` — UI only  **[CORE]**

**Rule: after the refactor, `app.py` contains no `pdfplumber`, no `ollama`, no `faiss`, no prompt strings.** It builds the objects once, then calls methods.

```python
config = AppConfig()
ocr = OcrEngine(config)
pipeline = RagPipeline(LoaderFactory(config, ocr), TextSplitter(config),
                       VectorStore(config), OllamaProvider(config),
                       PromptBuilder(config))
```

**Work to do:**
- [ ] Strip all logic out of both tabs
- [ ] Guard the startup: if `provider.is_available()` is False, show a clear message instead of a traceback
- [ ] Show the `IngestReport` after upload
- [ ] Show cited page numbers under each answer

**Self-check when you are done:** if `app.py` still imports anything from `pdfplumber`, `ollama`, `langchain` or `faiss`, the refactor is not finished.

---

## 5. Phase 2 — Text recognition (OCR)  **[CORE]**

This earns the „препознавање на текст" half of the title.

- [ ] Install Tesseract (the binary, not just the Python package) and add `pytesseract` to `requirements.txt`. EasyOCR is the alternative — no binary needed, but slower and a large model download.
- [ ] Install the Cyrillic language data (`mkd`, and `srp`/`rus` as a fallback) — confirm with your mentor whether the demo must handle Macedonian
- [ ] Implement `OcrEngine.recognise()` returning text **and** confidence
- [ ] Wire the fallback into `PdfLoader`: a page whose `extract_text()` returns nothing (or fewer than ~20 characters) gets rasterised via `page.to_image(resolution=300)` and sent to OCR
- [ ] Wire `ImageLoader` to OCR uploaded images
- [ ] Preprocess before OCR — greyscale, and deskew if needed. Even a simple greyscale + threshold step measurably improves accuracy, and *measuring that improvement is a result you can put in a table*
- [ ] Surface low confidence in the UI: "Page 4 was recognised with 46% confidence — the answer may be unreliable"
- [ ] Handle Tesseract not being installed: `is_available()` False → the app still runs, OCR features are disabled with an explanation

**Demo to prepare for the defence:** upload a scanned Macedonian document, show the current version returning nothing, show the new version answering questions about it. That single comparison justifies the whole OCR chapter.

---

## 6. Phase 3 — Hardening  **[CORE]**

- [ ] Every value in `AppConfig`, injected everywhere — no literals left in the logic files
- [ ] `system_prompt` and `temperature` genuinely applied
- [ ] Error handling for: Ollama not running, model not pulled, corrupt PDF, password-protected PDF, empty document, unsupported file type, Tesseract missing
- [ ] A small exception hierarchy (`DocuMindError` → `EmptyDocumentError`, `UnsupportedFileError`, `ProviderUnavailableError`) — this is also inheritance, and worth one paragraph in the OOP chapter
- [ ] Persist the FAISS index to `config.index_dir`, keyed by a hash of the file, so a repeat upload skips embedding
- [ ] `.gitignore` the index directory
- [ ] Multi-document support **[OPTIONAL]** — the `Chunk.source_document` field is already there for it

---

## 7. Phase 4 — Tests and evaluation  **[CORE]**

### 7.1 Unit tests (pytest)

Target the classes, never the Streamlit UI.

- [ ] `ChatSession`: add/clear/export; that `messages` returns a copy and mutating it does not affect the session
- [ ] `TextSplitter`: chunk count for known input, overlap is exactly `chunk_overlap`, page numbers preserved
- [ ] `TextLoader`: UTF-8 and cp1251 files
- [ ] `PdfLoader`: a text PDF uses no OCR; a scanned PDF sets `used_ocr=True` (mock `OcrEngine`)
- [ ] `LoaderFactory`: right loader per extension; raises on `.docx`
- [ ] `DocumentLoader`: raises `EmptyDocumentError` on a blank document
- [ ] `PromptBuilder`: context and question both appear in the output
- [ ] `RagPipeline`: end-to-end with a `FakeProvider` and an in-memory store

**Write `FakeProvider` early.** It is the class that makes the whole suite possible without Ollama, and it is the concrete proof that the `LLMProvider` abstraction was worth adding.

### 7.2 Evaluation — the results chapter

This is the part I cannot do for you and the part that turns a project into a thesis.

- [ ] Assemble 5–10 documents: some native-text PDFs, some scanned, ideally some Macedonian
- [ ] Write 20–30 questions with known correct answers, and note which page each answer is on
- [ ] Measure and tabulate:

| Metric | How to compute |
|---|---|
| Retrieval accuracy | Is the correct page among the top-k retrieved chunks? Report as a percentage |
| Answer correctness | Score each answer manually (correct / partially correct / wrong / refused) — manual scoring is acceptable, just state the method |
| OCR accuracy | Character Error Rate against a hand-typed ground truth for 3–5 scanned pages |
| Latency per stage | Time extraction, OCR, embedding, retrieval and generation separately |

- [ ] Run at least one comparison so you have something to *discuss*, not just report:
  - chunk size 500 vs 1000 vs 1500 → effect on retrieval accuracy
  - k = 2 vs 4 vs 8 → accuracy against latency
  - OCR with and without greyscale preprocessing → effect on CER
- [ ] Turn each comparison into a graph. Graphs are what get discussed at a defence.

---

## 8. Phase 5 — Thesis documentation  **[CORE]**

- [ ] **UML class diagram** — the centrepiece. Show the two ABCs with their subclasses, and `RagPipeline`'s composition arrows. Generate it from the code with `pyreverse` (part of pylint) and then tidy it by hand, so it cannot drift from reality
- [ ] **Use case diagram** — upload document, ask a question about it, analyse an image, chat freely, switch model, export chat
- [ ] **Sequence diagram** — one question through the pipeline: `app` → `RagPipeline.ask` → `VectorStore.search` → `PromptBuilder` → `OllamaProvider.stream` → back to the UI
- [ ] **Component / data-flow diagram** of the ingestion pipeline including the OCR branch
- [ ] One section per row of the table in §3, each naming a specific class in your code
- [ ] A before/after section: `chat_history.py` versus `ChatSession`. Honest, concrete, and it shows you understand *why*, not just *how*
- [ ] Screenshots: the chat tab, a PDF answer with a cited page number, a scanned document being OCR'd
- [ ] Rewrite the README to match the final architecture
- [ ] Add `docs/` to the repo with the diagram sources

---

## 9. Ask your mentor before you start

1. **Does the thesis need a novel contribution, or is an implementation-based thesis acceptable?** This decides how heavy Phase 4 has to be.
2. **Which diagrams are required** — class + use case + sequence, or a specific set?
3. **Is manual scoring acceptable for answer correctness**, or is an automated metric expected?
4. **Must the OCR work on Macedonian (Cyrillic)?** It changes the language pack and the whole test set — confirm early.
5. **Is Streamlit acceptable as the UI**, or is a conventional web framework expected?
6. **Is the [OPTIONAL] work worth doing** (page citations, multi-document, persistence), or should that time go into the evaluation chapter?

---

## 10. Order of work

1. **Phase 1** — the OOP refactor. Biggest gap; unlocks tests and every diagram.
2. **Phase 2** — OCR. Closes the second title gap.
3. **Phase 3** — hardening. Removes the easy criticisms.
4. **Phase 4** — tests and evaluation. Turns a project into a thesis.
5. **Phase 5** — diagrams and writing. Only possible once 1 and 2 are done.

Inside Phase 1, a safe build order: `AppConfig` → `models.py` → `ChatSession` (small, self-contained, immediately replaces a whole file) → `LLMProvider` + `OllamaProvider` → `DocumentLoader` + the three subclasses → `TextSplitter` → `VectorStore` → `RagPipeline` → strip `app.py` last.

One class, one commit. The agent writes you the commit message; **you** make every commit yourself (§11.3). That history is part of what gets judged.

---

## 11. Instructions for the coding agent

This section is the working agreement you hand to the agent along with the document. Sections 1–10 describe *what* to build; this section describes *how to work*.

### 11.0 Three rules before anything else

1. **One phase per session.** Not the whole document in one run. You need to read and understand Phase 1 before Phase 2 is built on top of it.
2. **Work on a branch.** `git checkout -b refactor/oop` before Phase 1 starts. If a phase goes wrong you throw the branch away, not the project.
3. **You review between phases.** The agent stops at every phase boundary and waits. If it runs straight from Phase 1 into Phase 2, stop it.

---

### 11.1 Preconditions — do this yourself, before the agent starts

The agent cannot verify anything it writes unless the environment exists first. Every item here has a verification command; do not start until all of them pass.

**Repository and Python**

```
git clone https://github.com/fdavchev/DocuMind-AI
cd DocuMind-AI
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
git checkout -b refactor/oop
```

**Ollama with the three models**

```
ollama serve
ollama pull llama3
ollama pull llava
ollama pull nomic-embed-text
ollama list          → all three must appear
```

Without `nomic-embed-text` nothing in the RAG path can be tested. Without `llava` the vision tab is dead.

**Tesseract — the binary, not just the Python package**

- Windows: install the UB Mannheim build, tick the additional language data during setup
- Add the install directory to `PATH`

```
tesseract --version       → must print a version
tesseract --list-langs    → must include eng, and mkd if you need Macedonian
pip install pytesseract
```

`pip install pytesseract` alone does nothing — it is a wrapper around a binary that must be installed separately. This is the single most common way Phase 2 stalls.

**Sample files — create a `samples/` folder with all four**

| File | What it must be | Which code path it proves |
|---|---|---|
| `samples/text.pdf` | A normal PDF with a real text layer | `PdfLoader` happy path, no OCR |
| `samples/scanned.pdf` | An image-only PDF (scan or print-to-PDF of photos) | The OCR fallback — **the whole point of Phase 2** |
| `samples/photo.jpg` | A phone photo of a printed page | `ImageLoader` |
| `samples/notes.txt` | Plain text, ideally one UTF-8 and one cp1251 | `TextLoader` encoding handling |

**Without `scanned.pdf` the agent cannot prove the OCR fallback works, and Phase 2 is unverifiable.** Make this one first.

**Baseline check — run the app as it is today**

```
streamlit run app.py
```

Upload `scanned.pdf` and ask a question. It will fail to answer. **Screenshot this.** It is your before/after evidence for the defence, and it disappears the moment Phase 2 lands.

---

### 11.2 The kickoff prompt — paste this verbatim

**Phase 1:**

```text
Read C:\Users\Filip Davchev\Desktop\project-report-2.md in full before doing anything.

Context: this is the codebase for my diploma thesis. I will be defending it orally, so
I have to be able to explain every class you write. Clarity beats cleverness everywhere.

Your task this session is PHASE 1 ONLY — the OOP refactor described in section 4.
Do not start Phase 2, 3, 4 or 5. Stop when Phase 1 is done.

Build in the order given at the end of section 10:
AppConfig → models.py → ChatSession → LLMProvider + OllamaProvider →
DocumentLoader + PdfLoader/ImageLoader/TextLoader → TextSplitter →
VectorStore → RagPipeline → strip app.py last.

Rules:
- One class at a time. After each class: run `streamlit run app.py`, confirm the app
  still starts, then STOP and give me a one-line commit message in English naming the
  class and the file it replaced. Then wait for me.
- YOU NEVER COMMIT. I make every commit myself. Do not run `git add`, `git commit`,
  `git checkout`, `git reset`, `git branch`, `git merge` or any other git command that
  changes the repository. Reading with `git log` / `git status` / `git diff` is fine.
  Your only involvement in git is writing the commit message text and handing it to me.
- Never batch. One class, one message, then stop and wait. Do not write the next class
  until I tell you the commit is done.
- Build only what section 4 specifies. Do not add features, caching, logging,
  async or abstractions that are not in the document.
- Anything tagged [OPTIONAL] in the document: ask me before building it. Do not decide.
- Anything listed in section 9 (mentor questions): ask me. Do not guess.
- After each class, write me 3-5 plain sentences: what it does, why it is designed that
  way, and which OO principle it demonstrates. Collect these in docs/class-notes.md.
  This is my study material for the defence, so write it for someone who has not seen
  the code.
- Do not write code comments explaining what a line does. Only comment a genuinely
  non-obvious decision.
- Do not touch section 7.2 (evaluation) or section 8 (thesis writing). Those are mine.
- Do not change git branch state. If you need a branch, tell me and wait.

When Phase 1 is complete, run the section 11.5 Phase 1 checks, report the results,
and stop.
```

**Phase 2 (a new session, after you have reviewed Phase 1):**

```text
Read C:\Users\Filip Davchev\Desktop\project-report-2.md in full.
Phase 1 is complete and merged. Your task this session is PHASE 2 ONLY — the OCR work
in section 5. Same rules as before (section 11.3 of the document).

Tesseract is installed and `samples/scanned.pdf` exists. Verify the OCR fallback with
that file specifically: before your change the app returns nothing for it, after your
change it must answer questions about its contents. Show me that comparison.

Ask me before choosing OCR languages or confidence thresholds. Stop when Phase 2 is done.
```

**Phase 3 and Phase 4** follow the same shape — name the phase, name the section, repeat the rules reference, state the stop condition.

---

### 11.3 Working rules for the agent

1. **One class per commit — and the agent never commits.** After each class it stops and hands you a one-line commit message **in English**, naming the class and the file it replaced: `Add ChatSession, replacing chat_history.py`. **You** run `git add` and `git commit`. The agent runs no git command that changes the repository — no `add`, no `commit`, no `checkout`, no `reset`, no branching or merging. Reading history (`git log`, `git status`, `git diff`) is fine. Your commit history is read at the defence as evidence the work was incremental and yours, so it should be made by you.
2. **Run the app after every class.** A refactor that only compiles is not verified. `streamlit run app.py` must still start.
3. **Never batch.** One class → one commit message → stop and wait for you to commit → next class. If it has written five classes before handing you the first message, stop it; do not try to reconstruct which change belonged to which class after the fact.
4. **Build only what §4 specifies.** No extra caching, logging, async, config layers, plugin systems or "while I was in there" improvements. Scope creep in a thesis codebase means classes you cannot justify, and an unjustifiable class is worse than no class.
5. **No explanatory code comments.** The explanation goes in `docs/class-notes.md`, not inline. Comment only a decision that is genuinely non-obvious.
6. **Write `docs/class-notes.md` as it goes** — 3–5 sentences per class, in plain language. This is the single highest-value instruction in this section: it is your defence preparation and the raw material for the OOP chapter in §8, and it costs the agent almost nothing.
7. **Ask, do not guess.** Rules in 11.4.
8. **Delete the old file when its replacement works.** `chat_history.py`, `pdf_handler.py`, `llm_chain.py`, `rag_chain.py` should all be gone by the end of Phase 1. Leaving both versions in the repo is how you end up defending dead code.
9. **Stop at the phase boundary and wait.**

---

### 11.4 Decisions the agent must bring back to you

It must **ask**, never decide, on:

- Every **[OPTIONAL]** item: `LoaderFactory`, `PromptBuilder`, page-number citations, multi-document support, FAISS persistence
- Everything in **§9** that your mentor has not answered yet
- **OCR language set** — `eng` only, or `mkd+eng`
- **Any threshold**: the character count that triggers OCR fallback, the confidence level that triggers a UI warning, chunk size, `k`
- **Anything in §4 that turns out to be wrong or impossible.** The plan is mine, not gospel — if the agent finds a real problem with a design, it should say so and wait, not silently substitute its own.
- **Renaming or restructuring beyond §4.0.** The class diagram in your thesis has to match the code; unplanned renames mean redrawing it.

Add this line to the prompt if the agent starts deciding on its own: *"You made a decision that was mine. List every decision you made without asking, and we will go through them."*

---

### 11.5 Definition of done — run these before accepting a phase

**Phase 1 — the OOP refactor**

```
grep -nE "pdfplumber|ollama|faiss|langchain" app.py     → must return NOTHING
grep -rn "^class " documind/ | wc -l                    → 12+ classes
grep -rn "ABC|abstractmethod" documind/                 → at least 2 ABCs
streamlit run app.py                                    → app starts
```

- [ ] Chat tab works: send a message, get a streamed reply
- [ ] PDF tab works: upload `samples/text.pdf`, ask a question, get a grounded answer
- [ ] Image works: upload `samples/photo.jpg`, LLaVA describes it
- [ ] Model switching still works
- [ ] Export chat still works
- [ ] `chat_history.py`, `pdf_handler.py`, `llm_chain.py`, `rag_chain.py` are **deleted**
- [ ] `git log --oneline` shows roughly one commit per class, not one big commit
- [ ] `docs/class-notes.md` exists and covers every class

**Phase 2 — OCR**

- [ ] `samples/scanned.pdf` — previously returned nothing, now answers questions correctly
- [ ] `samples/photo.jpg` — text in the photo is now *searchable*, not just described
- [ ] `samples/text.pdf` — still does **not** trigger OCR (check `used_ocr` is False; if a native-text PDF is running OCR, the fallback condition is wrong)
- [ ] Uninstall/rename Tesseract temporarily → app still starts and explains OCR is unavailable
- [ ] OCR confidence appears in the UI

**Phase 3 — hardening**

- [ ] Stop Ollama → app shows a clear message, no traceback
- [ ] Upload a corrupt or password-protected PDF → clear message, no traceback
- [ ] Upload a `.docx` → "unsupported file type", no traceback
- [ ] Re-upload the same PDF → noticeably faster (index reused)
- [ ] `grep -rnE "\"llama3\"|nomic-embed-text|500|0\.7" documind/ --include=*.py` finds these only in `config.py`

**Phase 4 — tests**

```
pytest -v          → all green
pytest --cov=documind
```

- [ ] The suite runs with **Ollama stopped** (proves `FakeProvider` and the ABC are doing their job)
- [ ] Every class in §4 has at least one test

---

### 11.6 Explicitly out of scope for the agent

State this in the prompt every time:

- **§7.2 — the evaluation numbers.** Retrieval accuracy, answer correctness, CER, latency. These require your documents, your questions and runs on your hardware. An agent asked for them will produce plausible-looking numbers that are fabricated. That is the most dangerous possible failure in a thesis. **Never let it fill in that table.**
- **§8 — the thesis text.** Chapters, argumentation, conclusions. `docs/class-notes.md` is raw material for you to write from, not the chapter.
- **Anything depending on your mentor's answers** until you have them.
- **Every git operation that changes the repository.** No `git add`, `git commit`, `git checkout`, `git branch`, `git merge`, `git reset`, `git stash`. **You make every commit yourself.** The agent's entire git involvement is writing you the commit message text; if it needs a branch it says which one and waits. Reading history (`git log`, `git status`, `git diff`) is allowed.

---

### 11.7 When it goes wrong

| Symptom | What to do |
|---|---|
| The app will not start after a class | **You** run `git checkout -- .` back to the last good commit, then have the agent redo that one class. This is why one commit per class matters. |
| It wrote several classes before handing you a single commit message | Do not try to reconstruct which change belonged to which class. Reset to the last good commit yourself and restate rules 11.3.1 and 11.3.3. |
| It ran a git command itself | Check `git log` and `git status` to see what it changed, undo it yourself, and restate §11.6. Your commit history has to be yours. |
| It invented features not in §4 | Have it list every addition, then remove them. Unjustifiable classes are a defence liability. |
| It filled in evaluation numbers | Delete them immediately and re-read §11.6 to it. Verify no fabricated figure survives anywhere. |
| It is rewriting §4 as it goes | Stop. Have it list its disagreements. Decide yourself which are real. |
| A whole phase went bad | Delete the branch, start the phase again with a tightened prompt. Cheaper than untangling it. |

---

### 11.8 Your review checklist after each phase

Before merging the branch:

- [ ] Read `docs/class-notes.md` end to end. **Anything you cannot explain in your own words, ask the agent to explain again** — this is exactly the defence, rehearsed early.
- [ ] Read every class the agent wrote. Not skim — read.
- [ ] For each class, answer out loud: *why does this exist, and what breaks without it?* Any class where you cannot answer either gets removed, or you learn it properly now.
- [ ] `git log --oneline` — does the history tell a coherent story?
- [ ] Run the §11.5 checks yourself. Do not take the agent's word that they passed.
- [ ] Only then merge to `main`.

**The point of the whole arrangement:** the agent does the typing, you keep the understanding. A thesis you cannot defend is worth nothing regardless of how good the code is.
