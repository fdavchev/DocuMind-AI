# vector_store.py
#
# WHAT THIS FILE DOES:
# 1. Takes our text chunks from pdf_handler.py
# 2. Converts each chunk into a "vector" (a list of ~768 numbers)
#    using the nomic-embed-text model running locally in Ollama
# 3. Stores all those vectors in FAISS (a fast similarity search library)
# 4. When the user asks a question, converts the question into a vector
#    and finds the chunks whose vectors are closest → most relevant context
#
# ANALOGY:
# Think of each chunk as a point in 3D space (but 768 dimensions).
# Similar text = nearby points. FAISS finds the nearest neighbours fast.

from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS


# The embedding model — runs locally via Ollama.
# It has NO LLM capability; it only converts text → vectors.
EMBEDDING_MODEL = "nomic-embed-text"


def build_vector_store(chunks: list[str]) -> FAISS:
    """
    Embeds every chunk and stores them in a FAISS index.
    Returns the FAISS vector store object.

    This is called ONCE when the user uploads a new PDF.
    It may take 5-30 seconds depending on PDF length and your hardware.
    """
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)

    # FAISS.from_texts embeds each chunk and builds the index in one call
    vector_store = FAISS.from_texts(texts=chunks, embedding=embeddings)

    return vector_store


def retrieve_relevant_chunks(vector_store: FAISS, question: str, k: int = 4) -> str:
    """
    Converts the user's question into a vector, then finds the k most
    similar chunks in the FAISS index.

    Returns a single string with all relevant chunks joined together —
    this becomes the "context" we pass to the LLM.

    k=4 means we retrieve the 4 most relevant chunks.
    More chunks = more context but slower + more tokens.
    """
    # similarity_search returns LangChain Document objects
    docs = vector_store.similarity_search(question, k=k)

    # Join the page_content of each document into one context block
    context = "\n\n---\n\n".join([doc.page_content for doc in docs])

    return context
