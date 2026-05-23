# ── Stage 1: builder — install Python deps ───────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────
FROM python:3.12-slim

# System dependencies: megatools, rclone, java (MegaBasterd), curl
RUN apt-get update && apt-get install -y --no-install-recommends \
        megatools \
        curl \
        default-jre-headless \
    && curl -fsSL https://rclone.org/install.sh | bash \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Runtime directories
RUN mkdir -p data downloads logs

# Non-root user for security
RUN useradd -m -u 1000 botuser \
    && chown -R botuser:botuser /app
USER botuser

CMD ["python", "main.py"]
