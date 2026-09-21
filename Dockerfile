# DocuMind AI — Streamlit application image.
#
# This image contains the app only. The LLM runtime lives in a separate
# `ollama` container (see docker-compose.yml), for two reasons:
#   1. Model weights are gigabytes — baking them into an image makes it
#      enormous and rebuilds slow. A named volume caches them across runs.
#   2. Ollama publishes an official image with GPU support already wired up;
#      re-implementing that here would be strictly worse.
#
# The app finds the runtime through OLLAMA_HOST, which both the `ollama`
# client and langchain-ollama honour.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl for the healthcheck below; tesseract-ocr so scanned PDFs work out of
# the box in the container even when the host has no OCR installed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first, so a source change doesn't invalidate the pip layer.
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY *.py ./

# Run as a non-root user — uploaded PDFs are untrusted input.
RUN useradd --create-home --uid 1000 documind && chown -R documind:documind /app
USER documind

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
