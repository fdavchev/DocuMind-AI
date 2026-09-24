# 🤖 DocuMind AI

> A **100% local, privacy-first AI assistant** — chat with your documents and images without a single byte leaving your machine.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.58-red?logo=streamlit)
![LangChain](https://img.shields.io/badge/LangChain-1.3-green)
![Ollama](https://img.shields.io/badge/Ollama-local-orange)
![FAISS](https://img.shields.io/badge/FAISS-vector--search-blueviolet)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## 📽️ Demo

<!-- After recording your demo, replace the line below with your actual GIF or video embed -->
> 🎬 *Demo video coming soon*

---

## ✨ Features

- 📄 **PDF Q&A** — upload PDFs and ask questions about their content using a full RAG pipeline
- 📚 **Multi-document search** — load several PDFs into one index and ask across all of them
- 🔖 **Source citations** — every answer cites the file and page it came from, with the passages listed underneath
- 💬 **Conversational AI** — multi-turn chat with full memory of the conversation
- 🖼️ **Vision support** — upload an image and ask questions about it (powered by LLaVA)
- 🔄 **Model switching** — swap between `llama3`, `mistral`, `phi3`, and `llava` at runtime
- 💾 **Save & export** — download the full chat history as a `.txt` file
- 🔒 **100% local** — zero API keys, zero cloud calls, zero data leakage
- ⚡ **Streaming responses** — token-by-token output just like ChatGPT
- 🐳 **One-command setup** — `docker compose up` starts the app, starts Ollama, and pulls the models
- 🔍 **OCR fallback** — scanned PDFs are read with Tesseract when it's installed, and degrade to a clear message when it isn't
- 🛟 **Readable failures** — Ollama down, model not pulled, oversized or corrupt PDF all produce an actionable message, never a traceback

---

## 🧠 How It Works

The app has two modes, chosen with the selector at the top of the page.

### 🤖 Chat mode (image + text)

```
User Input
    │
    ▼
Streamlit UI  ──►  LangChain  ──►  Ollama (local LLM / LLaVA)
    │                                         │
    │◄──────────── Streamed Response ─────────┘
    ▼
Chat History  ──►  Export to .txt
```

### 📄 PDF Q&A mode (RAG pipeline)

```
PDF Upload (one or many)        RagPipeline.ingest(file)
    │
    ▼
Extract Text page by page      (pdfplumber)      → LoaderFactory → PdfLoader
    │
    ▼
Split each page into Chunks    (LangChain RecursiveCharacterTextSplitter)
    │                           each chunk tagged {source: file.pdf, page: n}
    │                                             → TextSplitter
    ▼
Embed Chunks                   (nomic-embed-text-v2-moe via Ollama)
    │                                             → VectorStore
    ▼
Store in FAISS                 (local vector database, all PDFs in one index)
    │
    ▼
User asks a question            RagPipeline.ask(question)
    │
    ▼
Embed question  ──►  Search FAISS for similar chunks (across every loaded PDF)
    │                                             → VectorStore.search
    ▼
[Numbered passages + their file/page + Question]  ──►  llama3 (Ollama)
    │                                             → OllamaProvider.stream_answer
    ▼
Streamed answer with inline [n] citations  +  a Sources list showing
"report.pdf, p. 4" for each passage the model was given
```

`app.py` calls exactly two of those boxes — `ingest` and `ask`. Everything
between them is the pipeline's own business, which is why the UI file names no
PDF, vector or model library at all.

**RAG** stands for **Retrieval Augmented Generation** — instead of asking the LLM to rely on its training data, we inject the relevant pages of *your* document into the prompt. The answer is always grounded in your actual file.

**Why split page by page?** A chunk assembled across a page boundary can't be cited honestly. Splitting each page on its own guarantees every chunk belongs to exactly one page, so a "p. 4" reference is always accurate.

---

## 🗂️ Project Structure

```
DocuMind-AI/
├── app.py              # Streamlit UI only — widgets plus calls on the objects below
├── ocr.py              # Optional Tesseract fallback for scanned pages
├── errors.py           # Failure translation + pre-flight checks (no tracebacks in the UI)
├── config.py           # UI vocabulary only: mode names and avatars
├── documind/           # The object-oriented core — the whole pipeline lives here
│   ├── config.py           # AppConfig — every tunable setting in one frozen object
│   ├── documents/          # Document value objects + DocumentLoader, PdfLoader, TextLoader, LoaderFactory, TextSplitter
│   ├── chat/               # Message + ChatSession — the conversation and its export
│   ├── llm/                # LLMProvider + OllamaProvider — every call to the model
│   └── rag/                # VectorStore — chunks in, cited chunks out; RagPipeline — upload in, cited answer out
├── tests/              # pytest suite — runs offline, no Ollama required
│   ├── conftest.py         # in-memory PDF builder + deterministic fake embeddings
│   ├── test_document_loader.py # the loaders: one load(), two file types
│   ├── test_loader_factory.py # picking the loader for a filename
│   ├── test_text_splitter.py # page-by-page chunking and the page-boundary rule
│   ├── test_rag_vector_store.py # the VectorStore class: indexing and the Chunk round trip
│   ├── test_rag_pipeline.py # the RagPipeline class: ingest, ask, citations, sources
│   ├── test_integration.py # PDF bytes → answer through the real object graph, Ollama stubbed
│   ├── test_errors.py      # failure paths: Ollama down, model missing, bad PDF
│   ├── test_ocr.py         # scanned-page detection and the OCR fallback
│   ├── test_chat_session.py# conversation state, export format, encapsulation
│   ├── test_ollama_provider.py # the model calls, with Ollama faked
│   └── test_app_smoke.py   # app.py actually starts, with and without Ollama
├── docs/architecture.md# Architecture chapter draft (components, pipeline, limitations)
├── DECISIONS.md        # Running log of design decisions and their rationale
├── Dockerfile          # App image (Python + Streamlit)
├── docker-compose.yml  # App + Ollama + one-shot model pull
├── requirements.txt    # Pinned Python dependencies
└── requirements-dev.txt# Test-only dependencies (pytest)
```

---

## 🚀 Getting Started

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10+ | [python.org](https://python.org) |
| Ollama | Latest | [ollama.com](https://ollama.com) |

### Option A — Docker (one command)

```bash
git clone https://github.com/fdavchev/DocuMind-AI.git
cd DocuMind-AI
docker compose up
```

That's the whole setup. Compose starts Ollama, pulls `llama3`,
`nomic-embed-text-v2-moe` and `llava` into a cached volume, waits until they're
actually present, then serves the app at
[http://localhost:8501](http://localhost:8501).

The first run downloads roughly 6 GB of model weights and takes a while; every
run after that reuses the volume and starts in seconds. Models run on CPU by
default — uncomment the `deploy:` block under the `ollama` service in
`docker-compose.yml` to use an NVIDIA GPU.

> Docker is the only prerequisite for this path — no Python, no virtualenv, no
> local Ollama install. Everything still runs on your machine; the only network
> traffic is downloading the model weights.

---

### Option B — Local Python install

#### 1 — Clone the repo

```bash
git clone https://github.com/fdavchev/DocuMind-AI.git
cd DocuMind-AI
```

#### 2 — Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

#### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

#### 4 — (Optional) Install Tesseract for scanned PDFs

Only needed if you want to read scanned, image-only PDFs. Text-based PDFs work
without it, and the app says so clearly rather than failing.

```bash
# Windows
winget install UB-Mannheim.TesseractOCR

# macOS
brew install tesseract

# Linux
sudo apt install tesseract-ocr
```

The Docker image installs Tesseract already — nothing to do there.

#### 5 — Pull the models with Ollama

```bash
# For the Chat tab
ollama pull llava        # vision + text chat
ollama pull mistral      # alternative text model

# For the PDF Q&A tab (both required)
ollama pull llama3             # answers questions about the document
ollama pull nomic-embed-text-v2-moe   # converts text to vectors for FAISS
```

> **Why two models for PDF Q&A?**
> `nomic-embed-text-v2-moe` is a small, multilingual model (English and Macedonian alike) whose only job is turning text into numbers (vectors) so FAISS can search by similarity. `llama3` is the model that actually reads the retrieved chunks and writes the answer.

#### 6 — Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser. No API key needed.

---

## 🛟 When Something Goes Wrong

The app never shows a Python traceback. Each common failure path is caught and
translated into a message that names the problem *and* the fix:

| What happened | What you see |
|---------------|--------------|
| Ollama isn't running | *"Ollama isn't running… start it with `ollama serve`"* |
| A model isn't pulled | *"The model `llama3` isn't installed… `ollama pull llama3`"* |
| PDF over 25 MB | *"…over the 25 MB limit"* — refused before parsing, so you aren't left watching a spinner |
| Corrupt / password-protected file | *"…appears to be corrupt, password-protected, or not a PDF"* |
| Nothing readable in the file (scanned with no Tesseract, OCR found nothing, or genuinely blank) | *"Nothing could be read from `scan.pdf` — every page came back empty"*, with the reminder that a scanned document needs OCR to be available |
| Scanned PDF over 50 pages | *"…over the 50-page limit"* — refused rather than starting a ten-minute OCR pass |
| A file type no loader handles | *"…isn't a file type this app can read"*, naming the formats that would have worked |
| A question asked before anything is indexed | *"There is nothing to search yet"* — the input is disabled until a document is indexed, so this is the belt to that braces |

Both tabs show a **System check** panel that verifies Ollama is reachable and
the required models are installed *before* you upload anything, with a re-check
button for once you've fixed it. The same panel reports whether OCR is available
and prints the install command for your platform when it isn't. In a batch
upload, one bad file is skipped with its own message while the rest still index.

The translation lives in `errors.py` and is unit-tested, so the UI carries no
knowledge of what an `httpx.ConnectError` means.

---

## 🧪 Running the Tests

The suite runs entirely offline — embeddings are replaced with a deterministic
stand-in and Ollama is stubbed, so no model needs to be pulled and no server
needs to be running. That also makes it CI-safe. It includes a smoke test that
boots `app.py` through Streamlit's own script runner, so a broken import or a
startup crash fails the build rather than the demo.

```bash
pip install -r requirements-dev.txt
pytest
```

| File | Covers |
|------|--------|
| `test_document_loader.py` | The loader contract: one `load()` shared by `PdfLoader` and `TextLoader`, page-accurate extraction |
| `test_loader_factory.py` | Dispatch by extension, unsupported-file refusal, registering a new loader |
| `test_text_splitter.py` | Page-by-page chunking, configured chunk size, no chunk across a page boundary |
| `test_rag_vector_store.py` | The `VectorStore` class: `Chunk` → FAISS → `Chunk`, retrieval width, indexed sources |
| `test_rag_pipeline.py` | The `RagPipeline` class: ingest reports, retrieval → prompt → streamed answer, cited sources |
| `test_chat_session.py` | Conversation state, export format, encapsulation of the message list |
| `test_ollama_provider.py` | Every model call: chat, vision and document answers, with Ollama faked |
| `test_integration.py` | Full pipeline through the real object graph: PDF bytes → chunks → FAISS → prompt → answer |
| `test_errors.py` | Failure translation, pre-flight checks, upload validation |
| `test_ocr.py` | Scanned-page detection, OCR fallback, graceful degradation without Tesseract |
| `test_app_smoke.py` | Runs `app.py` through Streamlit's script runner — catches broken imports and startup crashes |

---

## ⚙️ Configuration

All settings live in the `AppConfig` class in `documind/config.py`. `app.py` builds one
`AppConfig()` at startup and passes it to every step of the pipeline:

| Setting | Default | Description |
|---------|---------|-------------|
| `default_model` | `llava` | Model loaded on startup in Chat mode |
| `available_models` | `(llama3, mistral, phi3, llava)` | Models shown in the sidebar dropdown |
| `vision_model` | `llava` | Model used when an image is attached |
| `answer_model` | `llama3` | Model that answers PDF questions |
| `embedding_model` | `nomic-embed-text-v2-moe` | Model that turns chunks into vectors |
| `chunk_size` / `chunk_overlap` | `500` / `50` | How PDF pages are split for indexing |
| `retrieval_k` / `retrieval_k_multi_document` | `4` / `6` | Chunks retrieved per question |
| `temperature` | `0.7` | Creativity (0 = deterministic, 1 = creative) |
| `max_tokens` | `512` | Max response length |
| `system_prompt` | See file | Personality/instruction prompt for the assistant |
| `max_ocr_pages` | `50` | Scanned pages OCR will attempt before refusing the file |

---

## 🖼️ Supported Models

| Model | Type | Used In |
|-------|------|---------|
| `llava` | Vision + Text | Chat tab — image understanding |
| `llama3` | Text | PDF Q&A tab — document answering |
| `mistral` | Text | Chat tab — fast general responses |
| `phi3` | Text | Chat tab — lightweight, low RAM |
| `nomic-embed-text-v2-moe` | Embeddings only | PDF Q&A tab — FAISS indexing |

---

## 📋 Key Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit==1.58.0` | Web UI |
| `langchain==1.3.4` | LLM orchestration & text splitting |
| `langchain-ollama==1.1.0` | Ollama integration for LangChain |
| `langchain-community==0.4.2` | FAISS vector store wrapper |
| `ollama==0.6.2` | Direct Ollama API client |
| `faiss-cpu` | Local vector similarity search |
| `pdfplumber` | PDF text extraction (page by page) |
| `pytesseract` | OCR for scanned PDFs (optional — needs the Tesseract binary) |
| `pytest` | Test suite (dev only — see `requirements-dev.txt`) |
| `pillow==12.2.0` | Image handling |

See `requirements.txt` for the full pinned list.

---


## 🔮 Roadmap

- [x] Local chat with text LLMs (Mistral, Llama3, Phi3)
- [x] Image Q&A with LLaVA
- [x] PDF Q&A with RAG pipeline (FAISS + nomic-embed-text-v2-moe + llama3)
- [x] Multi-document support (query across several PDFs at once)
- [x] Source citation with page number references
- [x] Automated test suite (pytest, runs without a live model)
- [x] Docker container for one-command setup
- [x] Graceful error handling for the common failure paths
- [x] Support for scanned PDFs via OCR (optional — needs Tesseract installed)

---

## 📚 Project Documentation

| Document | What's in it |
|----------|--------------|
| [`docs/project-report.md`](docs/project-report.md) | What was built phase by phase, what is verified and how, measured performance, environment gotchas, and a step-by-step manual testing guide |
| [`docs/architecture.md`](docs/architecture.md) | How the system fits together: components, the RAG pipeline, error-handling design, testing strategy, deployment, and known limitations |
| [`DECISIONS.md`](DECISIONS.md) | Every non-obvious engineering choice, with the alternatives considered and why each was rejected |

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## 📄 License

[MIT](LICENSE)

---

> Built using Streamlit + LangChain + FAISS + Ollama — running 100% locally 🔒
