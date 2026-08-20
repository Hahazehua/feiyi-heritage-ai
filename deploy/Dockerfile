# syntax=docker/dockerfile:1

FROM python:3.11-slim

# PyPI resolves but crawls from the competition host — numpy alone downloaded at
# 38 KB/s, putting a cold install past half an hour. Override PIP_INDEX_URL to
# build elsewhere:
#   docker compose build --build-arg PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TIMEOUT=60 \
    PIP_RETRIES=5 \
    PYTHONPATH=/app/src

# curl is only needed for the container HEALTHCHECK below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependency layer. requirements.txt installs the project itself with `-e .`,
# which needs an importable package to exist at install time — so a stub stands
# in for the real one here. Copying src/ instead would put application code
# above this layer, and every code push would reinstall every dependency from
# scratch, which is exactly what used to happen.
COPY pyproject.toml requirements.txt README.md ./
RUN mkdir -p src/heritagelink \
    && touch src/heritagelink/__init__.py \
    && pip install -r requirements.txt

# Application layer. PYTHONPATH points at /app/src, so the real package below
# is imported directly and the editable install's own resolution never matters.
COPY src/ ./src/
COPY app.py ./
COPY data/ ./data/
COPY assets/ ./assets/
# The pitch deck is served from here so the presenter reaches it in one click.
COPY static/ ./static/
COPY skills/ ./skills/
COPY .streamlit/config.toml ./.streamlit/config.toml

# Run as a non-root user inside the container.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=true", \
     "--browser.gatherUsageStats=false"]
