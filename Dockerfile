FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 18+ for MCP Playwright
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install MCP Playwright server globally
RUN npm install -g @playwright/mcp

# Install Playwright browsers for MCP
RUN npx playwright install --with-deps chromium

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/out/digests /app/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV DB_PATH=/app/data/news.db

# Create non-root user
RUN useradd -m -u 1000 newsanalyzer && \
    chown -R newsanalyzer:newsanalyzer /app
USER newsanalyzer

# Initialize database on first run
RUN python scripts/init_db.py
RUN python scripts/load_feeds.py

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('${DB_PATH}').execute('SELECT 1')" || exit 1

# Default command
CMD ["python", "news_analyzer.py", "--export", "--format", "json"]

# Labels
LABEL org.opencontainers.image.title="AI News Analysis System"
LABEL org.opencontainers.image.description="Swiss business news analysis with GPT-5 models"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.authors="AI News Analysis Team"
