FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8080

WORKDIR /app

EXPOSE 8080

# System deps (quiet, noninteractive)
RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends -qq build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install only runtime deps to avoid dev resolution issues
COPY pyproject.toml /app/pyproject.toml
RUN pip install --upgrade pip \
    && pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --without dev --no-root

COPY . /app

CMD ["python","-m","app.main"]
