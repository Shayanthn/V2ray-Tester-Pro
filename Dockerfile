# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY Requirements.md .
RUN pip install --no-cache-dir \
    aiohttp \
    psutil \
    requests \
    python-dotenv \
    rich \
    python-telegram-bot

# Download latest Xray core
RUN XRAY_VERSION=$(curl -s https://api.github.com/repos/XTLS/Xray-core/releases/latest | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/') && \
    wget https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-64.zip && \
    unzip Xray-linux-64.zip && \
    chmod +x xray && \
    rm Xray-linux-64.zip

# Copy application files
COPY ["v2raytesterpro source.py", "./v2raytesterpro.py"]
COPY subscription_manager.py .
COPY .env* ./ || true

# Create output directories
RUN mkdir -p /app/subscriptions /app/logs

# Expose ports (if web dashboard is added)
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/app/subscriptions/subscription.txt') else 1)"

# Run in CLI mode by default
ENTRYPOINT ["python", "v2raytesterpro.py"]
CMD ["--cli", "--max-configs", "300", "--output-dir", "/app/subscriptions"]
