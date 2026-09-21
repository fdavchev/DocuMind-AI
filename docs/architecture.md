# Architecture

> Draft of the architecture/pipeline chapter of the thesis. It describes what
> the system is, how the parts fit together, and why the structure is what it
> is. The reasoning behind individual choices is recorded in
> [`DECISIONS.md`](../DECISIONS.md); this document describes the result.

---

## 1. System overview

DocuMind AI is a local document question-answering system. A user uploads one or
more PDFs and asks questions in natural language; the system answers from the
content of those documents and cites the file and page each part of the answer
came from.

The defining constraint is that **no document content leaves the machine**.
Every stage — text extraction, embedding, vector search, and answer generation —
runs locally. The system makes no network request that carries user data, and
requires no API key.

```mermaid
graph LR
    U[User] --> S[Streamlit UI<br/>app.py]
    S --> P[RAG pipeline<br/>pdf_handler / vector_store / rag_chain]
    P --> O[Ollama runtime<br/>localhost:11434]
    O --> M[(Local models<br/>llama3 · nomic-embed-text · llava)]
    P --> F[(FAISS index<br/>in process memory)]

    style O fill:#2d3748,color:#fff
    style M fill:#2d3748,color:#fff
    style F fill:#2d3748,color:#fff
```

Three things are worth noticing in that diagram:

1. **The vector index lives in process memory**, not on disk. It is built when a
   document is uploaded and discarded when the session ends.
2. **Ollama is a separate process**, reached over HTTP on localhost. The
   application never loads model weights itself.
3. **There is no database.** The only persistent state in the system is the
   model weights that Ollama manages.

---

## 2. Component structure

The codebase is organised by pipeline stage rather than by technical layer. Each
module owns one step and can be tested in isolation.

| Module | Responsibility | Depends on |
|---|---|---|
| `app.py` | Streamlit UI: two tabs, upload handling, chat loops, error rendering | every module below |
| `pdf_handler.py` | PDF → per-page text → chunked `Document`s tagged with source and page | pdfplumber, LangChain splitter |
| `vector_store.py` | Chunks → embeddings → FAISS index; similarity retrieval | langchain-ollama, FAISS |
| `rag_chain.py` | Retrieved chunks → cited prompt → streamed answer | ollama |
| `llm_chain.py` | The chat tab's text and vision paths | langchain-ollama, ollama, Pillow |
| `chat_history.py` | In-memory conversation history and text export | — |
| `errors.py` | Failure translation and pre-flight readiness checks | ollama, httpx |
| `config.py` | Tunable settings: models, prompts, UI labels | — |

The dependency graph is acyclic and shallow: `app.py` depends on the pipeline
modules, the pipeline modules depend only on libraries, and nothing depends on
`app.py`. That is what makes the pipeline testable without Streamlit, and what
lets the test suite exercise the whole chain without a UI.

---

## 3. The RAG pipeline

RAG — Retrieval Augmented Generation — addresses a specific problem: a language
model has no knowledge of a document it was never trained on. Rather than
fine-tuning a model per document, RAG retrieves the passages relevant to a
question and places them in the prompt, so the model reasons over supplied text
instead of recalled text. The answer is *grounded* in the document.

### 3.1 Ingestion

```mermaid
graph TD
    A[Uploaded PDF] --> B{Size ≤ 25 MB?}
    B -- no --> X[PdfTooLarge — refused before parsing]
    B -- yes --> C[pdfplumber: extract text per page]
    C --> D{Any text found?}
    D -- no --> Y[NoTextInPdf — scanned document]
    D -- yes --> E[Split each page separately<br/>500 chars, 50 overlap]
    E --> F[Document chunks tagged<br/>source = filename, page = n]
    F --> G[nomic-embed-text → vectors]
    G --> H[(FAISS index)]
```

Two properties of this stage carry the rest of the system:

**Page-wise splitting.** The text splitter is applied to each page
independently, never to the concatenated document. A chunk assembled across a
page boundary would have no single honest page number, and any citation attached
to it would be a guess. Splitting page by page guarantees each chunk belongs to
exactly one page. The cost is a few short chunks at page ends. A test,
`test_no_chunk_spans_two_pages`, pins this invariant.

**Metadata as a first-class payload.** Each chunk is a LangChain `Document`
carrying `{"source": filename, "page": n}`, and the index is built with
`FAISS.from_documents` rather than `from_texts`. This is the single change that
makes citation possible: the metadata survives embedding and comes back attached
to every retrieval result.

### 3.2 Retrieval

A question is embedded with the same model used for the chunks — this matters,
because similarity is only meaningful within one embedding space — and FAISS
returns the `k` nearest chunks by vector distance.

All documents share **one** index. Uploading a second PDF adds its chunks to the
existing index rather than creating a parallel one, so "which document best
answers this question?" is decided by embedding distance rather than by a
hand-written merge rule across separate indexes.

`k` is 4 for a single document and 6 once several are loaded. The widening is a
deliberate mitigation: with a fixed small `k`, one long document can plausibly
occupy every slot and crowd out a shorter file that holds the actual answer.

### 3.3 Generation

Retrieved chunks are rendered into a numbered context block:

```
[1] handbook.pdf, p. 3
the submission deadline is March first

---

[2] finance.pdf, p. 2
the budget forecast for the quarter
```

The prompt instructs the model to answer only from this context, to cite the
`[n]` markers inline, to say "I couldn't find that information in the document"
when the answer is absent, and never to cite a number not listed. The answer
streams token by token to the UI, and the same numbered passages are rendered
beneath it in a Sources panel.

The numbering is what closes the loop. The model cites `[2]`; the reader expands
Sources and sees that `[2]` is page 2 of `finance.pdf`, together with the text
the model was actually given. A grounded answer the reader cannot verify is
still just a claim; this makes it checkable.

---

## 4. Error handling architecture

A local-first system has more ways to be misconfigured than a hosted one: the
runtime may not be started, a model may not be downloaded. These are the normal
first-run experience, not exotic edge cases, so they are treated as a designed
part of the system rather than as exceptions to be caught somewhere.

```mermaid
graph TD
    subgraph Detection
        A[ConnectionError] --> T[translate]
        B[httpx.ConnectError] --> T
        C[ollama.ResponseError] --> T
        D[PdfminerException] --> T
    end
    T --> F[FriendlyError<br/>message + hint]
    F --> UI[st.error / st.warning]
    P[Pre-flight readiness check] --> F
```

The design has three parts:

1. **One translation point.** `errors.translate` is the only place that knows
   what an `httpx.ConnectError` means. Every call site does the same two things:
   catch, and render. Four different code paths — chat streaming, vision
   streaming, PDF indexing, PDF answering — therefore produce identical wording
   for identical causes.
2. **Every message carries a remedy.** A `FriendlyError` has a `message` (what
   went wrong) and a `hint` (what to do, usually a command to copy). A test
   asserts that every error type defines a hint.
3. **Pre-flight, not only reactive.** Both tabs render a readiness panel that
   verifies Ollama is reachable and the required models are installed *before*
   anything is uploaded. Catching a failure when the user asks their first
   question is correct but late; they have already uploaded a file and waited
   through indexing.

One implementation detail proved instructive and is worth reporting in the
thesis: `ollama.list()` wraps connection failures in a plain Python
`ConnectionError`, but a *streaming* `ollama.chat()` connects lazily during
iteration and surfaces the raw `httpx.ConnectError`. Two exception types, one
cause. This was found by probing the real client with the server stopped, not by
reading documentation — a small illustration of why integration boundaries need
empirical testing rather than assumption.

---

## 5. Testing strategy

The suite has 66 tests and runs with **no Ollama server and no model pulled**.
That constraint drove several design choices and is the reason the tests are
usable in CI rather than being a demo script.

```mermaid
graph TD
    A["test_app_smoke.py — boots app.py<br/>via Streamlit's script runner"] --> B
    B["test_integration.py — PDF bytes → answer"] --> C
    C["test_pdf_handler · test_vector_store<br/>test_rag_chain · test_errors"]

    style A fill:#4a3f6b,color:#fff
    style B fill:#3f5a6b,color:#fff
    style C fill:#3f6b4a,color:#fff
```

| Layer | What it proves | Substitutions |
|---|---|---|
| Unit | Extraction, chunking, metadata, retrieval, prompt shape, error mapping | Fake embeddings |
| Integration | The whole chain from PDF bytes to a cited answer | Fake embeddings, stubbed Ollama |
| Smoke | `app.py` actually starts and renders, with Ollama up and down | Stubbed `ollama.list` |

Two techniques make this possible:

**Injectable embeddings.** `build_vector_store(chunks, embeddings=None)`
defaults to `OllamaEmbeddings` but accepts any `Embeddings` implementation. The
tests pass a deterministic bag-of-words fake. Because it is a real `Embeddings`
subclass, FAISS indexing and similarity search are genuinely executed — only the
model behind them is substituted.

**Generated test PDFs.** `tests/conftest.py` contains a small raw PDF writer
that builds a valid PDF from a list of page strings. A test asserting "this
chunk is on page 3" is only readable if page 3's content is visible in the test
itself; a committed binary fixture hides that, and adding `reportlab` would be a
heavyweight dependency for one job.

What the suite deliberately does **not** test is answer quality. That is a
research-evaluation question requiring labelled question–answer pairs, and it is
outside the scope of an engineering-focused capstone. Section 7 revisits this as
future work.

---

## 6. Deployment

Two supported paths, with different trade-offs.

**Local Python install** — a virtualenv, `pip install -r requirements.txt`, and
a locally installed Ollama. Lowest overhead for development; requires the
correct Python version and a working Ollama on the host.

**Docker Compose** — three services:

```mermaid
graph LR
    O[ollama<br/>official image] --> I[model-init<br/>one-shot pull]
    I --> A[app<br/>Streamlit]
    V[(named volume<br/>model weights)] -.- O

    style O fill:#2d3748,color:#fff
    style V fill:#2d3748,color:#fff
```

Model weights live in a named volume, so the roughly 6 GB download happens once
and survives `docker compose down`. The `model-init` service exists to solve an
ordering problem: having `app` wait for Ollama to be merely *reachable* is not
enough, because the first question would then fail with "model not found".
Instead `app` waits on `service_completed_successfully` of the pull step, so by
the time the UI is available, the models are genuinely present.

The app finds the runtime through the `OLLAMA_HOST` environment variable, which
both the `ollama` client and `langchain-ollama` honour — verified empirically
before the compose file was written.

---

## 7. Known limitations and future work

Stated plainly, because a limitation named in the thesis is a stronger position
than one found by the committee.

| Limitation | Consequence | Possible resolution |
|---|---|---|
| No OCR for scanned PDFs | Image-only documents cannot be indexed | Tesseract fallback when extraction yields no text |
| FAISS has no cheap delete | Removing a file from the uploader does not un-index it; only a full clear does | Rebuild the index on removal, or move to a store with deletion |
| Index is not persisted | Re-indexing on every session, 10–30 s per document | `FAISS.save_local`, if the use case shifts to a fixed corpus |
| No answer-quality evaluation | Retrieval and grounding are untested for accuracy | A small labelled question set with retrieval precision@k |
| Fixed chunk size (500/50) | Not tuned against this corpus | Sweep chunk size and overlap, measure retrieval precision |
| `langchain-community` FAISS import | Upstream has announced it is sunsetting the package | Migrate when a standalone integration package exists |
| Single-user, session-scoped | Not designed for concurrent users | Out of scope; the local-first premise assumes one user |

The most academically valuable of these is the fourth. The system currently
demonstrates that grounding and citation *work mechanically* — the right page is
retrieved and correctly attributed, which the tests verify. It does not
demonstrate how *often* the right page is retrieved. A modest labelled set of
questions over a known document, scored by whether the correct page appears in
the top `k`, would turn a qualitative claim into a measured one, and is the
natural next step for the evaluation chapter.
