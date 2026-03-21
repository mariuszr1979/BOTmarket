FROM python:3.12-slim

WORKDIR /app

# Install system deps for psycopg binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (from frozen requirements.txt — no venv inside container)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy exchange source
COPY *.py ./
COPY skill.md ./

# Expose both interfaces
EXPOSE 8000
EXPOSE 9000

# Healthcheck uses the existing /v1/health endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/v1/health || exit 1

# Entrypoint starts both servers in the same container.
# TCP server is backgrounded; uvicorn runs in foreground and holds the process.
CMD ["sh", "-c", "python tcp_server.py & uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info"]
