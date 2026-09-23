# config.py
#
# What is left here is UI vocabulary only — the model and pipeline settings now
# live in documind/config.py as AppConfig.

# The two modes of the app. Defined here rather than in app.py so tests can
# reference them without importing (and therefore executing) the Streamlit
# script.
CHAT_MODE = "🤖 Chat"
PDF_MODE = "📄 PDF Q&A"

USER_AVATAR = "🧑"
ASSISTANT_AVATAR = "🤖"
