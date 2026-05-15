FROM python:3.11-slim-bookworm

# Install ALL possible system tools AI might need
RUN apt-get update && apt-get install -y \
    # Core utilities
    curl wget git build-essential libffi-dev libssl-dev \
    # Text processing
    jq yq grep sed awk \
    # Archives
    unzip p7zip-full tar gzip bzip2 \
    # Media
    ffmpeg imagemagick \
    # Browsers
    chromium chromium-driver \
    # Display for headless browser
    xvfb xauth \
    # Fonts
    fonts-liberation fonts-noto \
    # Node.js & npm
    nodejs npm \
    # Additional languages
    ruby ruby-dev \
    # Go (for building Go tools)
    golang-go \
    # Rust (for cargo)
    rustc cargo \
    # Java (for some tools)
    default-jre \
    # Database clients
    sqlite3 postgresql-client \
    # Network tools
    net-tools iputils-ping dnsutils \
    # Process management
    htop procps \
    # Text editors
    vim nano \
    # Version control
    git git-lfs \
    # Cloud CLIs (optional, can be installed dynamically)
    awscli \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN pip install playwright && playwright install chromium

# Install global npm packages AI commonly uses
RUN npm install -g \
    puppeteer \
    @anthropic-ai/sdk \
    axios \
    cheerio \
    puppeteer-extra \
    puppeteer-extra-plugin-stealth \
    2>/dev/null || true

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY scripts/ ./scripts/

# Create directories with proper permissions
RUN mkdir -p /data /data/sandbox /data/sessions /data/tools /data/logs /data/backups \
    /tmp/sandbox /app/static /app/data \
    && chmod 777 /data /data/sandbox /data/sessions /data/tools /data/logs /data/backups

# Set environment variables
ENV PYTHONPATH=/app
ENV SANDBOX_DIR=/data/sandbox
ENV VOLUME_PATH=/data
ENV SESSIONS_DIR=/data/sessions
ENV TOOLS_DIR=/data/tools
ENV LOGS_DIR=/data/logs
ENV BACKUPS_DIR=/data/backups
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright
ENV PATH="/data/tools/bin:/data/tools:$PATH"
ENV AUTO_INSTALL_TOOLS=true
ENV PERSIST_SESSIONS=true

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start Xvfb and the application
CMD ["sh", "-c", "Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 & uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 1 --loop uvloop"]
