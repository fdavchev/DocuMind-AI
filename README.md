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

---

## 🧠 How It Works

The app has two modes, accessible via tabs in the UI.

### Tab 1 — 🤖 Chat (image + text)

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

### Tab 2 — 📄 PDF Q&A (RAG pipeline)

```
PDF Upload (one or many)
    │
    ▼
Extract Text page by page      (pdfplumber)
    │
    ▼
Split each page into Chunks    (LangChain RecursiveCharacterTextSplitter)
    │                           each chunk tagged {source: file.pdf, page: n}
    ▼
Embed Chunks                   (nomic-embed-text via Ollama)
    │
    ▼
Store in FAISS                 (local vector database, all PDFs in one index)
    │
    ▼
User asks a question
    │
    ▼
Embed question  ──►  Search FAISS for similar chunks (across every loaded PDF)
    │
    ▼
[Numbered passages + their file/page + Question]  ──►  llama3 (Ollama)
    │
    ▼
Streamed answer with inline [n] citations  +  a Sources list showing
"report.pdf, p. 4" for each passage the model was given
```

**RAG** stands for **Retrieval Augmented Generation** — instead of asking the LLM to rely on its training data, we inject the relevant pages of *your* document into the prompt. The answer is always grounded in your actual file.

**Why split page by page?** A chunk assembled across a page boundary can't be cited honestly. Splitting each page on its own guarantees every chunk belongs to exactly one page, so a "p. 4" reference is always accurate.

---

## 🗂️ Project Structure

```
DocuMind-AI/
├── app.py              # Streamlit UI — two tabs, sidebar, chat loops
├── pdf_handler.py      # Per-page PDF extraction + chunking with page metadata
├── vector_store.py     # Embed chunks with nomic-embed-text, store & search FAISS
├── rag_chain.py        # Build the cited RAG prompt, stream answer from llama3
├── llm_chain.py        # LangChain logic for the chat tab (text + vision)
├── chat_history.py     # In-memory conversation history management & export
├── config.py           # All tunable settings (models, prompts, UI labels)
├── tests/              # pytest suite — runs offline, no Ollama required
│   ├── conftest.py         # in-memory PDF builder + deterministic fake embeddings
│   ├── test_pdf_handler.py # extraction, chunking, page metadata
│   ├── test_vector_store.py# embedding, retrieval, multi-document indexing
│   ├── test_rag_chain.py   # prompt construction and citation rendering
│   └── test_integration.py # PDF bytes → answer, with Ollama stubbed
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

### 1 — Clone the repo

```bash
git clone https://github.com/fdavchev/DocuMind-AI.git
cd DocuMind-AI
```

### 2 — Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — Pull the models with Ollama

```bash
# For the Chat tab
ollama pull llava        # vision + text chat
ollama pull mistral      # alternative text model

# For the PDF Q&A tab (both required)
ollama pull llama3             # answers questions about the document
ollama pull nomic-embed-text   # converts text to vectors for FAISS
```

> **Why two models for PDF Q&A?**
> `nomic-embed-text` is a tiny, fast model whose only job is turning text into numbers (vectors) so FAISS can search by similarity. `llama3` is the model that actually reads the retrieved chunks and writes the answer.

### 5 — Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser. No API key needed.

---

## 🧪 Running the Tests

The suite runs entirely offline — embeddings are replaced with a deterministic
stand-in and Ollama is stubbed, so no model needs to be pulled and no server
needs to be running. That also makes it CI-safe.

```bash
pip install -r requirements-dev.txt
pytest
```

| File | Covers |
|------|--------|
| `test_pdf_handler.py` | Page-accurate extraction, chunking, empty/scanned-page handling |
| `test_vector_store.py` | FAISS indexing, metadata survival, multi-document retrieval |
| `test_rag_chain.py` | Citation formatting, prompt rules, streaming from a stubbed Ollama |
| `test_integration.py` | Full pipeline: PDF bytes → chunks → FAISS → prompt → answer |

---

## ⚙️ Configuration

All settings live in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_MODEL` | `llava` | Model loaded on startup in the Chat tab |
| `AVAILABLE_MODELS` | `[llama3, mistral, phi3, llava]` | Models shown in the sidebar dropdown |
| `TEMPERATURE` | `0.7` | Creativity (0 = deterministic, 1 = creative) |
| `MAX_TOKENS` | `512` | Max response length |
| `SYSTEM_PROMPT` | See file | Personality/instruction prompt for the assistant |

To change the PDF Q&A answer model or the embedding model, edit the constants at the top of `rag_chain.py` and `vector_store.py`.

---

## 🖼️ Supported Models

| Model | Type | Used In |
|-------|------|---------|
| `llava` | Vision + Text | Chat tab — image understanding |
| `llama3` | Text | PDF Q&A tab — document answering |
| `mistral` | Text | Chat tab — fast general responses |
| `phi3` | Text | Chat tab — lightweight, low RAM |
| `nomic-embed-text` | Embeddings only | PDF Q&A tab — FAISS indexing |

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
| `pytest` | Test suite (dev only — see `requirements-dev.txt`) |
| `pillow==12.2.0` | Image handling |

See `requirements.txt` for the full pinned list.

---


## 🔮 Roadmap

- [x] Local chat with text LLMs (Mistral, Llama3, Phi3)
- [x] Image Q&A with LLaVA
- [x] PDF Q&A with RAG pipeline (FAISS + nomic-embed-text + llama3)
- [x] Multi-document support (query across several PDFs at once)
- [x] Source citation with page number references
- [x] Automated test suite (pytest, runs without a live model)
- [ ] Support for scanned PDFs via OCR
- [ ] Docker container for one-command setup

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## 📄 License

[MIT](LICENSE)

---

> Built using Streamlit + LangChain + FAISS + Ollama — running 100% locally 🔒
