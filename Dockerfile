# FORGE-Vision — Docker Image
# Serves both the FastAPI backend and the Streamlit UI.
# The docker-compose.yml runs each as a separate container from this same image.

FROM python:3.11-slim

# System deps: gcc for bcrypt/cryptography C extensions; libpq-dev for asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies — cached as a separate layer so code changes
# don't trigger a full reinstall.
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# Copy application source
COPY src/ ./src/
COPY config/ ./config/
COPY alembic.ini .
COPY alembic/ ./alembic/

# Ensure the project root is on PYTHONPATH so `from src.x import y` works.
ENV PYTHONPATH=/app

# Ports used by each service (docker-compose maps these individually)
EXPOSE 8000 8501
