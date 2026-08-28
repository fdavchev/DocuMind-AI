# app.py
#
# Main Streamlit entry point.
# Two tabs:
#   Tab 1 — 🤖 Chat    : image + text chat
#   Tab 2 — 📄 PDF Q&A : RAG pipeline for document question-answering
#
# LAYOUT NOTES:
# The conversation lives in a fixed-height scrolling container and the input sits
# directly beneath it. That way the input stays put no matter how long the
# conversation gets, instead of being pushed further down the page with every
# answer. Setup controls (uploads, status, model choice) live in the sidebar or
# in a collapsible panel, so the reading area stays uncluttered.

from datetime import datetime

import streamlit as st

from config import (
    APP_TITLE, APP_ICON,
    USER_AVATAR, ASSISTANT_AVATAR,
    AVAILABLE_MODELS, DEFAULT_MODEL,
)
from chat_history import init_memory, add_message, get_history, clear_history, export_history
from llm_chain import build_llm, stream_response, stream_vision_response

# Imports for the PDF Q&A tab (RAG with source citations)
from pdf_handler import load_pdf_as_documents, scanned_page_count
from vector_store import build_vector_store, add_documents, retrieve_relevant_documents
from rag_chain import stream_rag_answer_from_documents, format_sources_markdown

# User-readable failures instead of tracebacks (Ollama down, model missing,
# oversized or corrupt PDF)
from errors import (
    CHAT_MODELS,
    PDF_MODELS,
    guarded_stream,
    no_text_error,
    ocr_status,
    readiness,
    translate,
    validate_pdf_upload,
)

# Height of the scrolling conversation area, in pixels. Fixed on purpose: it is
# what keeps the input box in the same place all session.
CHAT_HEIGHT = 430

# One readiness check covering everything the app needs, so the user sees a
# single verdict rather than one panel per tab.
REQUIRED_MODELS = list(dict.fromkeys(CHAT_MODELS + PDF_MODELS))


def show_error(exc: Exception, filename: str | None = None) -> None:
    """Renders any pipeline failure as an actionable message."""
    st.error(translate(exc, filename).render())


def render_status_panel() -> None:
    """
    The single pre-flight check for the whole app, shown in the sidebar.

    Verifies Ollama is reachable and every required model is installed, before
    the user uploads anything. Cached in session state so we don't call the
    Ollama API on every rerun, with a button to re-check after a fix.
    """
    if "status" not in st.session_state:
        st.session_state.status = readiness(REQUIRED_MODELS)

    problem = st.session_state.status
    label = "✅ System ready" if problem is None else "⚠️ Setup needed"

    with st.expander(label, expanded=problem is not None):
        if problem is None:
            st.success(f"Ollama is running with {', '.join(REQUIRED_MODELS)} installed.")
        else:
            st.warning(problem.render())

        # OCR is optional, so its absence is a note rather than a warning.
        st.caption(ocr_status())

        if st.button("🔄 Re-check", use_container_width=True):
            st.session_state.status = readiness(REQUIRED_MODELS)
            st.rerun()


def render_message(msg: dict) -> None:
    """One chat bubble, with its Sources panel when the message has citations."""
    avatar = USER_AVATAR if msg["role"] == "user" else ASSISTANT_AVATAR
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("📚 Sources"):
                st.markdown(msg["sources"])


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="centered")

# Light styling only — spacing and emphasis. No hardcoded colours, so the app
# still looks right in both Streamlit's light and dark themes.
st.markdown(
    """
    <style>
      /* Tighten the gap above the title */
      .block-container { padding-top: 2.5rem; }

      /* Make the tab labels easier to hit and read */
      .stTabs [data-baseweb="tab"] {
          font-size: 1rem;
          padding: 0.4rem 1rem;
      }

      /* Sources panels sit under answers — keep them quiet */
      [data-testid="stExpander"] summary p { font-size: 0.85rem; }

      /* A little breathing room between chat bubbles */
      [data-testid="stChatMessage"] { margin-bottom: 0.35rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(f"{APP_ICON} {APP_TITLE}")

# ── Session state ──────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = init_memory()
if "selected_model" not in st.session_state:
    st.session_state.selected_model = DEFAULT_MODEL
if "llm" not in st.session_state:
    st.session_state.llm = build_llm(st.session_state.selected_model)
if "export_snapshot" not in st.session_state:
    st.session_state.export_snapshot = ""
if "pdf_vector_store" not in st.session_state:
    st.session_state.pdf_vector_store = None
if "pdf_filenames" not in st.session_state:
    st.session_state.pdf_filenames = []
if "pdf_chat_history" not in st.session_state:
    # each entry: {"role": ..., "content": ..., "sources": <markdown or None>}
    st.session_state.pdf_chat_history = []


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — shared by both tabs, so the status check appears exactly once
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("⚙️ Settings")
    render_status_panel()

    st.markdown("---")
    st.markdown("**Chat model**")
    chosen_model = st.selectbox(
        label="Choose a model",
        options=AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index(st.session_state.selected_model),
        label_visibility="collapsed",
        help="Used by the Chat tab. PDF answers always use llama3.",
    )
    if chosen_model != st.session_state.selected_model:
        st.session_state.selected_model = chosen_model
        st.session_state.llm = build_llm(chosen_model)
        st.toast(f"Switched to **{chosen_model}**", icon="🔄")

    st.markdown("**🖼️ Image input**")
    uploaded_image = st.file_uploader(
        "Upload an image",
        type=["png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
    )
    if uploaded_image:
        st.image(uploaded_image, use_container_width=True)

    st.markdown("---")
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.history = clear_history(st.session_state.history)
        st.session_state.export_snapshot = ""
        st.rerun()

    has_history = bool(st.session_state.history)
    st.download_button(
        label="💾 Save chat",
        data=st.session_state.export_snapshot if has_history else "",
        file_name=f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not has_history,
    )

    st.markdown("---")
    st.caption("Running 100% locally via Ollama 🔒")


tab_chat, tab_pdf = st.tabs(["🤖 Chat", "📄 PDF Q&A"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Chat (image + text)
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:

    # The conversation scrolls inside this box; the input below never moves.
    chat_box = st.container(height=CHAT_HEIGHT, border=False)
    with chat_box:
        if not st.session_state.history:
            st.caption("Ask anything, or upload an image in the sidebar to talk about it.")
        for msg in get_history(st.session_state.history):
            render_message(msg)

    if user_input := st.chat_input("Ask about the image or just chat..."):
        with chat_box:
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(user_input)
            st.session_state.history = add_message(
                st.session_state.history, "user", user_input
            )

            with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                try:
                    if uploaded_image:
                        response = st.write_stream(
                            guarded_stream(
                                stream_vision_response(
                                    uploaded_image.getvalue(),
                                    user_input,
                                    model_name="llava",
                                )
                            )
                        )
                    else:
                        response = st.write_stream(
                            guarded_stream(
                                stream_response(
                                    st.session_state.llm, st.session_state.history
                                )
                            )
                        )
                except Exception as exc:
                    show_error(exc)
                    response = None

        # Only record an answer we actually got — a failed turn leaves the
        # history clean so the user can simply retry.
        if response:
            st.session_state.history = add_message(
                st.session_state.history, "assistant", response
            )
            st.session_state.export_snapshot = export_history(st.session_state.history)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PDF Q&A (RAG pipeline)
# ══════════════════════════════════════════════════════════════════════════════
with tab_pdf:

    indexed = st.session_state.pdf_filenames

    # Setup collapses once documents are loaded, so the conversation gets the
    # space instead of the upload widget.
    with st.expander(
        f"📎 Documents ({len(indexed)} indexed)" if indexed else "📎 Upload documents",
        expanded=not indexed,
    ):
        uploaded_pdfs = st.file_uploader(
            "Upload PDFs",
            type=["pdf"],
            accept_multiple_files=True,
            help="Your files never leave your machine. Upload several to ask across all of them.",
        )

        if uploaded_pdfs:
            new_files = [
                pdf for pdf in uploaded_pdfs if pdf.name not in st.session_state.pdf_filenames
            ]

            for pdf in new_files:
                try:
                    with st.spinner(f"Reading and indexing **{pdf.name}**... (~10-30 seconds)"):
                        # Step 0: refuse files too large to index in reasonable time
                        validate_pdf_upload(pdf)

                        # Step 1 + 2: extract per-page text and chunk it, keeping
                        # {"source": filename, "page": n} on every chunk
                        documents = load_pdf_as_documents(pdf)

                        if not documents:
                            # Distinguish "scanned, and we can't OCR it" from
                            # "genuinely empty" — different problems, different fixes.
                            raise no_text_error(pdf.name, scanned_page_count(pdf))

                        # Step 3: embed the chunks — into a new index, or into the
                        # existing one so several PDFs are searchable together
                        if st.session_state.pdf_vector_store is None:
                            st.session_state.pdf_vector_store = build_vector_store(documents)
                        else:
                            add_documents(st.session_state.pdf_vector_store, documents)

                        st.session_state.pdf_filenames.append(pdf.name)
                except Exception as exc:
                    # One bad file must not stop the rest of the batch indexing.
                    show_error(exc, pdf.name)
                    continue

                st.success(f"✅ **{pdf.name}** indexed — {len(documents)} chunks created.")

        if st.session_state.pdf_filenames:
            st.markdown(
                "**Answering from:** "
                + " · ".join(f"`{name}`" for name in st.session_state.pdf_filenames)
            )
            if st.button("🗑️ Clear documents & chat", use_container_width=True):
                st.session_state.pdf_vector_store = None
                st.session_state.pdf_filenames = []
                st.session_state.pdf_chat_history = []
                st.rerun()

    # Same pattern as the chat tab: scrolling history, fixed input beneath it.
    pdf_box = st.container(height=CHAT_HEIGHT, border=False)
    with pdf_box:
        if not st.session_state.pdf_chat_history:
            st.caption(
                "Answers cite the file and page they came from — open **📚 Sources** "
                "under any answer to check it."
            )
        for msg in st.session_state.pdf_chat_history:
            render_message(msg)

    if st.session_state.pdf_vector_store is None:
        st.chat_input("Upload a PDF above to start asking questions...", disabled=True)
    elif pdf_question := st.chat_input("Ask a question about the documents..."):
        with pdf_box:
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(pdf_question)
            st.session_state.pdf_chat_history.append(
                {"role": "user", "content": pdf_question, "sources": None}
            )

            # Retrieve relevant chunks from FAISS. With several PDFs indexed we
            # widen the window so one long document can't crowd the others out.
            # Embedding the question needs Ollama, so retrieval can fail too.
            with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                response, sources_markdown = None, None
                try:
                    k = 4 if len(st.session_state.pdf_filenames) <= 1 else 6
                    docs = retrieve_relevant_documents(
                        st.session_state.pdf_vector_store, pdf_question, k=k
                    )
                    sources_markdown = format_sources_markdown(docs)

                    # Stream the answer, then show the passages it was given
                    response = st.write_stream(
                        guarded_stream(
                            stream_rag_answer_from_documents(docs, pdf_question)
                        )
                    )
                    with st.expander("📚 Sources"):
                        st.markdown(sources_markdown)
                except Exception as exc:
                    show_error(exc)

        if response:
            st.session_state.pdf_chat_history.append(
                {
                    "role": "assistant",
                    "content": response,
                    "sources": sources_markdown,
                }
            )
