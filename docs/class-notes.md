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
