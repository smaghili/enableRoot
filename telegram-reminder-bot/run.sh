#!/bin/bash

# Telegram Reminder Bot Startup Script

echo "🤖 Starting Telegram Reminder Bot..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check environment variables
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ BOT_TOKEN environment variable not set!"
    echo "Please set it with: export BOT_TOKEN='your_bot_token'"
    exit 1
fi

if [ -z "$OPENROUTER_KEY" ]; then
    echo "❌ OPENROUTER_KEY environment variable not set!"
    echo "Please set it with: export OPENROUTER_KEY='your_api_key'"
    exit 1
fi

# Create data directories
mkdir -p data/users

echo "✅ Starting bot..."
python bot.py