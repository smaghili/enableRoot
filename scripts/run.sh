#!/bin/bash

# Telegram Reminder Bot Startup Script
# Version: 1.0

set -e
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}🤖 Starting Telegram Reminder Bot...${NC}"
    echo
}

check_packages() {
    print_status "Checking Python packages..."
    python3 -c "import aiogram, aiohttp, jdatetime" 2>/dev/null || {
        print_error "Missing packages! Run: pip install -r requirements.txt"
        exit 1
    }
}

check_dependencies() {
    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt not found!"
        exit 1
    fi
    
    print_status "Ensuring dependencies are installed..."
    python3 -m pip install --user --break-system-packages -q -r requirements.txt 2>/dev/null || true
}

validate_env() {
    print_status "Validating configuration..."
    
    if [ ! -f "config/config.json" ]; then
        print_error "config/config.json not found!"
        print_error "Please run ./install.sh to configure the bot"
        exit 1
    fi
    
    print_status "Configuration file found"
}

create_directories() {
    print_status "Creating data directories..."
    mkdir -p data/users
    chmod 700 data data/users 2>/dev/null || true
}

check_running() {
    if pgrep -f "python.*bot.py" > /dev/null; then
        print_warning "Bot appears to be already running!"
        echo -n "Do you want to stop it and restart? (y/N): "
        read restart_choice
        
        if [[ $restart_choice =~ ^[Yy]$ ]]; then
            print_status "Stopping existing bot process..."
            pkill -f "python.*bot.py" || true
            sleep 2
        else
            print_status "Startup cancelled"
            exit 0
        fi
    fi
}

start_bot() {
    print_status "Starting bot..."
    echo -e "${BLUE}Press Ctrl+C to stop the bot${NC}"
    echo
    trap 'print_status "Bot stopped by user"; exit 0' INT
    python3 bot.py
}

main() {
    print_header
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    BOT_DIR="$(dirname "$SCRIPT_DIR")"
    cd "$BOT_DIR"
    if [ ! -f "bot.py" ]; then
        print_error "bot.py not found!"
        print_error "Script directory structure might be incorrect"
        exit 1
    fi   
    check_packages
    check_dependencies
    validate_env
    create_directories
    check_running
    start_bot
}

main "$@"