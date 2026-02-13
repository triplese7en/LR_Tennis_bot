#!/bin/bash

# Tennis Court Booking Bot - Setup Script
# This script sets up the bot environment and dependencies

set -e

echo "🎾 Tennis Court Booking Bot - Setup"
echo "===================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.8+ required. Found: $python_version"
    exit 1
fi
echo "✅ Python version OK: $python_version"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "✅ Virtual environment created"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip
echo "✅ pip upgraded"
echo ""

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Install Chrome and ChromeDriver (Ubuntu/Debian)
if command -v apt-get &> /dev/null; then
    echo "Detected Debian/Ubuntu system"
    echo "Installing Chrome and ChromeDriver..."
    
    # Install Chrome
    if ! command -v google-chrome &> /dev/null; then
        wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
        echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
        sudo apt-get update
        sudo apt-get install -y google-chrome-stable
        echo "✅ Chrome installed"
    else
        echo "✅ Chrome already installed"
    fi
    
    # ChromeDriver will be managed by webdriver-manager
    echo "✅ ChromeDriver will be auto-managed"
fi
echo ""

# Create directories
echo "Creating required directories..."
mkdir -p logs screenshots data config
echo "✅ Directories created"
echo ""

# Copy config template
if [ ! -f "config/config.json" ]; then
    echo "Creating config.json from template..."
    cp config/config.json config/config.json.backup 2>/dev/null || true
    echo "⚠️  Please edit config/config.json and add your Telegram bot token"
fi
echo ""

# Copy .env template
if [ ! -f ".env" ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your credentials"
fi
echo ""

# Set permissions
echo "Setting file permissions..."
chmod +x setup.sh
chmod 755 src/*.py
echo "✅ Permissions set"
echo ""

# Test installation
echo "Testing installation..."
python3 -c "import telegram; import selenium; print('✅ All modules imported successfully')"
echo ""

# Display next steps
echo "======================================"
echo "✅ Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Edit config/config.json and add your Telegram bot token"
echo "2. (Optional) Edit .env for additional configuration"
echo "3. Run the bot: python3 src/telegram_bot.py"
echo ""
echo "For production deployment:"
echo "- Docker: docker-compose up -d"
echo "- Systemd: sudo cp tennis-bot.service /etc/systemd/system/ && sudo systemctl enable tennis-bot"
echo ""
echo "Need help? Check README.md"
echo ""
