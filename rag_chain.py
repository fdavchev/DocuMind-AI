# rag_chain.py
#
# WHAT THIS FILE DOES:
# This is the final step of the RAG pipeline.
#
# RAG = Retrieval Augmented Generation
#   Retrieval  → fetch relevant chunks from FAISS  (vector_store.py)
#   Augmented  → add those chunks to the prompt
#   Generation → send the augmented prompt to the LLM and stream the answer
#
# WHY NOT JUST ASK THE LLM DIRECTLY?
# Because the LLM doesn't know what's in your PDF. It was trained on
# general internet data. By injecting the relevant chunks into the prompt,
# we "show" it the right pages of the document before asking the question.
#
# This is called "grounding" — the answer is grounded in your actual document.

import ollama


# The text LLM used for answering. Must be pulled via `ollama pull llama3`.
# We use llama3 here because llava is a vision model, not optimised for
# long document reasoning.
ANSWER_MODEL = "llama3"


def build_rag_prompt(context: str, question: str) -> str:
    """
    Builds the full prompt that gets sent to the LLM.

    The prompt has three parts:
    1. Instruction — tells the model its role and rules
    2. Context     — the relevant PDF chunks retrieved from FAISS
    3. Question    — the user's actual question
    """
    prompt = f"""You are a helpful assistant that answers questions strictly based on the provided document context.

Rules:
- Only use information from the CONTEXT below to answer.
- If the answer is not in the context, say "I couldn't find that information in the document."
- Be concise and direct.
- Do not make up information.

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
