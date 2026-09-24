# Two retrieval bugs: document-metadata questions, and Macedonian retrieval

**Date:** 2026-09-24
**Branch:** `fix/09-embedding-batches`

## 1. Questions about a document's own title/authors failed

**Symptom:** asking "What is the title of this paper?" of
`2609.28470v1.pdf` (uploaded and correctly indexed) returned *"I couldn't
find the title of the paper in the provided document context."*

**Cause:** `ask()` only sends the top-4 chunks by embedding similarity to
the LLM. A question like "what's the title" barely matches the title chunk
semantically, but matches the paper's own bibliography (a list of other
papers' titles) well. In the reproduction, the title chunk ranked 228th of
379 chunks and never reached the prompt. **VERIFIED by live run** against
the real Ollama pipeline.

**Fix:** three changes, all landed and uncommitted on this branch:
1. **Primary — document-level context independent of similarity search.**
   `rag_pipeline.py` now prepends a `DOCUMENT: <file> — Title: … — Authors:
   …` line per indexed document, read from PDF metadata and falling back to
   the first 200 characters of the first chunk if metadata is missing.
2. **nomic task prefixes.** `vector_store.py` wraps the real Ollama
   embeddings with `search_document:`/`search_query:` prefixes (the model's
   expected usage). Test-injected `FakeEmbeddings` are unaffected.
3. **Degenerate chunk filtering.** `text_splitter.py` now drops chunks with
   fewer than 3 letters (Cyrillic-aware), so near-empty chunks (e.g. a chunk
   that was just `)`) stop polluting retrieval.

Recorded in DECISIONS.md #19.

**Checks:**
- Full suite: 263 → 283 tests passing (20 new tests added). **VERIFIED by
  automated test.**
- Live check: the Title/Author line reaches the prompt even when the top-4
  retrieved chunks are still bibliography entries. **VERIFIED by live run.**
- End-to-end llama3 answer to the title question specifically was not
  re-checked at the time (Ollama was down mid-session) — confirmed later,
  see below.

**Known limits, not bugs:** a junk PDF `Title` property (e.g. "Microsoft
Word - x.docx") would be passed through as-is; a document made entirely of
number-only pages is now refused as empty (previously it silently indexed
nothing useful).

## 2. Macedonian-language retrieval was close to chance

**Symptom:** "Кој ја измислил кошарката и во која година?" against
`Кошарка.pdf` (native text, not scanned) returned *"I couldn't find that
information in the document."* even though the answer is on page 1 in plain
text. This was a **different, separate root cause** from bug #1 — not a
metadata question, so fixes 1–3 above didn't address it.

**Cause:** the embedding model, `nomic-embed-text`, is effectively
English-only. Its tokenizer has almost no Cyrillic vocabulary, so Macedonian
text is read close to letter-by-letter and the model can barely tell
Macedonian passages apart. Measured live across five of Filip's own
Macedonian eval questions, the correct chunk ranked 7, 23, 17, 5, 1 out of
~121 (only rank ≤4 reaches the LLM) — versus 1, 1, 1, 3 for English
questions on the same pipeline. **VERIFIED by live run.**

**Fix:** switched the embedding model.
- `ollama pull nomic-embed-text-v2-moe` (958MB, multilingual, same
  `search_query:`/`search_document:` prefix convention as v1 — confirmed
  against the model card, no prefix code change needed).
- `nomic-embed-text` removed locally (`ollama rm nomic-embed-text`) — nothing
  else in the codebase depends on it.
- `documind/config.py`, `errors.py` (model-readiness check),
  `docker-compose.yml`, `vector_store.py` comments, README.md,
  `docs/architecture.md`, and test fixtures updated to the new model name.
  Historical mentions in DECISIONS.md #5/#6/#19 and past project reports
  left untouched on purpose — they're records of what was true at the time.
- Recorded in DECISIONS.md #20.

**Checks:**
- Same five Macedonian questions re-ranked against the new model: **1, 2, 2,
  1, 1** — all now inside the top-4 that reaches the prompt. **VERIFIED by
  live run.**
- English questions spot-checked, no regression (ranks 1, 1, 1, 2, 2).
  **VERIFIED by live run.**
- Full end-to-end answers via llama3 on the Macedonian questions now come
  back correct (e.g. "Џејмс Нејсмит … 1891 [1]"). **VERIFIED by live run.**
- Full suite: 283 passed. **VERIFIED by automated test.**
- New model's 512-token-per-input limit checked against actual chunk sizes
  in this corpus (max ~230 tokens including prefix) — nothing gets
  truncated. **VERIFIED by live run.**

**Known limits, not bugs:**
- `docker-compose.yml`'s "~6 GB" download-size comment was already stale
  before this change (llama3 + llava alone are ~9.4GB) and is now ~10.4GB
  with the new embedding model. Not corrected — pre-existing inaccuracy,
  out of scope for this fix.
- `docs/phase-06-manual-test-checklist.md` still references
  `ollama pull nomic-embed-text` as a historical Phase 6 record — left
  alone; say if you want it updated too.
- A separate correctness bug, investigated but **not fixed** (see section 4
  below): asking "Каде Најсмит го развил кошарката?" got a wrong answer
  about where Naismith developed basketball.

## 3. llama3 answered Macedonian questions in English

**Symptom:** llama3 answered the first question in a Macedonian chat
correctly in Macedonian, then reverted to English on every question after
that in the same session.

**Cause, found by live reproduction (not theorized):** this was never a
session/history bug — confirmed the app builds each prompt fresh with no
carried-over state. llama3-8B simply defaults to English on this prompt
regardless of turn number: at temperature 0, it answered in English on
every run of every question, including the first. The earlier apparent
"Macedonian success" on turn 1 was a lucky high-temperature sampling draw,
because that answer happened to be a near-verbatim copy of an
already-Macedonian source passage. **VERIFIED by live run** (repeated
multi-turn sessions, and isolated prompt-variant testing at both
temperature 0.7 and temperature 0).

**Fix:**
- Detect the question's language by counting Cyrillic vs Latin letters
  (`documind/rag/rag_pipeline.py`, `_answer_language_for`).
- Insert an explicit, **language-specific** instruction directly before
  `ANSWER:` in the prompt (not a generic "match the question's language"
  line — that was tested and found to break English questions 5/8 of the
  time by flipping them to Macedonian).
- Translated the "I couldn't find that information" fallback sentence into
  Macedonian, selected by the same detection.
- New `AnswerLanguage` config type in `documind/config.py` holding both
  languages' instruction and fallback text.
- Recorded in DECISIONS.md #21.

**Checks:**
- 9 new unit tests (language detection, instruction placement, fallback
  text, no-letters and 50/50-split edge cases, config-driven text).
  **VERIFIED by automated test.**
- Full suite: 292 passed. **VERIFIED by automated test.**
- Live run against the real pipeline (Кошарка.pdf + Green City Accord
  ingested together, 3 repeats per question, 6 questions spanning both
  languages and both documents): **18/18 answers in the correct language.**
  **VERIFIED by live run.**
- Fallback sentence: Macedonian out-of-scope question got the Macedonian
  fallback sentence in 2/3 runs (the third run answered with wrong content
  but still in Macedonian, so not a language failure); English fallback
  came back correctly 3/3. **VERIFIED by live run** (not exhaustively).

## 4. Wrong answer to "Каде Најсмит го развил кошарката?" — investigated, not fixed

**Symptom:** this question gets a wrong answer about where Naismith
developed basketball (varies by run — sometimes Kansas, sometimes a
non-answer, sometimes correct).

**This turned out NOT to be the retrieval-ranking bug it looked like.**
Investigated live and root-caused to three compounding causes, none of
which has a clean fix yet:

1. **The correct answer sentence is split across two chunks** by
   `chunk_size=500`/`chunk_overlap=50` (`config.py:70-71`,
   `text_splitter.py:44`). The chunk that reaches the prompt only says
   Naismith was "an instructor" at the YMCA Training School — the chunk
   saying he *created the game* there ranks 13th and never reaches the
   model.
2. **A distractor chunk ranks #1** — a section heading "Ран развој"
   ("Early development") plus a Naismith/basketball mention echoes the
   question's wording closely enough to outrank the real answer.
3. **llama3-8B's Macedonian comprehension is the deciding factor**, not
   retrieval. With the retrieved context held constant, the identical
   question in English answered correctly 16/16; in Macedonian it failed
   most of the time. Wording matters a lot: some natural Macedonian
   phrasings of the same question scored 16/16 correct, others 0/16 —
   the exact wording in `eval/qa_pairs.csv` row 14 is also slightly
   ungrammatical ("го" should be "ја"), which likely contributes.

**Confirmed NOT the fix:** raising `retrieval_k` — measured to make this
specific case *worse* (Kansas answered 8/8 at k=6 and k=8, temp 0).

**Tried and did not work on their own:** larger chunk sizes (800/150,
1000/200), sending each chunk's neighbor alongside it, an extra prompt
rule, a cross-encoder reranker (FlashRank), BM25+vector hybrid search,
appending an English translation of the question.

**Showed promise but not a clean fix:** an "English pivot" (translate the
Macedonian question to English internally, retrieve/answer, translate
back) fixed most phrasings but introduced citation mislabeling and
degraded back-translation quality when tested.

**Recommendation, not yet actioned:**
- Larger/sentence-aware chunking is necessary but insufficient alone.
- The real bottleneck looks like it's `answer_model` (`config.py:51`,
  currently llama3-8B)'s Macedonian comprehension, not retrieval — worth
  having `researcher` check whether a more multilingual model (e.g.
  qwen2.5, gemma2-class) handles Macedonian noticeably better before
  attempting a code fix.
- Separately, `eval/qa_pairs.csv` row 14's wording has a grammar error
  worth fixing so it tests the system rather than a typo.

No code changes were made for this one — nothing was verified as an actual
fix. **Decision: leaving this as a documented known limitation** — Filip's
call, not pursuing further for now.

## 5. Row 8 (pre-test/post-test question count) — also no clean fix

**Symptom:** "How many questions were on the pre-test and post-test?"
against 2609.28470v1.pdf (StudentBench) always refused, even after the
embedding model swap.

**Investigated, same pattern as section 4.** The answer sentence spans the
page 3/4 boundary (chunking never lets a chunk cross a page, DECISIONS #1),
gets interrupted by footnote URLs and a running header, and the paper's own
wording ("assessment", "GRE exam") doesn't match the question's phrasing
("pre-test and post-test"). Best-case chunk rejoining only got the correct
chunk to rank 18th of ~377 — still outside the top-4 that reaches the
prompt. **Raising `retrieval_k` makes it worse here too** — confirmed
producing confident wrong answers (e.g. "a single question", a falsely
cited "27") instead of honest refusals, at k=6 through k=12.

**Decision: also a known limitation, not pursued further.** Instead:
- `eval/qa_pairs.csv` row 8 reworded to the paper's own terminology ("How
  many questions were on each assessment?") and `answer_page` corrected
  from 3 to 4 (the fact spans the boundary; page 4 is where "27 questions"
  actually appears).

## 6. Row 10 (first author's affiliation) — fixed

**Symptom:** "What is the first author's affiliation?" against
2609.28371v1.pdf answered wrong ("not explicitly stated... inferred from
email address") despite the correct affiliation being explicit on page 1.
Re-tested fresh at k=4 (single document), it actually failed outright
("couldn't find") — the CSV's old answer was likely recorded under
different conditions (more documents loaded, raising k to 5-6, or the
prior embedding model).

**Cause:** two-part gap. The correct chunk (page 1, containing title,
authors and affiliations) ranked 97th of 188 by embedding similarity —
same class of failure as the original title bug, since the question shares
no topic vocabulary with the abstract that dominates that chunk's
embedding. And the existing document-metadata fix (`_describe_document`,
DECISIONS #19) only added "opening lines" to the prompt when a PDF's
title/authors metadata was *missing* — this PDF declares both, so the
opening lines (containing the affiliations) were skipped even though the
title/authors line alone doesn't include them.

**Fix (DECISIONS #22):**
- `_describe_document` (`rag_pipeline.py`) now always includes opening
  lines, regardless of whether title/authors metadata is present.
- `OPENING_TEXT_LIMIT` raised from 200 to 400 characters so both authors'
  affiliations fit without being cut off mid-sentence.
- Prompt rule reworded to mention affiliations as something opening lines
  may cover.

**Checks:**
- New/updated unit tests covering: opening lines present even when
  title+authors are declared, the new 400-char limit, short-opening case
  unchanged. Full suite: 294 passed. **VERIFIED by automated test.**
- Live run: row 10 answered correctly 3/3 at both temperature 0 and 0.7 —
  "Fusion Energy Division, Oak Ridge National Laboratory, Oak Ridge, TN,
  USA." No regression on rows 5, 7, 9, 11. **VERIFIED by live run.**
- `eval/qa_pairs.csv` row 10 updated with the corrected answer.

**Known limit, not fixed:** with several PDFs loaded together, "the first
author's affiliation" is ambiguous across documents — the fix improves
this case (1/3 correct vs 0/3 before) but doesn't fully resolve it.
Citations for facts sourced from the DOCUMENT line still sometimes get a
made-up `[n]` number (pre-existing issue from the original title fix, not
introduced here).

## Outstanding for Filip

- Nothing is committed — four landed fixes (title/metadata, embedding
  model swap, Macedonian language, affiliation/opening-lines) plus the
  pre-existing clear-button/large-PDF-batch fix are sitting together in
  the working tree. You looked at splitting this into separate commits
  earlier; still your call on final grouping.
- `eval/qa_pairs.csv` fully graded as of this session: rows 1-7, 9, 11-13,
  15-25 correct; row 6 has a minor wording issue (app said "first authors"
  plural, named two people, when only Northcutt is actually first author);
  row 8 and row 14 are documented known limitations (sections 4 and 5
  above), not expected to pass reliably.
- Sections 4 and 5's bugs are unresolved by decision, not oversight —
  documented as known limitations rather than pursued further.
- `switchModelsOnFlag` was checked and ruled out as the cause of
  `debugger`/`coder` running on Sonnet instead of the Opus their agent
  definitions specify — its actual purpose is unrelated (safety-classifier
  model fallback). No config-level cause was found; Opus is confirmed
  available on this account (model catalog cache). Current workaround:
  passing `model: "opus"` explicitly on each subagent call, which is now
  being done for `debugger`/`coder` launches in this conversation.
