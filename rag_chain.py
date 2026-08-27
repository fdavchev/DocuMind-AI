# rag_chain.py
#
# WHAT THIS FILE DOES:
# This is the final step of the RAG pipeline.
#
# RAG = Retrieval Augmented Generation
#   Retrieval  → fetch relevant chunks from FAISS  (vector_store.py)
#   Augmented  → add those chunks to the prompt, each labelled with its
#                source file and page number
#   Generation → send the augmented prompt to the LLM and stream the answer
#
# WHY NOT JUST ASK THE LLM DIRECTLY?
# Because the LLM doesn't know what's in your PDF. It was trained on
# general internet data. By injecting the relevant chunks into the prompt,
# we "show" it the right pages of the document before asking the question.
#
# This is called "grounding" — the answer is grounded in your actual document.
#
# WHY CITATIONS?
# A grounded answer the reader can't verify is still a claim. Each context
# block is prefixed with [1] report.pdf, p. 4, the model is told to cite
# those markers inline, and the UI lists the same passages underneath — so
# any sentence in the answer can be traced back to a page.

import ollama
from langchain_core.documents import Document

# The text LLM used for answering. Must be pulled via `ollama pull llama3`.
# We use llama3 here because llava is a vision model, not optimised for
# long document reasoning.
ANSWER_MODEL = "llama3"


def format_citation(doc: Document) -> str:
    """
    Renders one chunk's provenance as human-readable text:
    "report.pdf, p. 4" — or just the filename if the page is unknown.
    """
    source = doc.metadata.get("source") or "document"
    page = doc.metadata.get("page")
    return f"{source}, p. {page}" if page else source


def build_context_block(docs: list[Document]) -> str:
    """
    Turns retrieved Documents into the CONTEXT section of the prompt, with
    each passage numbered so the model has a concrete marker to cite.

        [1] report.pdf, p. 4
        <chunk text>
    """
    blocks = []
    for index, doc in enumerate(docs, start=1):
        blocks.append(f"[{index}] {format_citation(doc)}\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks)


def format_sources_markdown(docs: list[Document]) -> str:
    """
    The "Sources" list shown under an answer in the UI, matching the [n]
    markers the model cites.
    """
    if not docs:
        return "_No sources retrieved._"

    lines = []
    for index, doc in enumerate(docs, start=1):
        excerpt = " ".join(doc.page_content.split())
        if len(excerpt) > 200:
            excerpt = excerpt[:200].rstrip() + "…"
        lines.append(f"**[{index}] {format_citation(doc)}** — {excerpt}")
    return "\n\n".join(lines)


def build_rag_prompt(context: str, question: str) -> str:
    """
    Builds the full prompt that gets sent to the LLM.

    The prompt has three parts:
    1. Instruction — tells the model its role and rules, citations included
    2. Context     — the numbered PDF passages retrieved from FAISS
    3. Question    — the user's actual question
    """
    prompt = f"""You are a helpful assistant that answers questions strictly based on the provided document context.

Rules:
- Only use information from the CONTEXT below to answer.
- Each passage is labelled [n] with its source file and page number.
- Cite the passages you used inline, e.g. "the deadline is March 1 [1]".
- If the answer is not in the context, say "I couldn't find that information in the document."
- Be concise and direct.
- Do not make up information, and never cite a passage number that is not listed below.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""

    return prompt


def stream_rag_answer(context: str, question: str):
    """
    Builds the RAG prompt and streams the LLM's answer token by token.

    This is a Python generator — it yields text pieces as they arrive
    from Ollama, which lets Streamlit display them in real time with
    st.write_stream().
    """
    prompt = build_rag_prompt(context, question)

    # Stream from Ollama using the low-level ollama library
    # (same approach as your existing llm_chain.py)
    stream = ollama.chat(
        model=ANSWER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )

    for chunk in stream:
        token = chunk["message"]["content"]
        if token:
            yield token


def stream_rag_answer_from_documents(docs: list[Document], question: str):
    """
    Citation-aware entry point: retrieved Documents in, streamed answer out.
    The UI pairs this with format_sources_markdown(docs) so the [n] markers
    in the answer line up with the list below it.
    """
    return stream_rag_answer(build_context_block(docs), question)
