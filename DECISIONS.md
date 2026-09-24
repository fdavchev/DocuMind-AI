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

`PdfLoader` extracts each page separately and `TextSplitter` runs the splitter
once per page, rather than concatenating the whole PDF and splitting the result.
(Both were `pdf_handler.py` until the OOP refactor moved them into
`documind/documents/`; the behaviour is unchanged.)

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

Uploading a second PDF calls `VectorStore.add` on the existing store instead of
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

`VectorStore(config, embeddings=None)` defaults to `OllamaEmbeddings` but
accepts any `Embeddings` implementation; the tests pass a deterministic
bag-of-words fake. Ollama's `chat` is monkeypatched in the integration tests, and
`RagPipeline` takes its model as an `LLMProvider`, so a test can hand it a fake
implementation instead.

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

**Reconsidered during Phase 3 hardening** *(2026-09-24)*: the hardening pass
considered adding save/load keyed by a file hash, so a repeat upload skips
re-embedding. Declined for the same reason as above — it would only save
10–30s on a same-file re-upload, which isn't how the demo or the evaluation
runs, and it would mean explaining at the defense why a documented privacy
guarantee was reversed for a marginal speed gain. The decision stands.

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

**Why:** unit tests over the loaders, the splitter, the vector store and the
pipeline can all pass while the app itself fails to start, because nothing in
them imports
`app.py`. That is exactly the failure that ruins a live demo, and it is the one
class of bug that only an end-to-end boot catches.

It earned its place immediately: the first run surfaced that `llm_chain.py` was
building its LLM with `langchain_community.llms.Ollama`, a class deprecated and
scheduled for removal, which printed a deprecation warning on every start. It
now uses `OllamaLLM` from `langchain-ollama`, which was already a dependency.

**Still outstanding:** `documind/rag/vector_store.py` imports FAISS from
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

---

## 17 — Chunks reach the embedding model in batches of 64
*2026-09-24*

`VectorStore.build` and `VectorStore.add` no longer hand every chunk to the
embedding model in one call. `_embed_in_batches` sends them in slices of
`AppConfig.embedding_batch_size` (64), collects the vectors, and only then gives
FAISS the whole set in one step (`FAISS.from_embeddings` / `add_embeddings`).

**What prompted it:** uploading the 792-chunk *Working anytime, anywhere* report
failed with `Ollama returned an error. Post "http://127.0.0.1:<port>/tokenize":
dial tcp ...: connectex: No connection could be made because the target machine
actively refused it. (status code: 400)`. Reproduced outside the app with
LangChain's `OllamaEmbeddings` against Ollama 0.30.2 on Windows (RTX 4060):
embedding all 792 texts in one call failed 2 times out of 3; the same 792 texts
in slices of 64 or 128 succeeded 6 times out of 6, about 6 s per full pass.
Every 128-chunk slice of the document succeeds on its own, so no single chunk is
at fault — it is the size of the request, and it becomes flaky above a few
hundred texts. Nothing in our code had changed; this was simply the first
document with hundreds of chunks.

**Likely mechanism (inferred, not proven):** Ollama fans one `/api/embed`
request out into one internal request per text, and Windows refuses the
connections that overflow its pending-connection queue.

**Alternatives considered:**
- *Upgrade or reconfigure Ollama.* Out of our hands on a user's machine, and
  with the mechanism unproven there is no version or setting known to fix it.
  Batching works against the Ollama that is installed today.
- *No batching, retry on failure.* The full 792-text request failed two times
  in three, so a retry is close to a coin toss and only hides the cause.
- *A module-level constant instead of an `AppConfig` field.* Every other tuning
  value lives in `AppConfig` (see the header of `config.py`), and a config
  field lets the tests use a batch size of 2 without monkeypatching.
- *Build from the first batch with `from_documents`, then `add_documents` the
  rest.* Simpler to read, but a batch that failed halfway would leave a partial
  index behind: `build` would already have discarded the old one, and `add`
  would leave part of a document indexed under its name. Because `app.py`
  only indexes uploads whose name is not yet in `sources`, that file would
  never be retried and would quietly be answered from part of its pages.
  Embedding first and inserting once keeps both methods all-or-nothing, as
  they were before.

**Why 64:** it was measured reliable, and it is the smaller of the two sizes
that were, which leaves the wider margin below the few hundred texts where
failures started. The cost is negligible: a full pass of 792 chunks took about
6 s in slices of 64 or of 128.

**Pinned by tests** in `test_rag_vector_store.py`: embedding calls never carry
more than the configured batch size, every batched chunk is searchable, a
batched `build` still replaces the old index, and a failing batch leaves the
index as it was.

---

## 18 — One reset button in the sidebar, and it follows the mode
*2026-09-24*

The sidebar's clear button now resets whichever mode is showing. In Chat mode it
reads **🗑️ Clear chat** and empties the conversation, as before. In PDF Q&A it
reads **🗑️ Clear documents & chat** and runs `reset_pdf_mode()`: a fresh index,
no answers, an empty uploader. The button that used to do this inside the
Documents panel is gone, so each mode has exactly one reset.

**What prompted it:** pressing Clear chat in PDF Q&A did nothing. That button
only ever cleared Chat mode's history, and the real PDF reset sat inside the
Documents panel, which collapses as soon as a file is indexed. To the user the
reset was invisible, and the one they could see ignored them.

To label the button by mode, the sidebar has to know the mode, so the mode
selector is now drawn before the sidebar. The page looks the same: the sidebar
is a separate container, so the selector still sits directly under the title.

**Alternatives rejected:**
- *Keep the reset inside the Documents panel.* It is exactly where it was
  hidden. Keeping the panel open would bring the button back, but the panel
  collapses on purpose, to give the conversation the room.
- *Two buttons: Clear chat always in the sidebar, Clear documents shown only in
  PDF mode.* In PDF Q&A the user would face a Clear chat button that clears a
  conversation they can't see, which is the same confusion that caused the bug.

**Pinned by tests** in `test_app_smoke.py`: the button's label in each mode,
that it empties the chat in Chat mode, that in PDF Q&A it empties the answers,
the index and the uploader and brings back the open "Upload documents" panel
with the input disabled, and that the Documents panel has no clear button of
its own.

---

## 19 — Every question is sent the title and authors of each document
*2026-09-24*

Three changes, all aimed at one failure: *"What is the title of this paper?"*
answered with *"I couldn't find that information"* for a paper that was
indexed correctly.

**What prompted it:** on the 47-page StudentBench paper
(`eval/corpus/native-text-english/2609.28470v1.pdf`, 379 chunks) the chunk
holding the title and authors ranked 228th of 379 for that question. The top
four were bibliography entries, which share more surface words with "title of
this paper" than a title page does. Retrieval is pure similarity top-k, so the
answer never reached the prompt.

**1. A DOCUMENT line per file, outside the similarity search (the main fix).**
At ingest, `PdfLoader` now reads the PDF's own Title and Author properties into
`Document.metadata` (a `DocumentMetadata`). `RagPipeline` turns that into one
line per file — `DOCUMENT: paper.pdf — Title: … — Authors: …` — and `ask` puts
the lines of every file still in the store at the top of the CONTEXT, whatever
the question. When a file declares no title or no authors, the opening 200
characters of its first passage are added instead (`Opening lines: …`), since
a title page holds both. The lines live on the pipeline, not in the index, and
are filtered by `VectorStore.sources` at question time, so a file removed from
the store drops out of the prompt with it.

*Alternatives rejected:*
- *Always retrieve the first chunk of each document.* It costs a passage slot
  per file, and a numbered `[n]` passage invites a citation of "p. 1" for
  facts that are not about the title at all.
- *Detect metadata questions and change the retrieval for them.* A keyword
  rule would miss rephrasings ("who wrote this?") and would be one more thing
  to test in both languages. A line or two per document is cheap enough to
  send every time.
- *Raise `retrieval_k`.* Rank 228 is out of reach of any sensible k.

*Known limit:* some PDFs carry a useless Title property (for example
"Microsoft Word - draft3.docx"). The opening lines are added only when a
property is missing, so such a file would be described by its bad title.

**2. nomic-embed-text gets its task prefixes.** The default embedding model is
wrapped in `TaskPrefixedEmbeddings`, which prepends `search_document: ` to
every passage and `search_query: ` to every question, as the model's
documentation asks. The prefixes are `AppConfig` fields next to
`embedding_model`, because they belong to that model. The wrapper only touches
the text on its way into the model: FAISS still stores and returns the passage
as it was. An injected model (the tests' `FakeEmbeddings`) is used unwrapped.
This is a contributing fix, not the main one: in the live check after all three
changes, the top four passages for both the title and the authors question were
still bibliography entries, and the question was answerable only because of the
DOCUMENT line.

**3. Near-empty chunks are no longer indexed.** `TextSplitter.split` used to
drop only whitespace-only chunks, so a lone `)` left at a page end was indexed.
Its vector is vague enough to sit close to many questions. A chunk now needs
at least `AppConfig.min_chunk_letters` (3) letters. `str.isalpha()` counts
Cyrillic, so Macedonian text is treated the same. On the StudentBench paper
this removes 2 of 379 chunks.

*Trade-off:* a page holding only numbers (a bare table of figures) now yields
no chunks. A document made of nothing else is refused as empty, which is
honest: a number with no words around it cannot be found by a question anyway.

**Pinned by tests:** `test_rag_pipeline.py` (the DOCUMENT line with declared
metadata, the opening-lines fallback, trimming, one line per file, a removed
file dropping out, and the title reaching the prompt when its page is not
retrieved), `test_document_loader.py` (PDF Title/Author read, empty when
undeclared, text files declare nothing), `test_rag_vector_store.py` (prefixes
on passages and questions, stored text unprefixed, the default model wrapped,
an injected model not wrapped) and `test_text_splitter.py` (near-empty pages
dropped, short real words kept in both alphabets, the threshold read from
config).

---

## 20 — The embedding model is the multilingual nomic-embed-text-v2-moe
*2026-09-24*

`AppConfig.embedding_model` is now `nomic-embed-text-v2-moe` instead of
`nomic-embed-text`. The readiness check (`errors.PDF_MODELS`), the Docker
`model-init` pull, the README and `docs/architecture.md` name the new model.

**What prompted it:** Macedonian questions about Macedonian documents were
answered badly because the right passage was not retrieved. v1 of
nomic-embed-text is effectively English-only: its tokenizer has almost no
Cyrillic vocabulary, so Macedonian passages all embed to similar vectors. With
v1, the passage holding the answer ranked 7th, 23rd, 17th, 5th and 1st out of
121 or 21 chunks for eval questions 12, 13, 14, 18 and 19. Only the top 4
reach the prompt, so four of the five questions could not be answered.

**Result with v2 (live run, same questions, same chunking, top 4 retrieved):**
the answer passage ranked 1st, 2nd, 2nd, 1st and 1st, so all five reach the
prompt. For Q13 the passage ranked 1st also holds the answer ("3.05 метри"),
from page 2. English questions did not get worse: Q7, Q11 and Q15 ranked 1st,
Q16 and Q17 2nd. llama3 answered Q12 and Q13 correctly from the retrieved
passages.

**Why this model:** it is trained on about 100 languages, it runs in Ollama
(958 MB), and it uses the same `search_query: ` / `search_document: ` task
prefixes as v1, so `TaskPrefixedEmbeddings` and the prefix settings (#19)
did not change. Its vectors also have 768 numbers, like v1's.

**Known limit:** v2 reads at most 512 tokens per input, where v1 read far
more. Chunks are 500 characters, which measured at most 230 tokens (with the
prefix) on the eval PDFs, so nothing is cut off at the current `chunk_size`.
A much larger `chunk_size` would need rechecking against this limit.

*Alternatives rejected:*
- *Keep v1 and add keyword search (BM25) next to it.* That helps questions
  that repeat words from the document, but it does not fix the cause: the
  vectors still cannot tell Macedonian passages apart.
- *Raise `retrieval_k` until the answer is included.* Rank 23 would need a
  prompt six times longer, full of unrelated passages.
- *Translate questions to English first.* The documents are Macedonian too,
  so their vectors would stay just as poor.

---

## 21 — The prompt names the answer language, picked from the question's alphabet
*2026-09-24*

`RagPipeline.build_rag_prompt` now counts the question's Cyrillic and Latin
letters. More Cyrillic means Macedonian; anything else (more Latin, an even
split, or no letters at all) means English. The chosen language's instruction
goes on its own line directly before `ANSWER:`:

- Macedonian: *"Respond only in Macedonian (македонски јазик), the language of
  the question. Do not use English."*
- English: *"Respond only in English, the language of the question."*

The "not in the context" sentence in the rules follows the same choice: *"Не
можев да ја најдам таа информација во документот."* for Macedonian, the old
*"I couldn't find that information in the document."* for English. Both
languages' texts are `AnswerLanguage` values on `AppConfig` (`macedonian`,
`english`), next to `ocr_language = "mkd+eng"`, which names the same two
languages. `RagPipeline` now takes the config as its first constructor argument
to reach them.

**What prompted it:** Macedonian questions were answered in English. A debugger
run ruled out a session or history bug (no state carries between calls):
llama3-8B writes English by default, and the prompt around the question was all
English. A generic rule in the Rules list (*"Answer in the same language as the
QUESTION, regardless of what language the context passages are in"*) gave 0-2
Macedonian answers out of 8 per question.

**Why these choices (debugger's live measurements, 8 runs per question):**
- *Position:* the instruction only works at the end of the prompt, right
  before generation starts. In the Rules list, far above, it is ignored.
- *Language-specific text, not a generic one:* a generic "answer in the same
  language as the question" placed before `ANSWER:` made things worse, turning
  English questions into Macedonian answers 5 times out of 8. Naming the
  language outright gave 8/8 in both directions, including at temperature 0.
- *Detected in code, not left to the model:* the app handles exactly two
  languages that use different alphabets, so counting letters is exact for
  real questions and costs nothing. A question like *"Што е FIBA?"* stays
  Macedonian because most of its letters are Cyrillic.
- *English as the default:* it is what llama3 falls back to anyway, and a
  question with no letters (*"1 + 1 = ?"*) has no language to match.

**The old generic rule was removed.** With the specific instruction in place it
made no measurable difference either way, and keeping two statements of the
same rule in one prompt invites them to drift apart.

**The fallback sentence is translated rather than described.** The model is
given the exact Macedonian sentence to say, instead of being told to translate
the English one itself. That keeps it to one fixed sentence in each language,
the same shape as the instruction above.

**Live check after the change (2026-09-24, llama3 via Ollama, default
temperature 0.7, Кошарка.pdf and the Green City Accord indexed together, 3 runs
per question):** 18 of 18 answers were in the question's language. That covers
two Macedonian questions from the eval set, an English question whose answer is
only in the Macedonian PDF (*"Who invented basketball and in what year?"*), an
English question on the English PDF, and a question in each language whose
answer is in neither document. The Macedonian out-of-scope question got the
Macedonian fallback sentence in 2 of 3 runs. In the third, the model quoted
attendance figures instead: a wrong answer, but still in Macedonian. The English
out-of-scope question got the English sentence 3 of 3 times.

*Alternatives rejected:*
- *A language-detection library (langdetect, fastText).* A new dependency to
  tell apart two languages that use different alphabets.
- *Translating the whole prompt into Macedonian for Macedonian questions.*
  Two copies of every rule to keep in step, for a problem one line fixed.
- *Putting the instruction in the system prompt.* It would sit even further
  from where generation starts, which is where the rule was already failing.

**Pinned by tests:** `test_rag_pipeline.py` (Cyrillic question → Macedonian
instruction, Latin question → English instruction, the instruction sitting
directly before `ANSWER:`, a Cyrillic question with a Latin acronym staying
Macedonian, no letters and an even split both defaulting to English, the
not-found sentence matching the language, and the texts coming from the config).

---

## 22 — Every DOCUMENT line carries the document's opening lines
*2026-09-24*

Two changes to the DOCUMENT line from #19, in `RagPipeline._describe_document`:

1. **The opening lines are always added.** Before, `Opening lines: …` was added
   only when the PDF declared no Title or no Author. Now it follows the title
   and authors every time, so a line reads
   `DOCUMENT: paper.pdf — Title: … — Authors: … — Opening lines: …`.
2. **`OPENING_TEXT_LIMIT` is 400 characters instead of 200.**

The prompt rule that explains DOCUMENT lines to the model now says they hold
the title and authors *when declared* and the opening lines, and names the
authors' affiliations as one of the things they answer.

**What prompted it:** eval row 10, *"What is the first author's
affiliation?"* on `eval/corpus/native-text-english/2609.28371v1.pdf`, was
answered by guessing from an email address ("we can infer … ORNL based on
yangm@ornl.gov"). That paper declares its title and authors, so under #19 its
DOCUMENT line had no opening lines. The affiliations ("Fusion Energy Division,
Oak Ridge National Laboratory, Oak Ridge, TN, USA") are printed on the title
page and appear in no metadata field. Retrieval did not rescue it either: a
debugger run found the chunk holding them ranked 97th of 188 for that
question. It is the same failure as the title question in #19: a question
about the document itself is not topically similar to the passage that
answers it.

**Why 400:** at 200 characters the first author's affiliation fits, but the
second author's is cut off mid-sentence. At 400 both fit, with the start of
the abstract after them. It does not need to go higher: the text comes from
the first chunk, which is at most `chunk_size` (500) characters anyway.

**Cost:** each indexed document now adds up to 400 more characters to every
prompt, even when its metadata is complete. With a handful of documents that
is well within llama3's context, and it is what makes title-page facts
answerable at all.

**This also eases #19's known limit.** A PDF whose Title property is junk
("Microsoft Word - draft3.docx") used to be described by that title alone.
Its real title now follows in the opening lines.

*Alternatives rejected:*
- *Add an `Affiliations:` metadata field.* PDFs have no standard property
  for it, so it would have to be parsed out of the title page, and the layout
  of that page differs from paper to paper. Handing the model the raw opening
  text lets it read the affiliations the way a person would.
- *Keep the opening lines conditional and raise `retrieval_k`.* Rank 97 of
  188 is out of reach of any sensible k, for the same reason as in #19.
- *Always retrieve the first chunk as a numbered passage.* Rejected in #19:
  it costs a passage slot per file and invites "p. 1" citations for unrelated
  facts.

**Live check (2026-09-24, llama3 and nomic-embed-text-v2-moe via Ollama,
one paper indexed at a time):** row 10 answered *"Fusion Energy Division, Oak
Ridge National Laboratory, Oak Ridge, TN, USA"* 3 of 3 times at temperature 0
and 3 of 3 times at the default 0.7. Rows 9 and 11 (same paper) and rows 5, 6
and 7 (the StudentBench paper) were still answered correctly at both
temperatures.

*Known limits:*
- With several papers indexed together, "the first author's affiliation" is
  ambiguous: the model has to pick a paper. A debugger run found the change
  helps there (1 of 3 correct, against 0 of 3 before) but does not solve it.
- A fact taken from a DOCUMENT line has no `[n]` label of its own, so the
  model either cites an unrelated passage number (usually `[1]`) or writes
  `[DOCUMENT]`. Both were seen in the live check. This dates from #19 and is
  not changed here.

**Pinned by tests** in `test_rag_pipeline.py`: opening lines added when the
title and authors are both declared, trimming to exactly
`OPENING_TEXT_LIMIT` characters, a short opening kept whole, one line per
file and a removed file dropping out (both now expecting opening lines), and
the prompt rule mentioning affiliations.
