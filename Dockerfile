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
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Xray core using Python for reliability (requests is installed)
RUN python -c "import requests; \
    try: \
        r = requests.get('https://api.github.com/repos/XTLS/Xray-core/releases/latest', timeout=10); \
        r.raise_for_status(); \
        tag = r.json()['tag_name']; \
        print(tag); \
    except: \
        print('v1.8.23')" > xray_version.txt && \
    XRAY_VERSION=$(cat xray_version.txt) && \
    echo "Downloading Xray Core $XRAY_VERSION..." && \
    (wget -q --show-progress --tries=3 --timeout=30 "https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-64.zip" -O Xray-linux-64.zip || \
    wget -q --show-progress --tries=3 --timeout=30 "https://github.com/XTLS/Xray-core/releases/download/v1.8.4/Xray-linux-64.zip" -O Xray-linux-64.zip) && \
    unzip -o Xray-linux-64.zip && \
    chmod +x xray && \
    rm Xray-linux-64.zip xray_version.txt

# Copy application files
COPY main.py .
COPY core/ ./core/
COPY config/ ./config/
COPY utils/ ./utils/
COPY gui/ ./gui/

# Create output directories
RUN mkdir -p /app/subscriptions /app/logs /app/badges

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/app/subscriptions/subscription.txt') else 1)"

# Run in CLI mode by default
CMD ["python", "main.py", "--cli", "--max-configs", "200"]
