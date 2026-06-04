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

# NEW imports for the PDF Q&A tab
from pdf_handler import extract_text_from_pdf, split_text_into_chunks
from vector_store import build_vector_store, retrieve_relevant_chunks
from rag_chain import stream_rag_answer

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

    st.subheader("📄 Ask Questions About a PDF")
    st.caption("Upload any PDF — the app reads it locally and answers based on its content.")

    # ── Session state for the PDF tab ──────────────────────────────────────────
    # We store the FAISS vector store and the PDF name so we don't re-process
    # the same PDF every time the user types a new question.
    if "pdf_vector_store" not in st.session_state:
        st.session_state.pdf_vector_store = None
    if "pdf_filename" not in st.session_state:
        st.session_state.pdf_filename = None
    if "pdf_chat_history" not in st.session_state:
        st.session_state.pdf_chat_history = []  # list of {"role": ..., "content": ...}

    # ── PDF Upload ─────────────────────────────────────────────────────────────
    uploaded_pdf = st.file_uploader(
        "Upload a PDF",
        type=["pdf"],
        help="Your file never leaves your machine.",
    )

    if uploaded_pdf is not None:
        # Only re-process if it's a NEW file (different name)
        if uploaded_pdf.name != st.session_state.pdf_filename:
            with st.spinner(f"Reading and indexing **{uploaded_pdf.name}**... (this takes ~10-30 seconds)"):
                # Step 1: Extract text from PDF
                raw_text = extract_text_from_pdf(uploaded_pdf)

                if not raw_text.strip():
                    st.error("⚠️ Could not extract text from this PDF. It may be a scanned image-only PDF.")
                    st.stop()

                # Step 2: Split into chunks
                chunks = split_text_into_chunks(raw_text)

                # Step 3: Embed chunks and build FAISS index
                st.session_state.pdf_vector_store = build_vector_store(chunks)
                st.session_state.pdf_filename = uploaded_pdf.name
                st.session_state.pdf_chat_history = []  # reset chat for new PDF

            st.success(f"✅ **{uploaded_pdf.name}** indexed — {len(chunks)} chunks created. Ask anything!")

        else:
            st.info(f"📎 **{st.session_state.pdf_filename}** is loaded. Ask a question below.")

    # ── Show PDF chat history ──────────────────────────────────────────────────
    for msg in st.session_state.pdf_chat_history:
        avatar = USER_AVATAR if msg["role"] == "user" else ASSISTANT_AVATAR
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # ── PDF Q&A input ──────────────────────────────────────────────────────────
    if st.session_state.pdf_vector_store is None:
        # No PDF loaded yet — show a disabled hint
        st.chat_input("Upload a PDF above to start asking questions...", disabled=True)
    else:
        if pdf_question := st.chat_input("Ask a question about the document..."):

            # Show user message
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(pdf_question)
            st.session_state.pdf_chat_history.append(
                {"role": "user", "content": pdf_question}
            )

            # Retrieve relevant chunks from FAISS
            context = retrieve_relevant_chunks(
                st.session_state.pdf_vector_store, pdf_question
            )

            # Stream the LLM's answer
            with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                response = st.write_stream(
                    stream_rag_answer(context, pdf_question)
                )

            st.session_state.pdf_chat_history.append(
                {"role": "assistant", "content": response}
            )

    # ── Clear PDF session ──────────────────────────────────────────────────────
    if st.session_state.pdf_vector_store is not None:
        if st.button("🗑️ Clear PDF & Chat", use_container_width=True):
            st.session_state.pdf_vector_store = None
            st.session_state.pdf_filename = None
            st.session_state.pdf_chat_history = []
            st.rerun()
