# Drafting the 20–30 evaluation Q&A pairs (section 7.2)

Plain steps for the one part of the evaluation only you can do: writing
questions with a known correct answer, so we can later check whether the app
actually retrieves the right passage and gives the right answer.

A template spreadsheet is ready at `eval/qa_pairs.csv` with one row per
document, pre-filled with how many questions to aim for. You just fill in
the `question`, `correct_answer`, and `answer_page` columns.

## Why this has to be you, step by step

1. **Open the document** in `eval/corpus/` (a PDF reader, not the app).
2. **Find a fact with one clear, unambiguous answer** — a date, a number, a
   named person or place, a defined term, a specific claim. Avoid anything
   opinion-based or anything the document itself hedges on.
3. **Write the question** the way you'd actually ask it in the chat — plain
   language, not "quote-the-sentence" style. E.g. not "What does page 4 say
   about deadlines?" but "When is the submission deadline?"
4. **Write down the correct answer** in your own words, short and specific.
5. **Note the exact page number** the answer came from. This is what lets us
   later check "did the app retrieve a chunk from this page?" — the
   retrieval-accuracy metric in section 7.2.
6. **One more check**: does the answer live entirely on that one page, or
   does it need two pages to make sense? If it spans two pages, either pick
   a different fact or note both page numbers — a chunk never spans a page
   boundary in this app (DECISIONS.md #1), so an answer split across pages
   is harder to grade fairly.

## How many, and from where

The template already splits this out, but the reasoning: longer documents
get more questions, every document gets at least 2 so nothing is untested,
and the three single-page scanned documents get 2 each since there's only
one page to ask about.

| Document | Pages | Suggested questions |
|---|---|---|
| working anytime anywhere-TJ0126015ENN.pdf | 98 | 4 |
| 2609.28470v1.pdf | 47 | 4 |
| 2609.28371v1.pdf | 30 | 3 |
| Кошарка.pdf | 19 | 3 |
| the green city accord-KH0126048ENN.pdf | 7 | 3 |
| Одбојка.pdf | 4 | 2 |
| ohrid-scanned-en.pdf | 1 | 2 |
| ohrid-scanned-mk.pdf | 1 | 2 |
| fudbal-scanned-mk.pdf | 1 | 2 |
| **Total** | | **25** |

That lands in the middle of the plan's 20–30 range. If a document turns out
to be thin on clear factual content, skip a question there and add one
elsewhere instead — the total matters more than the per-file split.

## A tip for the scanned documents specifically

Since these went through OCR, pick a fact from a part of the page where the
recognized text looked clean (check `docs/reports/2026-09-24-eval-corpus-setup.md`
for what was actually recognized) — a question whose answer depends on a
part of the page OCR read wrong will look like a retrieval failure when it's
actually an OCR failure. Both are worth knowing, but keep the two separate
in your head when you're grading answers later, since the CER (character
error rate) metric is what specifically measures the OCR side.

## What happens after you fill it in

Send me the completed `eval/qa_pairs.csv` (or tell me it's ready in place)
and I'll run every question through the real pipeline — check whether the
retrieved chunk matches your `answer_page`, and show you the app's actual
generated answer next to your recorded correct one. You then grade each
answer (correct / partially correct / wrong / refused) yourself, since
that's the judgement call the plan says has to be manual and yours.
