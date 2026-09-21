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
