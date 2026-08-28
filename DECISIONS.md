# Design Decisions

A running log of the non-obvious engineering choices in DocuMind AI, written as
they are made. Each entry states the decision, the alternatives considered, and
why this one won — the raw material for the design-decisions chapter of the
thesis, and for the questions a defense committee tends to ask.

Entries marked **(reconstructed)** were made before this log existed; the
reasoning is stated as it holds today rather than as it was recorded at the time.

---

## 1 — Chunks are split page by page, never across a page boundary
*2026-08-27*

`pdf_handler.py` extracts each page separately and runs the text splitter once
per page, rather than concatenating the whole PDF and splitting the result.

**Alternative:** split one continuous string, which is the more common tutorial
approach and produces slightly fewer, more evenly sized chunks.

**Why this way:** a chunk assembled from the end of page 3 and the start of
page 4 has no single honest page number. Any citation attached to it is a guess.
Since source citations are a graded feature, correctness of the citation matters
more than chunk-size uniformity. The cost is a handful of short chunks at page
ends — cheap next to a citation that points at the wrong page. A test
(`test_no_chunk_spans_two_pages`) pins this property so it can't regress.

---

## 2 — One shared FAISS index for all documents, not one index per file
*2026-08-27*

Uploading a second PDF calls `add_documents` on the existing store instead of
building a separate index per file and merging results at query time.

**Alternative:** an index per document, then query each and merge the top hits.

**Why this way:** a single index means one similarity ranking across the whole
corpus, so "which document answers this best?" is decided by the embedding
distances rather than by a hand-written merge rule. It is also simpler: no
per-index bookkeeping, no reconciling scores whose scales aren't guaranteed
comparable. Each chunk still carries its `source` filename, so per-document
provenance survives without per-document indexes.

**Known cost:** FAISS has no cheap delete, so removing a file from the uploader
does not un-index it. The "Clear PDFs & Chat" button is the escape hatch. If
per-file removal ever becomes a requirement, that is the trigger to revisit this.

---

## 3 — Retrieval widens from k=4 to k=6 once several PDFs are loaded
*2026-08-27*

**Why:** with one document, four passages is a reasonable context window. With
several, a single long document can plausibly occupy all four slots and crowd
out a shorter file that holds the actual answer. Widening the window is the
cheapest mitigation. The principled alternative — retrieve per source and
interleave — was rejected as premature for a corpus of a few PDFs.

---

## 4 — The embedding model is injectable, and the LLM call is stubbed in tests
*2026-08-27*

`build_vector_store(chunks, embeddings=None)` defaults to `OllamaEmbeddings` but
accepts any `Embeddings` implementation; the tests pass a deterministic
bag-of-words fake. Ollama's `chat` is monkeypatched in the integration tests.

**Alternative:** integration tests that require a live Ollama with `llama3` and
`nomic-embed-text` pulled.

**Why this way:** the test suite has to run on a machine that has never installed
Ollama — that is what makes it CI-viable and what makes it credible evidence of
engineering maturity rather than a demo script. The fake embedding is a real
`Embeddings` subclass, so FAISS indexing and similarity search are genuinely
exercised; only the model behind them is substituted. What the suite deliberately
does *not* test is answer quality, which is a research-evaluation question and
out of scope for this capstone.

---

## 5 — Test PDFs are generated in memory, not checked into the repo
*2026-08-27*

`tests/conftest.py` contains a ~50-line raw PDF writer that builds a valid PDF
from a list of page strings.

**Alternatives:** commit sample PDF binaries, or add `reportlab` as a test
dependency.

**Why this way:** a test that asserts "this chunk is on page 3" is only readable
if page 3's content is visible in the test itself. Binary fixtures hide that, and
`reportlab` is a heavyweight dependency for one job. The hand-rolled writer adds
no dependency and keeps each test self-describing.

---

## 6 — Retrieval and generation use different models than the chat tab
*(reconstructed)*

`llava` drives the chat tab; `llama3` answers PDF questions;
`nomic-embed-text` does the embedding.

**Why:** `llava` is a vision-language model — its strength is image grounding,
not long-context document reasoning. `nomic-embed-text` has no generative
capability at all; it exists only to turn text into vectors, and it is small and
fast enough that indexing a document takes seconds rather than minutes. Using one
model for all three jobs would be worse at each of them.

---

## 7 — FAISS rather than Chroma or a hosted vector database
*(reconstructed)*

**Why:** the project's central constraint is that nothing leaves the machine,
which rules out hosted options immediately. Between the local libraries, FAISS is
an in-process library with no server, no daemon, and no on-disk schema — it is a
dependency, not infrastructure. Chroma's advantages (persistence, collections,
metadata filtering as a first-class feature) are all things this app does not
currently need, since each session indexes fresh uploads. Choosing FAISS keeps
the setup story "pip install and run", which directly serves the defense demo.

---

## 8 — Ollama rather than calling llama.cpp directly
*(reconstructed)*

**Why:** Ollama is a thin management layer over the same inference engine —
it handles model download, quantisation choice, GPU offload, and process
lifecycle, and exposes one HTTP API. Driving `llama.cpp` directly would mean
owning model file management and binding setup as part of the project's setup
instructions, on a project whose grading depends partly on someone else being
able to run it. The abstraction cost is real (less control over sampling
parameters and no direct access to lower-level runtime flags), but it buys a
setup procedure that fits in four `ollama pull` commands.

---

## 9 — The vector store lives in session state, not on disk
*(reconstructed)*

Each Streamlit session builds its index from the uploaded files and discards it
when the session ends.

**Why:** the app's promise is that documents never leave the machine, and not
persisting them is the strongest form of that promise — there is no index file to
leak, and no stale index to invalidate when a document changes. The cost is
re-indexing on every session, which is 10–30 seconds for a typical PDF and
acceptable for interactive use. A persistent store (`FAISS.save_local`) would be
the right call if the use case shifted toward a fixed corpus that is queried
repeatedly over time; it is the wrong call for "upload a document and ask about
it", which is what this app is.

---

## 10 — Failure translation lives in one module, not at each call site
*2026-08-27*

`errors.py` owns the mapping from raw exception to user-facing message. Every
call site does the same two things: catch, and render.

**Alternative:** `try/except` blocks in `app.py` with the message written inline
at each place a call can fail.

**Why this way:** the same failure reaches the user through four different code
paths (chat stream, vision stream, PDF indexing, PDF answering), and a message
written inline drifts between them. Centralising also makes the mapping
*testable* — `test_errors.py` asserts that a `ConnectionError` and an
`httpx.ConnectError` both become the same "Ollama isn't running" message,
without a running server. The UI never has to know what an httpx exception is.

**A detail worth keeping:** `ollama.list()` wraps connection failures in a plain
`ConnectionError`, but a *streaming* `ollama.chat()` connects lazily and leaks
the raw `httpx.ConnectError`. Two exception types, one cause. This was found by
probing the real client with the server stopped, not by reading the docs.

---

## 11 — Errors are pre-flighted as well as caught
*2026-08-27*

Both tabs render a "System check" panel that verifies Ollama is reachable and
the required models are pulled, before the user uploads anything.

**Why:** catching a failure at the moment the user asks their first question is
correct but late — they have already uploaded a file and waited through
indexing. The check costs one localhost HTTP call, is cached in session state so
it doesn't run on every rerun, and has an explicit re-check button. For a live
defense demo, this is the difference between "it's broken" and "Ollama isn't
started yet, one moment."

The oversized-PDF check follows the same principle: the size gate runs *before*
parsing, so an unusable file is refused in milliseconds instead of after a long
spinner.

---

## 12 — Docker runs the app and Ollama as separate services
*2026-08-27*

`docker-compose.yml` defines three services: `ollama`, a one-shot `model-init`
that pulls the models, and `app`. Model weights live in a named volume.

**Alternatives:** a single image with Ollama and the app together; or baking the
model weights into the image.

**Why this way:** baking in ~6 GB of weights makes the image unusable to
distribute and forces a full re-download on any rebuild — the named volume
pulls them once and survives `docker compose down`. Keeping Ollama as its own
service means using the official image, which already has GPU support wired up
correctly; reimplementing that in a combined image would be strictly worse.

`model-init` exists to solve an ordering problem: `app` waiting on Ollama being
*reachable* is not enough, because the first question would then fail with
"model not found". `app` waits on `service_completed_successfully` of the pull
step instead, so by the time the UI is up, the models are genuinely there.

**Not yet verified:** the image has not been built — Docker isn't installed on
the development machine. The compose file parses and the service wiring is
reasoned through, but `docker compose up` remains untested.

---

## 13 — The test suite boots the real app, not just its modules
*2026-08-27*

`tests/test_app_smoke.py` runs `app.py` through Streamlit's `AppTest` script
runner and asserts it starts with no exception — both with Ollama reachable and
with it refused.

**Why:** unit tests over `pdf_handler`, `vector_store` and `rag_chain` can all
pass while the app itself fails to start, because nothing in them imports
`app.py`. That is exactly the failure that ruins a live demo, and it is the one
class of bug that only an end-to-end boot catches.

It earned its place immediately: the first run surfaced that `llm_chain.py` was
building its LLM with `langchain_community.llms.Ollama`, a class deprecated and
scheduled for removal, which printed a deprecation warning on every start. It
now uses `OllamaLLM` from `langchain-ollama`, which was already a dependency.

**Still outstanding:** `vector_store.py` imports FAISS from
`langchain-community`, which upstream has announced it is sunsetting. It works
and there is no drop-in replacement package yet, so this is logged as known
technical debt rather than fixed.

---

## 14 — OCR is a fallback, not a requirement
*2026-08-27*

Scanned PDFs are read with Tesseract when it is installed. When it isn't, the
app says so — naming the install command for the user's platform — and
text-based PDFs continue to work.

**Alternative:** make Tesseract a hard dependency and fail without it.

**Why this way:** Tesseract is a native binary, not a Python package. Requiring
it turns `pip install -r requirements.txt` into a platform-specific system
install and breaks the one-command Docker promise for anyone running locally.
Scanned PDFs are also the minority case; making the common case depend on the
uncommon one is the wrong trade. The Docker image installs Tesseract, so the
containerised path supports scanned documents out of the box.

**A detail that matters for accuracy:** the trigger is not "the page has no
text" but "the page has fewer than 20 characters". Scanned pages are rarely
completely empty — a stamped page number or a header artefact often survives
extraction — and a page with nine characters on it has no usable text layer
even though `extract_text()` returned something.

**Three failure states, three messages.** "Scanned and Tesseract is missing",
"scanned and OCR read nothing", and "genuinely empty" look identical to the
caller but need different remedies: install Tesseract, re-scan at higher DPI, or
check the file. `errors.no_text_error` picks between them.

**Verified against a real scan (2026-08-27):** with Tesseract 5.4.0 installed,
an image-only PDF — a rendered picture of text carrying no text layer at all —
was run through the full pipeline. Both pages were read character-for-character
correctly, and the recovered text kept its page number, so a citation from a
scanned document is as accurate as one from a text document. Measured cost was
roughly 0.55 s per page at 300 DPI. Without the binary the same file yielded
nothing, which is the intended degradation rather than a failure.

---

## 15 — Tests force OCR off unless a test turns it on
*2026-08-27*

An autouse fixture in `conftest.py` patches `ocr.is_available` to return False
for every test.

**Why:** without it the suite behaves differently depending on whether the
machine running it happens to have Tesseract installed — pages with a thin text
layer would be OCR'd on one machine and skipped on another. A test suite whose
results depend on undeclared host state is not evidence of anything. Tests that
exercise OCR re-patch the function themselves, and because fixtures apply before
the test body, theirs wins.

---

## 16 — A mode selector instead of tabs, so the input can be pinned
*2026-08-28*

The two modes are chosen with a segmented control at the top of the page
rather than `st.tabs`, and the single `st.chat_input` lives at module top level.

**Why:** Streamlit pins the chat input to the bottom of the viewport only when
the widget is created directly in the main container. From
`streamlit/elements/widgets/chat.py`:

```python
ancestor_block_types = set(self.dg._active_dg._ancestor_block_types)
if (self.dg._active_dg._root_container == RootContainer.MAIN
        and not ancestor_block_types):
    position = "bottom"
else:
    position = "inline"
```

Inside `st.tabs` the input is therefore always `inline`: it sits in the document
flow and scrolls out of reach as the conversation grows, so the user has to
scroll back down to type. No amount of CSS fixes this cleanly, because the
widget is simply in the wrong place in the tree.

**Alternatives rejected:** pinning the inline input with `position: fixed` CSS,
which means owning the width, background and z-index by hand and re-doing it
whenever Streamlit's DOM changes; and a fixed-height scrolling container, which
was tried first and only stabilised the input relative to the message list, not
to the viewport.

**Cost:** the UI is no longer literally tabbed, and the mode name is now shared
state in `config.py`. Both cheap. The behaviour is what a chat interface is
expected to do.

**Pinned by a test** that asserts the *condition* rather than the symptom:
`test_the_input_is_top_level_so_streamlit_pins_it` captures the input's ancestor
block types at creation and fails if it is ever nested again.
