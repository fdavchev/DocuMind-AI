# Class notes

Plain-language notes on each class introduced during the object-oriented
refactor: what it does, why it is built that way, and what it demonstrates.

## AppConfig (`documind/config.py`)

`AppConfig` is a small object that holds every setting the application runs on —
the title shown in the browser tab, which Ollama models are used for chat, for
images, for answering document questions and for turning text into vectors, how
large a PDF chunk is, how many chunks a question retrieves, how creative and how
long an answer may be, the assistant's system prompt, and the page limit for
OCR. The app builds exactly one of these at startup and hands it to every step
of the pipeline, so no module has to reach out to a global variable to discover
how it should behave.

It is a *frozen dataclass* rather than a file full of constants for two reasons.
Frozen means the values cannot be changed once the object exists, so a config
shared by five modules can never be quietly altered by one of them; and because
it is an object rather than a module, a caller can create a different one —
`AppConfig(chunk_size=100)` — and hand it in without editing any source file.
The tests already use this: the OCR page-limit tests now pass in a config with a
limit of one or two pages instead of monkeypatching a module constant, which is
shorter and far less fragile.

Honestly, this class is not a showcase of a classic principle like inheritance
or polymorphism — it is about *dependency injection* and testability. The
settings are no longer something the code goes and fetches for itself; they are
something the code is given. That is the foundation the rest of this refactor
builds on: every class added in the following steps receives an `AppConfig`
instead of importing constants, so each one can be created, configured and
tested on its own.

Building it also fixed a real bug. `TEMPERATURE`, `MAX_TOKENS` and
`SYSTEM_PROMPT` existed in the old `config.py` but no code ever read them, so
editing them did nothing at all. They now reach Ollama for real — as the
`temperature` and `num_predict` settings on the chat model, and as the system
message in front of every image conversation.

## Document, ExtractedPage and Chunk (`documind/documents/models.py`)

These three frozen dataclasses are the things the document pipeline passes
around. An `ExtractedPage` is one page after extraction — its 1-based number,
its text, whether it had to be read by OCR, and a reserved slot for an OCR
confidence score a later phase can fill in. A `Document` is a whole uploaded
file: its name plus a tuple of those pages, with small read-only properties for
the questions the app actually asks (`text`, `page_count`, `ocr_page_count`,
`is_empty`). A `Chunk` is one passage small enough to embed, carrying the page
number and the source filename it came from.

They replace two shapes that carried the same information without naming it.
Extraction used to return `(page_number, page_text)` tuples, where nothing tells
a reader which element is which, and chunking used to return LangChain
`Document` objects with `metadata={"source": ..., "page": ...}`, where a
misspelled key fails silently at retrieval time instead of loudly where it was
written. Named fields cannot be misread or misspelled without an error, and
they can be extended — which is exactly why the OCR flag could be added to
every page in this step without any caller noticing, when the tuple version had
nowhere to put it.

This is the thesis's *value objects* row: small immutable objects that describe
data rather than do work. `Chunk` carries a page number so the app can answer
"according to page 7" — a measurable, demoable thing the earliest version of
this project threw away by concatenating a whole PDF into one string. That
citation path is still intact: the end-to-end test indexes two PDFs, asks a
question, and asserts the prompt and the Sources panel both say
`[1] handbook.pdf, p. 3`.

The one seam worth pointing at is `vector_store._as_documents`. FAISS only
understands LangChain's `page_content` plus a metadata dictionary, so a `Chunk`
is flattened into that dictionary at the moment it is stored and read back out
of it when a citation is formatted. Keeping that translation in one function
means the rest of the pipeline never handles a raw metadata key — the
dictionary now exists only inside the library boundary that requires it.

## Message and ChatSession (`documind/chat/`)

A `Message` is one turn of a conversation — who spoke, what was said, and when.
A `ChatSession` is the conversation itself: it keeps the messages in order, adds
one at a time through `add_user` and `add_assistant`, forgets them all through
`clear`, reports whether anything has been said yet through `is_empty`, and
writes the plain-text transcript the sidebar's "Save chat" button downloads
through `export`. The app builds exactly one of these at startup, stores it in
Streamlit's session state, and every part of the chat tab — the bubbles on
screen, the prompt sent to Ollama, the download button — reads from that one
object.

The list of messages is private, and `messages` hands back a tuple rather than
the list. Those two details are the whole point. A tuple cannot be appended to,
and because a fresh one is built on every read, a caller that does mutate what
it was given is mutating its own copy: the conversation is unchanged. So the
only way a message can enter a `ChatSession` is through one of the two methods
that add one, and the only way one can leave is `clear`. The session can never
be found in a state it did not put itself into.

This is the thesis's *encapsulation* exhibit, and the contrast with what it
replaced is exact. The old `chat_history.py` had no object at all: the
conversation was a plain `list` of `{"role": ..., "content": ...}` dictionaries
that `app.py` held and passed into every function. `add_message(history, role,
content)` would accept *any* list — the wrong conversation, an empty one, a list
of integers — and append to it without complaint. Every caller holding that list
could append to it, reorder it, delete a message the user had already seen, or
edit an answer after it was displayed, and nothing anywhere would raise. The
data was public and the functions were merely conventions for touching it.
Moving the list inside `ChatSession` turns those conventions into the only
available operations.

The tests state the claim rather than describe it:
`test_mutating_what_messages_returned_does_not_change_the_session` copies the
messages out, appends to the copy and clears it, then asserts the session still
holds its two original messages, and
`test_a_session_cannot_be_handed_an_existing_conversation` asserts the
constructor takes nothing but a system prompt. The export format was carried
over character for character from the old
`export_history`, and is pinned by a test comparing against the exact expected
string, so the user-facing download is provably unchanged by the refactor.

## LLMProvider and OllamaProvider (`documind/llm/`)

`LLMProvider` states the four things this application ever asks of a language
model — say whether you can answer right now, continue a conversation, look at
an image, and answer one already-written prompt — and says nothing about where
that model lives. `OllamaProvider` is the one implementation: it talks to the
local Ollama server, sending chat to whichever model the sidebar selected,
images to llava because it is the only model here that can see one, and document
answers to llama3. It replaces `llm_chain.py` entirely and absorbs the
`ollama.chat` call `rag_chain.py` used to make itself, so every call to a model
in the whole project now leaves from one file.

Writing an abstract base class for a single implementation looks like ceremony
until you try to test the thing. Ollama is a server that has to be running and a
multi-gigabyte model that has to be pulled, and its answers are different every
time — none of which belongs in a test suite. Because every caller is written
against the four method names rather than against Ollama, a stand-in that
returns canned tokens is accepted everywhere the real provider is: the new
`tests/test_ollama_provider.py` pins all four paths — which model each one uses,
the exact prompt and options sent, the JPEG conversion, the empty tokens
skipped — in 18 tests, and the whole 137-test suite still runs with no Ollama
process anywhere. The abstract methods are what make that promise enforceable:
the last two tests in that file build a stand-in provider and then show that a
subclass which forgets a method cannot be instantiated at all.

This is the thesis's *abstraction and strategy pattern* exhibit. The strategy —
how an answer is actually produced — sits behind a fixed interface, and choosing
a different one is a constructor argument rather than a rewrite. Swapping Ollama
for a hosted API or a different local runtime means writing one new class with
those four methods and changing the single line in `app.py` that builds the
provider; `rag_chain.py`, the chat loop and the image path would not change by a
character, because none of them imports `ollama` any more.

## DocumentLoader, PdfLoader and TextLoader (`documind/documents/`)

`DocumentLoader` says what it means to read an uploaded file into a `Document`,
without saying anything about what kind of file it is. Its `load()` method does
the work that is the same whatever was uploaded: check the extension is one this
loader handles, ask for the pages, wrap them in a `Document` named after the
upload, and refuse a file that turned out to contain no text. The one step it
does not do itself is the extraction, which is declared abstract — so `load()`
is written once on the base class and the two subclasses supply only the step
that is genuinely their own. `PdfLoader` reads a PDF page by page and falls back
to OCR on pages with no text layer; `TextLoader` decodes a `.txt` or `.md` file
and calls the whole thing page 1.

This is the *template method* pattern, and it is the clearest inheritance
example in the project. A new loader — for `.docx`, say — is one class with one
method; it cannot forget to validate the extension, cannot name the document
differently, and cannot return an empty `Document` to a caller that was not
expecting one, because it never writes that code. Contrast it with the old
`pdf_handler.extract_pages_from_pdf`: a module-level function, so a second
format would have meant a second function with its own copy of the checks, and
whatever called it would need an `if` deciding which one to call.

Building a second loader was a deliberate decision rather than a feature the app
asked for. One subclass cannot demonstrate polymorphism, it can only assert it —
with two, the claim becomes something the tests check: the same `load()` call
serves a scanned PDF and a plain text file, and `test_both_loaders_*` runs the
identical assertions over both loaders in one loop, which is only possible
because nothing in those tests knows which kind of file it is holding.
`TextLoader` tries UTF-8 first and falls back to Windows-1251, which is what
older Macedonian documents were written in; those bytes are not valid UTF-8, so
the first attempt raises instead of producing nonsense, which is what makes
trying them in that order safe.

The OCR logic moved into `PdfLoader` unchanged — the same 20-character threshold
for "this page has no real text layer", the same refusal of a document needing
OCR on more pages than `AppConfig.max_ocr_pages`. `PdfLoader` calls the
functions in `ocr.py` directly rather than through a wrapper class, because
whether Tesseract is installed is a fact about the machine, not a choice between
strategies, and a class around two functions would add a name without adding a
decision. The two new failure cases, `EmptyDocumentError` and
`UnsupportedFileError`, were added to the existing hierarchy in `errors.py` as
`FriendlyError` subclasses, so `app.py`'s one "catch a friendly error, render
its message and hint" handler already covers them without a line of new UI code.
