# DocuMind AI — Project Report & Testing Guide

**Date:** 2026-08-27 · **Author:** Filip Davchev, with Claude Code
**Scope:** Phases 1–4 of the capstone roadmap

This document records what was built, what was verified (and how), what remains
open, and a step-by-step guide for testing the system by hand. It is written to
be readable without inspecting the code.

---

## 1. Completion status

All four phases are complete, each on its own Git branch, all pushed to
`origin`.

| Phase | Branch | Tests | Pushed |
|---|---|---|---|
| 1 — Citations & multi-document | `phase-01-citations-and-multidoc` | 34 | ✅ |
| 2 — Polish & defense-readiness | `phase-02-polish-and-defense-readiness` | 66 | ✅ |
| 3 — Write-up | `phase-03-write-up` | 66 | ✅ |
| 4 — OCR fallback | `phase-04-ocr-fallback` | 87 | ✅ |

**Final verified state:** 87 tests passing in both the project virtualenv and a
from-scratch virtualenv built only from `requirements.txt`; the app boots with
zero exceptions; the working tree is clean; no TODOs or placeholder code remain.

`main` is untouched. The four branches are pushed but unmerged, so merging
directly or opening pull requests for the record is still an open choice.

---

## 2. What is verified, and what is not

Honesty about testing matters more than a tidy report, so each claim below is
labelled with how it was established.

### VERIFIED — by automated tests (87 tests, run offline)

- Page-accurate text extraction and chunking; no chunk spans two pages
- Source and page metadata survive embedding, indexing and retrieval
- Multi-document indexing and cross-document retrieval
- Citation formatting and prompt construction
- Failure translation for every handled error path
- Upload size validation and corrupt-file handling
- `app.py` starts and renders both tabs, with Ollama both up and down

### VERIFIED — by live runs against real software

| What | How it was checked | Result |
|---|---|---|
| Full RAG pipeline with real models | Real `nomic-embed-text` embeddings, real `llama3` generation, two PDFs in one index | Correct file **and** page cited on both test questions |
| Multi-document routing | Two questions, each answerable by only one of two PDFs | Each retrieved from the correct document |
| Inline citation markers | Inspected generated answers | Model emitted `[1]` markers as instructed |
| Refusal behaviour | Asked "What is the capital of Japan?" over unrelated PDFs | *"I couldn't find that information in the document."* |
| OCR on a scanned document | Built a genuinely image-only PDF (a picture of text, no text layer) and ran the real pipeline with Tesseract 5.4.0 | Both pages read **character-for-character correctly**, page numbers preserved |
| OCR degradation | Same file with OCR disabled | Recovered nothing, as intended — no crash |
| Clean-machine install | Fresh virtualenv from `requirements.txt` alone | All 87 tests pass |

### NOT VERIFIED

- **`docker compose up` has never been run.** Docker is not installed on the
  development machine. The compose file parses and the service wiring is
  reasoned through, but the image has never been built. This is the single
  remaining untested part of the project.
- **The demo video has not been recorded.**

---

## 3. Measured performance

Real numbers from the live runs, suitable for quoting in the thesis.

### Retrieval and generation (llama3, CPU)

| Stage | Cold | Warm |
|---|---|---|
| Indexing 2 small PDFs (real embeddings) | 6.1 s | — |
| Retrieval (embed question + FAISS search) | 0.03 s | 0.03 s |
| Time to first token | 7.8 s | 0.2 s |
| Full answer | 8.1 s | 0.5 s |

The cold/warm gap is entirely `llama3` loading into RAM.
**Practical consequence for the defense:** ask one throwaway question before the
committee arrives, so the model is warm and answers arrive in under a second.

### OCR

| Metric | Value |
|---|---|
| Rendering + OCR per page (300 DPI) | ~0.55 s |
| Accuracy on clean rendered text | character-for-character correct |

---

## 4. Environment setup — gotchas found the hard way

Two installers on this machine did **not** add themselves to the Windows PATH.
Both produced the same confusing symptom: the program is installed, but the
terminal says *"the term is not recognized"*.

| Program | Real location | Fix applied |
|---|---|---|
| Ollama | `%LOCALAPPDATA%\Programs\Ollama` | Added to user PATH |
| Tesseract | `C:\Program Files\Tesseract-OCR` | Added to user PATH |

**Important:** a PATH change only reaches **newly opened** terminals. An existing
window keeps the old PATH until it is closed and reopened.

Two related notes:

- `Error: listen tcp 127.0.0.1:11434: bind: Only one usage of each socket
  address...` does **not** mean something is broken. It means Ollama is *already
  running*. Check with `ollama ps` before starting the server; if it prints a
  table, skip `ollama serve` entirely.
- The user PATH contains a pre-existing broken entry, `C:\Users\Davchev\AppDa`,
  a truncated fragment. Harmless — Windows ignores folders that do not exist —
  but worth cleaning up via *Settings → Environment Variables*.

### What must be installed

| Component | Required? | Purpose |
|---|---|---|
| Python 3.12 | **Yes** | Runs the app |
| Ollama | **Yes** | The local AI runtime |
| `nomic-embed-text` (0.27 GB) | **Yes** | Converts text to vectors. **Cannot be replaced by a chat model** |
| `llama3` (4.7 GB) | **Yes** | Answers PDF questions. Swappable for another text model in `rag_chain.py` |
| `llava` (4.7 GB) | Only for the image chat tab | Vision model |
| Tesseract | Optional | Scanned PDFs only |
| Docker | Optional | The one-command setup path |

---

## 5. What was built, phase by phase

### Phase 1 — Source citations, multi-document support, test suite

**In plain terms:** the app can now tell you *where* an answer came from. Every
piece of text extracted from a PDF remembers which file and which page it came
from, all the way through to the answer. Several PDFs can be loaded at once and
questioned together.

**How citations were made honest.** Previously the app joined the whole PDF into
one long stream and cut it into pieces, so a piece could begin on page 3 and end
on page 4 — leaving no truthful page number to cite. Now each page is split
independently, guaranteeing every piece belongs to exactly one page. Answers
carry markers like `[1]`, and a **Sources** panel underneath shows
`[1] report.pdf, p. 4` together with the exact text the model was given.

**Files:** `pdf_handler.py`, `vector_store.py`, `rag_chain.py`, `app.py`,
`requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `tests/`, `README.md`

**Tests:** 34 written, 34 passing. They run with no Ollama and no model
downloaded — the AI components are replaced by predictable stand-ins, so the
real search machinery still executes but no server is needed.

**Problems solved:** the fake embedding stand-in was initially not recognised by
the search library (fixed by making it a proper subclass); one test failed
because the text `[2]` appeared in the prompt's *instructions* rather than its
content (fixed by narrowing the assertion to the content section).

**Commit:** `fb7ddcf9`

---

### Phase 2 — Graceful errors, Docker, app-boot tests

**In plain terms:** the app no longer shows Python crash text. The four things
that actually go wrong each produce a plain message stating what broke *and* the
command that fixes it. Both tabs also check the setup *before* anything is
uploaded, so a misconfiguration is visible immediately rather than after a long
wait.

**Docker.** `docker compose up` is intended to be the entire setup: it starts
Ollama, downloads the models into a cache that survives restarts, waits until
they are genuinely present, then starts the app.

**Files:** `errors.py` (new), `app.py`, `llm_chain.py`, `Dockerfile` (new),
`docker-compose.yml` (new), `.dockerignore` (new), `README.md`

**Tests:** 66 total, 66 passing — including tests that boot the *real* `app.py`
through Streamlit's own script runner.

**Bug caught by those tests:** `llm_chain.py` was building its model with a
LangChain class that is deprecated and scheduled for deletion, printing a
warning on every start. Replaced with the current class.

**Technical finding worth mentioning at the defense:** Ollama reports "server is
down" as *two different exception types* depending on how it is called — a plain
`ConnectionError` from `list()`, but a raw `httpx.ConnectError` from a streaming
chat, because the streaming call connects lazily during iteration. This was
discovered by stopping the server and probing the real client, not by reading
documentation. Both now map to one message.

**Commit:** `e6a3486b`

---

### Phase 3 — Write-up

Two documents for the thesis itself.

**`DECISIONS.md`** — 15 entries, each stating the decision, the alternatives
considered, and why this one won. Entries 6–9 answer the three questions the
roadmap predicted a committee would ask (why FAISS rather than Chroma, why
Ollama rather than llama.cpp, why the index is not saved to disk). Those are
marked **(reconstructed)**, because they were decided before the log existed and
should not be presented as notes written at the time.

**`docs/architecture.md`** — the architecture chapter draft: system overview,
component structure and its acyclic dependency graph, the ingestion / retrieval
/ generation pipeline, the citation mechanism, error-handling design, testing
strategy, deployment topology, and a limitations table with proposed
resolutions.

**Commit:** `fb3098eb`

---

### Phase 4 — OCR for scanned PDFs

**In plain terms:** scanned PDFs — photographs of pages, containing no real text
— can now be read using Tesseract, *if it is installed*. If it is not, the app
says so and gives the install command for the operating system in use, and
ordinary PDFs continue to work untouched.

**A detail that matters for accuracy.** The trigger is not "this page has no
text" but "this page has fewer than 20 characters". Scanned pages frequently
carry a stray page number or header artefact, so a strict zero-text check would
miss them.

**Three problems, three messages:** scanned but no Tesseract (install it),
scanned but OCR read nothing (re-scan at higher quality), and genuinely empty
(check the file). A document needing OCR on more than 50 pages is refused up
front rather than starting a multi-minute wait.

**Files:** `ocr.py` (new), `pdf_handler.py`, `errors.py`, `app.py`, `Dockerfile`
(now installs Tesseract), `requirements.txt`, `tests/conftest.py`,
`tests/test_ocr.py` (new), `README.md`, `DECISIONS.md`

**Tests:** 87 total, 87 passing. A rule was added forcing OCR off during tests
unless a test explicitly enables it — otherwise results would differ depending
on whether the machine happens to have Tesseract, which would make the suite
worthless as evidence.

**Commit:** `50207cbb`

---

## 6. Final architecture

A Streamlit user interface on top of five small modules, one per pipeline stage:

- **`pdf_handler`** — PDF → per-page text → chunks tagged with source and page
- **`vector_store`** — chunks → FAISS index → similarity retrieval
- **`rag_chain`** — retrieved chunks → cited prompt → streamed answer
- **`ocr`** — optional Tesseract fallback for pages without a text layer
- **`errors`** — turns failures into readable messages, and pre-flight checks

Nothing depends on `app.py`, which is why the entire pipeline is testable
without the user interface.

## 7. Known limitations

All documented in `docs/architecture.md`:

- No evaluation of answer *quality* — correctness of retrieval is untested at
  scale (see idea 1 below)
- FAISS cannot cheaply delete, so removing a file from the uploader does not
  un-index it; the Clear button is the reset
- The index is not saved between sessions, so documents are re-indexed each time
- `langchain-community`'s FAISS import is being retired upstream, with no
  drop-in replacement package yet

---

## 8. Ideas to improve the thesis

**1. Retrieval accuracy evaluation** *(the important one)*
Write ~30 questions over a known document, record which page truly answers each,
then measure how often the correct page appears in the top *k*.
*Why:* the project currently proves citations work **mechanically**. It does not
show how **often** the right page is retrieved. This converts a qualitative
claim into a measured one. *Difficulty:* medium. **Essential.**
*Measured by:* precision@k, recall@k, mean reciprocal rank.

**2. Chunk-size sweep**
Re-run evaluation 1 at chunk sizes 250/500/1000 and overlaps 0/50/100.
*Why:* 500/50 is currently an unjustified default, and "why 500?" is an easy
question to ask. *Difficulty:* easy once 1 exists. **High value per hour.**

**3. Latency measurements**
Partly done — see section 3. Extend across several document sizes.
*Why:* gives a performance section with real numbers. *Difficulty:* easy.
**Optional.**

**4. Compare embedding models**
Run evaluation 1 with `nomic-embed-text` vs `mxbai-embed-large` vs `all-minilm`.
*Why:* "why this embedding model?" becomes answerable with evidence.
*Difficulty:* medium. **Optional.**

**5. Citation faithfulness check**
Sample answers and check whether each cited `[n]` genuinely supports the
sentence. *Why:* models can cite plausibly but wrongly; measuring this is more
interesting than retrieval alone and is an active research topic.
*Difficulty:* medium, needs manual scoring. **Optional, high academic value.**

**6. Continuous integration**
A GitHub Actions workflow running the 87 tests on push. *Why:* the suite already
runs without Ollama, so CI is nearly free, and a green badge is concrete
evidence of discipline. *Difficulty:* trivial. **Recommended.**

**7. Baseline comparison — RAG vs no RAG**
Ask the same questions with and without retrieved context. *Why:* demonstrates
the retrieval is doing the work rather than the model already knowing.
*Difficulty:* easy given 1. **Recommended.**

**8. Structured logging**
Log retrieval scores, chunk counts and latencies. *Why:* it is how the data for
ideas 1–4 gets collected. *Difficulty:* easy. **Optional.**

**Not recommended:** user accounts, a database, a REST API, or a rewritten
frontend. They add code without strengthening the thesis and dilute the
local-first premise that makes the project coherent.

---

# What You Need to Test

Start every test from here:

```powershell
cd C:\Users\Davchev\Projects\DocuMind-AI
git checkout phase-04-ocr-fallback
```

That branch contains all four phases. **Do this first**, or you will be testing
an older version.

> **Before starting:** run `ollama ps`. If it prints a table, Ollama is already
> running — skip `ollama serve`. If it says it cannot connect, run
> `ollama serve` in its own window.

---

## Test 1 — The app runs and gives a cited answer

**Why we are testing this:** this is the core of the project. The pipeline has
been verified programmatically, but not by clicking through the real interface,
and a browser can surface problems a script cannot.

**Where:** a terminal, then a browser.

**Command:**

```powershell
cd C:\Users\Davchev\Projects\DocuMind-AI
venv\Scripts\activate
streamlit run app.py
```

**What to do:**

1. Open `http://localhost:8501` if the browser does not open by itself.
2. Click the **📄 PDF Q&A** tab.
3. Confirm a green **✅ System ready** box appears. Expand it — it should
   confirm Ollama is running with `llama3` and `nomic-embed-text` installed.
4. Click **Browse files** and upload a PDF containing real text — a lecture
   PDF, a paper, anything whose text you can select with the mouse. Not a scan.
5. Wait for the green **"✅ *yourfile.pdf* indexed — N chunks created"**.
6. In the box at the bottom, type a question you already know the answer to from
   that PDF, for example `What is the deadline?`, and press Enter.
7. Click the grey **📚 Sources** bar beneath the answer.

**What you should see:** the answer appearing word by word, containing a marker
such as `[1]`. The Sources panel lists `[1] yourfile.pdf, p. 3` followed by the
actual passage.

**Expected result:** open your PDF at the page named in Sources. **The quoted
text must genuinely be on that page.** If the page number is right, citations
work.

**If it fails:** send (a) the question, (b) the full answer, (c) what Sources
said, (d) the page the text is really on.

---

## Test 2 — Error test: Ollama not running

**Why we are testing this:** proves an examiner on a fresh machine gets a helpful
message rather than a crash.

**What to do:**

1. Quit Ollama completely — right-click its icon in the system tray, near the
   clock, and choose Quit. Close any `ollama serve` window.
2. Run `streamlit run app.py` and open the **📄 PDF Q&A** tab.

**What you should see:** an already-expanded orange **⚠️ Setup needed** box:

> **Ollama isn't running.** This app talks to a local Ollama server and can't
> reach one at `http://localhost:11434`.
> Start it with `ollama serve` (or launch the Ollama desktop app), then try again.

**Expected result:** that message and nothing else — **no red Python error text,
no line containing "Traceback" or "httpx"**.

3. Start Ollama again, return to the browser and click **🔄 Re-check**.

**Expected result:** the orange box becomes a green **✅ System ready** box.

**If it fails:** screenshot the whole page.

---

## Test 3 — Error test: model not downloaded

**Why we are testing this:** the second most likely first-run problem.

> **Skip this test on limited internet** — it deletes a 4.7 GB model you must
> then re-download.

**Command:**

```powershell
ollama rm llama3
```

**What to do:** restart the app and open the **📄 PDF Q&A** tab.

**What you should see:**

> **The model `llama3` isn't installed.** Ollama is running, but this model
> hasn't been downloaded yet.
> Pull it with `ollama pull llama3` — then reload this page.

**Expected result:** the message names the *exact* missing model and the exact
command.

**Afterwards, restore it:**

```powershell
ollama pull llama3
```

---

## Test 4 — Error test: a broken file

**Why we are testing this:** proves a corrupt upload does not crash the app.

**What to do:**

1. Open Notepad, type `this is not really a pdf`, and save it to your Desktop as
   `broken.pdf`. In the Save dialog set *Save as type* to **All Files**, or
   Notepad will append `.txt`.
2. Upload `broken.pdf` in the **📄 PDF Q&A** tab.

**What you should see:**

> **broken.pdf couldn't be read.** The file appears to be corrupt,
> password-protected, or not a PDF.

**Expected result:** that message, **and the app keeps working** — you can
upload a good PDF immediately afterwards without restarting.

---

## Test 5 — Edge case: several PDFs at once

**Why we are testing this:** proves multi-document search picks the right *file*,
not merely the right page.

**What to do:**

1. Find two clearly different PDFs — one on your thesis topic, one unrelated
   (a manual, an invoice, a recipe).
2. Click Browse and select **both** at once (Ctrl-click).
3. Wait for two green "indexed" messages and a blue box listing both filenames.
4. Ask a question only the **first** PDF could answer. Open **📚 Sources**.
5. Ask a question only the **second** PDF could answer. Open **📚 Sources**.

**Expected result:** each answer's Sources names the correct file. Different
questions pull from different documents, and each states which.

---

## Test 6 — Edge case: a scanned PDF

**Why we are testing this:** exercises the OCR path. Tesseract 5.4.0 is already
installed and this has been verified with a synthetic scan; this confirms it
with a **real** one.

**What to do:**

1. Obtain a scanned PDF — photograph or scan a printed page, or find one whose
   text you **cannot** select with the mouse in a PDF reader.
2. Restart the app and look at the small grey line under the System-check box in
   the PDF tab.
3. Upload the scanned PDF and ask about something visible on it.

**What you should see:** the grey line should read
**"OCR is available (Tesseract 5.4.0.20240606) — scanned PDFs are supported."**

**Expected result:** the file indexes and answers with a page citation. OCR is
not perfect on real-world scans — judge it as "mostly right", not "flawless".
Poor lighting, skew, or low resolution will degrade it.

**If it fails:** report what the grey OCR line said and whether the file indexed.

---

## Test 7 — The automated test suite

**Why we are testing this:** confirms on your machine what was verified
elsewhere. This is also the evidence of engineering discipline to show a
committee.

**Ollama does not need to be running** — that is the point.

**Command:**

```powershell
cd C:\Users\Davchev\Projects\DocuMind-AI
venv\Scripts\activate
pytest
```

**Expected result:**

```
87 passed, 1 warning in 4.02s
```

**87 passed, zero failures.** The single warning concerns `langchain-community`
being retired upstream — expected, and documented as known technical debt.

Use `pytest -v` to see individual test names instead of dots.

**If it fails:** copy the whole output, especially any line beginning `FAILED`.

---

## Test 8 — Docker *(the only completely unverified part)*

**Why we are testing this:** it is the one-command setup and the insurance
policy if the defense happens on another machine. It has never been run.

**What to do:**

1. Install Docker Desktop from `https://www.docker.com/products/docker-desktop/`,
   start it, and wait until the whale icon reports "running".
2. Run:

```powershell
cd C:\Users\Davchev\Projects\DocuMind-AI
docker compose up
```

3. Wait. **The first run downloads about 6 GB of models — expect 10–30 minutes.**
   A great deal of text will scroll past; this is normal.

**What you should see, in order:**

1. Docker building the app image
2. `documind-ollama` starting
3. `documind-model-init` showing download progress for the three models
4. `documind-model-init` exiting
5. `documind-app` printing `You can now view your Streamlit app`

4. Open `http://localhost:8501`.

**Expected result:** the app loads, shows **✅ System ready**, and the grey line
reports **OCR is available** (the image bundles Tesseract). Upload a PDF and ask
a question — it should behave exactly as in Test 1.

5. Verify the model cache: press `Ctrl+C`, then run `docker compose up` again.

**Expected result:** the second start takes **seconds, not minutes**. It must
**not** re-download 6 GB. If it does, the volume is not working.

6. Clean up with `docker compose down`.

**If it fails:** send the **last 30 lines** of output and say which of the five
stages it stopped at. This is the part most likely to need a fix.

---

## Test 9 — Performance

**Why we are testing this:** produces real numbers for the thesis, and confirms
the figures in section 3 on your hardware.

**What to do:**

1. Note a PDF's page count.
2. Time, with a phone, from the moment the spinner appears to the green
   "indexed" message.
3. Ask a question and time from pressing Enter to the first word appearing.
4. Ask a **second** question and time it again.

**Expected result:** roughly 10–30 s indexing for a 10–20 page document; the
first question slower than the second, because the model loads into RAM on
first use. Section 3 measured 7.8 s cold versus 0.2 s warm.

**Record:** pages, indexing seconds, first-question and second-question times.

---

## Test 10 — Security and privacy

**Why we are testing this:** "100 % local, nothing leaves your machine" is the
project's central claim. This proves it.

**What to do:**

1. Start the app and upload a PDF.
2. **Disconnect from the internet** — switch off Wi-Fi or unplug the cable.
3. Ask a question about the PDF.

**Expected result:** it works **exactly the same**, with citations, with no
internet connection.

**Why this proves the claim:** if any document text were being sent anywhere,
this would fail. It does not.

**This is the single most convincing demonstration available, and it takes ten
seconds — consider doing it live at the defense.**

---

## Test 11 — Final end-to-end run (demo rehearsal)

**Why we are testing this:** this is the defense demo, start to finish. Run it
exactly as it will be run in front of the committee.

**What to do:**

1. **Restart the computer**, so nothing is left running from earlier.
2. Start Ollama (tray app, or `ollama serve`).
3. Run:

```powershell
cd C:\Users\Davchev\Projects\DocuMind-AI
venv\Scripts\activate
streamlit run app.py
```

4. In the **🤖 Chat** tab, upload an image in the sidebar and ask
   `What is in this image?`
   → *Expected:* a description streaming in word by word.
5. Switch to **📄 PDF Q&A**. Point out the **✅ System ready** panel — the
   "setup is verified" moment.
6. Upload **two** PDFs at once.
7. Ask a question answered by the first. Open **📚 Sources** and read out the
   file and page.
8. **Open that PDF at that page and show the committee the sentence is really
   there.** This is the strongest moment of the demo — the claim is verifiable
   in real time.
9. Ask a question answered by the second document. Show Sources now names the
   other file.
10. Ask something the documents do not cover, e.g. `What is the capital of Japan?`
    → *Expected:* *"I couldn't find that information in the document."* It
    refuses to invent an answer. Show this deliberately; it demonstrates the
    system's honesty.
11. Switch off Wi-Fi and ask one more question (Test 10). It still works.
12. Click **🗑️ Clear PDFs & Chat** and confirm everything resets.

**Expected result:** all twelve steps without a single red error message.

**Tip:** ask one throwaway question before the committee enters, so `llama3` is
warm and answers arrive in roughly half a second instead of eight.

**If any step fails:** report the step number, what you did, what you expected,
what appeared, and a screenshot.
