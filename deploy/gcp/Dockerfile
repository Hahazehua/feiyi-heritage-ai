FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LLM_ENABLED=false \
    ANALYTICS_ENABLED=false \
    AGENT_REVIEW_MODE_ENABLED=false

WORKDIR /app
COPY pyproject.toml requirements.txt README.md ./
COPY src/ ./src/
# Match requirements.txt's Streamlit pin without installing this project twice.
# Image paths in the app are resolved from the src checkout, so preserve that layout.
RUN python -m pip install -e '.[gcp]' 'streamlit==1.59.2'
COPY app.py ./
COPY data/ ./data/
COPY assets/ ./assets/
COPY static/ ./static/
COPY .streamlit/config.toml ./.streamlit/config.toml
RUN useradd --create-home --uid 10001 appuser
USER appuser
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)"
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]
