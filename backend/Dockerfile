# Backend Dockerfile for Document Chatbot
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OPENROUTER_MODEL=google/gemma-4-31b-it:free \
    OPENROUTER_BASE_URL=https://openrouter.ai/api/v1 \
    OPENROUTER_TIMEOUT_SECONDS=90

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --timeout 120 --retries 10 -r requirements.txt

# Copy application code
COPY . .

# Run the API and ingestion worker as an unprivileged user.
RUN mkdir -p uploads chroma_db /app/storage \
    && useradd --create-home --uid 10001 app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health')" || exit 1

# Run the application
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
