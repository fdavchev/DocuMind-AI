# app.py
#
# Main Streamlit entry point.
# We split the app into two tabs:
#   Tab 1 — 🤖 Chat  : your original image + text chat (unchanged)
#   Tab 2 — 📄 PDF Q&A : new RAG pipeline for document question-answering

import streamlit as st
from datetime import datetime

from config import (
    APP_TITLE, APP_ICON,
    USER_AVATAR, ASSISTANT_AVATAR,
    AVAILABLE_MODELS, DEFAULT_MODEL,
)
from chat_history import init_memory, add_message, get_history, clear_history, export_history
from llm_chain import build_llm, stream_response, stream_vision_response

# Imports for the PDF Q&A tab (RAG with source citations)
from pdf_handler import load_pdf_as_documents
from vector_store import build_vector_store, add_documents, retrieve_relevant_documents
from rag_chain import stream_rag_answer_from_documents, format_sources_markdown

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="centered")
st.title(f"{APP_ICON} {APP_TITLE}")

# ── Create the two tabs ────────────────────────────────────────────────────────
tab_chat, tab_pdf = st.tabs(["🤖 Chat", "📄 PDF Q&A"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Original chat (image + text)
# Everything below is identical to your original app.py
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:

    # ── Initialize session state ───────────────────────────────────────────────
    if "history" not in st.session_state:
        st.session_state.history = init_memory()
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = DEFAULT_MODEL
    if "llm" not in st.session_state:
        st.session_state.llm = build_llm(st.session_state.selected_model)
    if "export_snapshot" not in st.session_state:
        st.session_state.export_snapshot = ""

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Settings")

        st.markdown("**Model**")
        chosen_model = st.selectbox(
            label="Choose a model",
            options=AVAILABLE_MODELS,
            index=AVAILABLE_MODELS.index(st.session_state.selected_model),
            label_visibility="collapsed",
        )
        if chosen_model != st.session_state.selected_model:
            st.session_state.selected_model = chosen_model
            st.session_state.llm = build_llm(chosen_model)
            st.toast(f"Switched to **{chosen_model}**", icon="🔄")

        st.markdown("---")
        st.markdown("**🖼️ Image Input**")
        uploaded_image = st.file_uploader(
            "Upload an image",
            type=["png", "jpg", "jpeg", "webp"],
            label_visibility="collapsed",
        )
        if uploaded_image:
            st.image(uploaded_image, use_container_width=True)

        st.markdown("---")
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.history = clear_history(st.session_state.history)
            st.session_state.export_snapshot = ""
            st.rerun()

        has_history = bool(st.session_state.history)
        filename = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        st.download_button(
            label="💾 Save Chat",
            data=st.session_state.export_snapshot if has_history else "",
            file_name=filename,
            mime="text/plain",
            use_container_width=True,
            disabled=not has_history,
        )

        st.markdown("---")
        st.caption("Running 100% locally via Ollama 🔒")

    # ── Render chat history ────────────────────────────────────────────────────
    for msg in get_history(st.session_state.history):
        avatar = USER_AVATAR if msg["role"] == "user" else ASSISTANT_AVATAR
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # ── Chat input ─────────────────────────────────────────────────────────────
    if user_input := st.chat_input("Ask about the image or just chat..."):
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(user_input)
        st.session_state.history = add_message(
            st.session_state.history, "user", user_input
        )

        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            if uploaded_image:
                image_bytes = uploaded_image.getvalue()
                response = st.write_stream(
                    stream_vision_response(image_bytes, user_input, model_name="llava")
                )
            else:
                response = st.write_stream(
                    stream_response(st.session_state.llm, st.session_state.history)
                )

        st.session_state.history = add_message(
            st.session_state.history, "assistant", response
        )
        st.session_state.export_snapshot = export_history(st.session_state.history)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PDF Q&A (RAG pipeline)
# ══════════════════════════════════════════════════════════════════════════════
with tab_pdf:

    st.subheader("📄 Ask Questions About Your PDFs")
    st.caption(
        "Upload one or more PDFs — the app reads them locally and answers "
        "from their content, citing the file and page it used."
    )

    # ── Session state for the PDF tab ──────────────────────────────────────────
    # We store the FAISS vector store and the names of the PDFs already indexed
    # so we never re-process a file the user is still working with.
    if "pdf_vector_store" not in st.session_state:
        st.session_state.pdf_vector_store = None
    if "pdf_filenames" not in st.session_state:
        st.session_state.pdf_filenames = []
    if "pdf_chat_history" not in st.session_state:
        # each entry: {"role": ..., "content": ..., "sources": <markdown or None>}
        st.session_state.pdf_chat_history = []

    # ── PDF Upload (multiple documents share one index) ────────────────────────
    uploaded_pdfs = st.file_uploader(
        "Upload PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        help="Your files never leave your machine. Upload several to ask across all of them.",
    )

    if uploaded_pdfs:
        new_files = [
            pdf for pdf in uploaded_pdfs
            if pdf.name not in st.session_state.pdf_filenames
        ]

        for pdf in new_files:
            with st.spinner(f"Reading and indexing **{pdf.name}**... (this takes ~10-30 seconds)"):
                # Step 1 + 2: extract per-page text and chunk it, keeping
                # {"source": filename, "page": n} on every chunk
                documents = load_pdf_as_documents(pdf)

                if not documents:
                    st.error(
                        f"⚠️ Could not extract text from **{pdf.name}**. "
                        "It may be a scanned image-only PDF."
                    )
                    continue

                # Step 3: embed the chunks — into a new index, or into the
                # existing one so several PDFs are searchable together
                if st.session_state.pdf_vector_store is None:
                    st.session_state.pdf_vector_store = build_vector_store(documents)
                else:
                    add_documents(st.session_state.pdf_vector_store, documents)

                st.session_state.pdf_filenames.append(pdf.name)

            st.success(f"✅ **{pdf.name}** indexed — {len(documents)} chunks created.")

    if st.session_state.pdf_filenames:
        loaded = ", ".join(f"**{name}**" for name in st.session_state.pdf_filenames)
        st.info(f"📎 Indexed: {loaded} — ask a question below.")

    # ── Show PDF chat history ──────────────────────────────────────────────────
    for msg in st.session_state.pdf_chat_history:
        avatar = USER_AVATAR if msg["role"] == "user" else ASSISTANT_AVATAR
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("📚 Sources"):
                    st.markdown(msg["sources"])

    # ── PDF Q&A input ──────────────────────────────────────────────────────────
    if st.session_state.pdf_vector_store is None:
        # No PDF loaded yet — show a disabled hint
        st.chat_input("Upload a PDF above to start asking questions...", disabled=True)
    else:
        if pdf_question := st.chat_input("Ask a question about the documents..."):

            # Show user message
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(pdf_question)
            st.session_state.pdf_chat_history.append(
                {"role": "user", "content": pdf_question, "sources": None}
            )

            # Retrieve relevant chunks from FAISS. With several PDFs indexed
            # we widen the window so one long document can't crowd the others out.
            k = 4 if len(st.session_state.pdf_filenames) <= 1 else 6
            docs = retrieve_relevant_documents(
                st.session_state.pdf_vector_store, pdf_question, k=k
            )
            sources_markdown = format_sources_markdown(docs)

            # Stream the LLM's answer, then show the passages it was given
            with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                response = st.write_stream(
                    stream_rag_answer_from_documents(docs, pdf_question)
                )
                with st.expander("📚 Sources"):
                    st.markdown(sources_markdown)

            st.session_state.pdf_chat_history.append(
                {"role": "assistant", "content": response, "sources": sources_markdown}
            )

    # ── Clear PDF session ──────────────────────────────────────────────────────
    if st.session_state.pdf_vector_store is not None:
        if st.button("🗑️ Clear PDFs & Chat", use_container_width=True):
            st.session_state.pdf_vector_store = None
            st.session_state.pdf_filenames = []
            st.session_state.pdf_chat_history = []
            st.rerun()
