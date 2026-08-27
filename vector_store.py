# vector_store.py
#
# WHAT THIS FILE DOES:
# 1. Takes the chunk Documents from pdf_handler.py
# 2. Converts each chunk into a "vector" (a list of ~768 numbers)
#    using the nomic-embed-text model running locally in Ollama
# 3. Stores those vectors in FAISS (a fast similarity search library)
#    together with each chunk's metadata (source filename + page number)
# 4. When the user asks a question, converts the question into a vector
#    and finds the chunks whose vectors are closest → most relevant context
#
# ANALOGY:
# Think of each chunk as a point in 3D space (but 768 dimensions).
# Similar text = nearby points. FAISS finds the nearest neighbours fast.
#
# MULTI-DOCUMENT:
# One FAISS index holds chunks from several PDFs at once. Each chunk keeps
# its "source" metadata, so retrieval can pull the best passages across all
# loaded documents and still say which file each one came from.

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

# The embedding model — runs locally via Ollama.
# It has NO LLM capability; it only converts text → vectors.
EMBEDDING_MODEL = "nomic-embed-text"


def get_embeddings():
    """The embedding function used for both indexing and querying."""
    return OllamaEmbeddings(model=EMBEDDING_MODEL)


def _as_documents(chunks: list) -> list[Document]:
    """Accepts either Documents or bare strings and normalises to Documents."""
    return [
        chunk if isinstance(chunk, Document) else Document(page_content=chunk)
        for chunk in chunks
    ]


def build_vector_store(chunks: list, embeddings=None) -> FAISS:
    """
    Embeds every chunk and stores them in a FAISS index, metadata included.
    Returns the FAISS vector store object.

    Called once per uploaded PDF (or once for the first PDF, after which
    add_documents extends the same index). It may take 5-30 seconds
    depending on PDF length and your hardware.

    `embeddings` is injectable so tests can run without a live Ollama.
    """
    if embeddings is None:
        embeddings = get_embeddings()

    # from_documents embeds each chunk and builds the index in one call,
    # carrying metadata through so citations survive retrieval.
    return FAISS.from_documents(documents=_as_documents(chunks), embedding=embeddings)


def add_documents(vector_store: FAISS, chunks: list) -> FAISS:
    """
    Adds another document's chunks to an EXISTING index.

    This is what makes multi-document Q&A work: upload a second PDF and its
    chunks join the same index rather than replacing it.
    """
    vector_store.add_documents(_as_documents(chunks))
    return vector_store


def retrieve_relevant_documents(
    vector_store: FAISS, question: str, k: int = 4
) -> list[Document]:
    """
    Converts the user's question into a vector, then returns the k most
    similar chunks as Documents — page_content plus source/page metadata.

    k=4 means we retrieve the 4 most relevant chunks.
    More chunks = more context but slower + more tokens.
    """
    return vector_store.similarity_search(question, k=k)


def retrieve_relevant_chunks(vector_store: FAISS, question: str, k: int = 4) -> str:
    """
    Same retrieval, but flattened to one plain string with no citations.
    Kept for callers that just want raw context.
    """
    docs = retrieve_relevant_documents(vector_store, question, k=k)
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


def list_sources(vector_store: FAISS) -> list[str]:
    """Sorted list of the filenames currently indexed — used by the UI."""
    sources = {
        doc.metadata.get("source")
        for doc in vector_store.docstore._dict.values()
        if doc.metadata.get("source")
    }
    return sorted(sources)
