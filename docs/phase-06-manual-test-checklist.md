# Phase 6 — manual pre-merge test checklist

Run this before merging `phase-06-oop-refactor`. Automated coverage (227 pytest
tests + a headless streamlit boot) already passed during the refactor, but
nothing in that automated pass talked to a real Ollama model end-to-end. This
checklist exercises exactly that gap.

## 1. Start Ollama and confirm the models this app needs are pulled

Open a terminal and run:

```powershell
ollama serve
```

Leave that running. In a **second** terminal, confirm every model
`AppConfig` expects is installed:

```powershell
ollama list
```

You need to see all of these in the list (pull any that are missing):

```powershell
ollama pull llama3
ollama pull mistral
ollama pull phi3
ollama pull llava
ollama pull nomic-embed-text
```

- `llama3` — answers PDF questions
- `llava` — default chat model, and the only one that reads images
- `mistral`, `phi3` — the other chat-mode options in the sidebar dropdown
- `nomic-embed-text` — turns text into vectors for the PDF search index

## 2. Start the app

In the project folder (`c:\Users\Davchev\Projects\DocuMind-AI`), run:

```powershell
.\run.ps1
```

This activates the project's venv and starts Streamlit with the right
interpreter. It should open a browser tab at `http://localhost:8501`.

If it fails immediately with "No virtualenv found", the venv doesn't exist
yet — that's a separate setup issue, not something this checklist covers.

## 3. Sidebar — system check

- Look at the **⚙️ Settings** panel in the sidebar. It should say
  **✅ System ready**, listing `llama3, mistral, phi3, llava,
  nomic-embed-text`.
- If it instead says **⚠️ Setup needed**, click **🔄 Re-check** after fixing
  whatever it names (usually a model that didn't finish pulling).

## 4. Chat mode

Mode selector at the top should default to **🤖 Chat**.

1. Type a plain question (e.g. "What's 2+2?") and press enter.
   Confirm the answer **streams** in (appears token by token, not all at once).
2. In the sidebar, under **🖼️ Image input**, upload any `.png`/`.jpg`.
   Ask a question about it (e.g. "What's in this image?").
   Confirm the answer references the image — this exercises `stream_vision`,
   which is new plumbing from item 4/10.
3. In the sidebar, switch **Chat model** to `mistral`, then ask another
   question. Confirm you get a toast ("Switched to mistral") and the answer
   still streams normally. This exercises the provider-rebuild code in
   `app.py`.
4. Click **🗑️ Clear chat**. Confirm the conversation empties.
5. Ask one more question so there's something to export, then click
   **💾 Save chat**. Open the downloaded `.txt` file and confirm it contains
   the conversation.

## 5. PDF Q&A mode — the highest-risk area

Switch the mode selector to **📄 PDF Q&A**. This area changed the most in
items 5–10 (three files were deleted here), so it's worth the most attention.

1. Upload one normal, text-based PDF.
   - Confirm the success message shows real numbers, not placeholders:
     `✅ <filename> indexed — N page(s), M chunks in T.Ts.`
     (page count, chunk count, and timing come from the new `IngestReport`
     dataclass, which had never run against a real file before this).
2. Ask a question the PDF can answer.
   - Confirm the answer streams.
   - Open the **📚 Sources** expander under the answer and confirm it shows
     the filename and a page number that's actually correct for that answer.
3. Upload a **second**, different PDF (with the first one still indexed).
   - Confirm the "Answering from:" line lists both filenames.
   - Ask a question that only the second PDF can answer, and confirm the
     Sources panel cites the second file — this exercises multi-document
     retrieval (the `k` widening from 4 to 6 chunks).
4. If you have a **scanned/image-only PDF** handy, upload it.
   - If it has no OCR-recoverable text at all, you'll get an error message
     instead of a success line. Confirm it's a plain, readable sentence —
     not a Python traceback. (This is the one deliberately-changed behavior
     from item 10: the old message distinguished "scanned, OCR unavailable"
     from "genuinely blank"; now both say roughly the same thing. Confirm
     it's still *usable*, not that it's identical to before.)
5. Click **🗑️ Clear documents & chat**.
   - Confirm the document list empties and the input placeholder goes back
     to "Upload a PDF above to start asking questions..." (disabled state).

## 6. Error handling — stop Ollama mid-session

1. Go back to the terminal running `ollama serve` and stop it (Ctrl+C).
2. In the app (either mode), ask a question.
   - Confirm you get a friendly error message (something like "Can't reach
     Ollama — is it running?"), not a raw exception or a frozen spinner.
3. Restart `ollama serve` and confirm the app recovers (re-check system
   status, or just ask another question).

## If all of this behaves

You're good to merge. Nothing above is expected to fail based on the
automated verification already done during the refactor — this checklist
exists to catch the one category of bug that pytest and a headless boot
structurally cannot: a real model producing a real (or malformed) response
through the actual UI wiring.

## If something breaks

Note exactly which step, the mode you were in, and the full error text
Streamlit shows (expand any "Show traceback" link). Bring that back and it
can be diagnosed before merging — better to catch it here than after this
branch is in `main`.
