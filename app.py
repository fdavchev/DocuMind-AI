# app.py

import streamlit as st
from datetime import datetime
from config import APP_TITLE, APP_ICON, USER_AVATAR, ASSISTANT_AVATAR, AVAILABLE_MODELS, DEFAULT_MODEL
from chat_history import init_memory, add_message, get_history, clear_history, export_history
from llm_chain import build_llm, stream_response, stream_vision_response

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="centered")
st.title(f"{APP_ICON} {APP_TITLE}")

# ── Initialize session state ───────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = init_memory()

if "selected_model" not in st.session_state:
    st.session_state.selected_model = DEFAULT_MODEL

if "llm" not in st.session_state:
    st.session_state.llm = build_llm(st.session_state.selected_model)

if "export_snapshot" not in st.session_state:
    st.session_state.export_snapshot = ""

# ── Sidebar ────────────────────────────────────────────────────────────────────
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

# ── Render chat history ────────────────────────────────────────────────────────
for msg in get_history(st.session_state.history):
    avatar = USER_AVATAR if msg["role"] == "user" else ASSISTANT_AVATAR
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ── Chat input ─────────────────────────────────────────────────────────────────
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