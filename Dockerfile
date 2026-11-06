# CPU image for self-hosting the API + UI (python:3.12-slim + CPU-only torch).
# Models download on first start into /root/.cache/huggingface (mount a volume).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.13.7

WORKDIR /app

# Dependencies first so code edits don't invalidate the (large) dependency layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --all-extras --no-install-project

COPY src ./src
COPY evals ./evals
COPY data/raw/laws.toml ./data/raw/laws.toml
RUN uv sync --locked --no-dev --all-extras

# Non-root user; data/ and the HF cache are expected as volumes.
RUN useradd --create-home marjaa && mkdir -p /app/data && chown -R marjaa /app
USER marjaa
ENV HF_HOME=/home/marjaa/.cache/huggingface

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["marjaa", "serve", "--host", "0.0.0.0", "--port", "8000"]
