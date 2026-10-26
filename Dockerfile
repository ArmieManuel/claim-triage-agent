# API image for the claim triage agent. The model runs in a separate Ollama container
# (see docker-compose.yml), reached through TRIAGE_OLLAMA_HOST.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so code changes do not rebuild this layer.
COPY pyproject.toml requirements.lock README.md ./
COPY src ./src
COPY data ./data
COPY evals ./evals
COPY config ./config

# Editable install keeps config/ and data/golden/ at their repo paths (/app/...).
# requirements.lock pins every transitive dependency to the tested versions.
RUN pip install --constraint requirements.lock -e . \
    && useradd --create-home --uid 10001 app \
    && chown -R app:app /app

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "triage.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
