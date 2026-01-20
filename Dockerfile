# WikiSeed Server - Main Dockerfile
# Used by all Python-based containers (controller, scraper, downloader, uploader, creator, publisher, monitor)

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
# Install production deps by default, dev deps can be added via docker-compose override
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Create non-root user for security
RUN useradd -m -u 1000 wikiseed && \
    chown -R wikiseed:wikiseed /app

# Switch to non-root user
USER wikiseed

# Default command (overridden by docker-compose for each service)
CMD ["python", "--version"]
