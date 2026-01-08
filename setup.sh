#!/bin/bash
# Setup script for V2Ray Tester Pro on Linux/macOS

echo "🚀 V2Ray Tester Pro - Setup Script"
echo "=================================="

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.11+ is required. You have Python $python_version"
    exit 1
fi
echo "✅ Python $python_version detected"

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# Download Xray core
echo ""
echo "⬇️  Downloading Xray Core..."
XRAY_VERSION=$(curl -s https://api.github.com/repos/XTLS/Xray-core/releases/latest | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
echo "Latest version: $XRAY_VERSION"

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    XRAY_FILE="Xray-linux-64.zip"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    XRAY_FILE="Xray-macos-64.zip"
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

wget https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/${XRAY_FILE}
unzip -o ${XRAY_FILE}
chmod +x xray
rm ${XRAY_FILE}
echo "✅ Xray Core installed"

# Create .env file
echo ""
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "✅ .env file created. Please edit it with your settings."
else
    echo "ℹ️  .env file already exists"
fi

# Create directories
echo ""
echo "📁 Creating directories..."
mkdir -p subscriptions logs
echo "✅ Directories created"

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To run the application:"
echo "  GUI mode: python3 'v2raytesterpro source.py'"
echo "  CLI mode: python3 'v2raytesterpro source.py' --cli"
echo ""
echo "Don't forget to edit the .env file with your configuration!"
