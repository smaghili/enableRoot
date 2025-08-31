#!/bin/bash

# Telegram Reminder Bot Startup Script
# Version: 2.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Function to load .env file
load_env() {
    if [ -f ".env" ]; then
        print_status "Loading environment variables from .env file..."
        export $(grep -v '^#' .env | xargs)
    else
        print_warning ".env file not found. Using system environment variables..."
    fi
}

# Function to check Python packages
check_packages() {
    print_status "Checking Python packages..."
    
    python3 -c "
try:
    import aiogram, aiohttp, jdatetime
except ImportError as e:
    print(f'Missing package: {e}')
    print('Please run ./install.sh first')
    exit(1)
" || exit 1
}

# Function to check dependencies
check_dependencies() {
    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt not found!"
        exit 1
    fi
    
    print_status "Ensuring dependencies are installed..."
    python3 -m pip install --user --break-system-packages -q -r requirements.txt 2>/dev/null || true
}

# Function to validate environment variables
validate_env() {
    print_status "Validating configuration..."
    
    if [ -z "$BOT_TOKEN" ]; then
        print_error "BOT_TOKEN environment variable not set!"
        print_error "Please run ./install.sh to configure the bot"
        exit 1
    fi

    if [ -z "$OPENROUTER_KEY" ]; then
        print_error "OPENROUTER_KEY environment variable not set!"
        print_error "Please run ./install.sh to configure the bot"
        exit 1
    fi
    
    # Validate bot token format
    if [[ ! $BOT_TOKEN =~ ^[0-9]{8,10}:[a-zA-Z0-9_-]{35}$ ]]; then
        print_error "Invalid BOT_TOKEN format!"
        print_error "Please check your bot token and run ./install.sh again"
        exit 1
    fi
    
    print_status "Configuration is valid"
}

# Function to create directories
create_directories() {
    print_status "Creating data directories..."
    mkdir -p data/users
    chmod 700 data data/users 2>/dev/null || true
}

# Function to check if bot is already running
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

# Function to start the bot
start_bot() {
    print_status "Starting bot..."
    echo -e "${BLUE}Press Ctrl+C to stop the bot${NC}"
    echo
    
    # Handle interruption gracefully
    trap 'print_status "Bot stopped by user"; exit 0' INT
    
    python3 bot.py
}

# Main function
main() {
    print_header
    
    # Check if we're in the right directory
    if [ ! -f "bot.py" ]; then
        print_error "bot.py not found!"
        print_error "Please run this script from the telegram-reminder-bot directory"
        exit 1
    fi
    
    load_env
    check_packages
    check_dependencies
    validate_env
    create_directories
    check_running
    start_bot
}

# Run main function
main "$@"