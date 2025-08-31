#!/bin/bash

# Telegram Reminder Bot Installation Script
# Author: AI Assistant
# Version: 2.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Telegram Reminder Bot Setup  ${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install Python if not exists
install_python() {
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
        print_status "Python $PYTHON_VERSION is already installed"
        
        # Check if version is 3.7 or higher
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 7) else 1)"; then
            print_status "Python version is compatible"
        else
            print_error "Python 3.7 or higher is required"
            exit 1
        fi
    else
        print_status "Installing Python3..."
        if command_exists apt-get; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv
        elif command_exists yum; then
            sudo yum install -y python3 python3-pip
        elif command_exists brew; then
            brew install python3
        else
            print_error "Could not install Python3. Please install it manually."
            exit 1
        fi
    fi
}

# Function to install pip if not exists
install_pip() {
    if command_exists pip3; then
        print_status "pip3 is already installed"
    else
        print_status "Installing pip3..."
        if command_exists apt-get; then
            sudo apt-get install -y python3-pip
        elif command_exists yum; then
            sudo yum install -y python3-pip
        else
            print_status "Downloading pip installer..."
            curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
            python3 get-pip.py
            rm get-pip.py
        fi
    fi
}

# Function to install dependencies without venv
install_dependencies() {
    print_status "Installing dependencies..."
    
    # Install requirements
    if [ -f "requirements.txt" ]; then
        python3 -m pip install --user --break-system-packages -r requirements.txt
        print_status "Dependencies installed successfully"
    else
        print_error "requirements.txt not found!"
        exit 1
    fi
}

# Function to get user input securely
get_secure_input() {
    local prompt="$1"
    local var_name="$2"
    local is_secret="$3"
    
    while true; do
        if [ "$is_secret" = "true" ]; then
            echo -n "$prompt"
            read -s input
            echo
        else
            echo -n "$prompt"
            read input
        fi
        
        if [ -n "$input" ]; then
            eval "$var_name='$input'"
            break
        else
            print_error "This field cannot be empty. Please try again."
        fi
    done
}

# Function to validate bot token format
validate_bot_token() {
    local token="$1"
    if [[ $token =~ ^[0-9]{8,10}:[a-zA-Z0-9_-]{35}$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to collect configuration
collect_config() {
    print_status "Collecting configuration..."
    echo
    
    # Get Bot Token
    while true; do
        get_secure_input "🤖 Enter your Telegram Bot Token (from @BotFather): " BOT_TOKEN false
        if validate_bot_token "$BOT_TOKEN"; then
            print_status "Bot token format is valid"
            break
        else
            print_error "Invalid bot token format. Please check and try again."
            print_warning "Bot token should look like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        fi
    done
    
    echo
    
    # Get OpenRouter Key
    get_secure_input "🔑 Enter your OpenRouter API Key: " OPENROUTER_KEY false
    
    echo
    
    # Optional configurations
    echo -e "${BLUE}Optional Configuration (press Enter for defaults):${NC}"
    
    echo -n "📊 Maximum requests per minute per user (default: 20): "
    read MAX_REQUESTS
    MAX_REQUESTS=${MAX_REQUESTS:-20}
    
    echo -n "📝 Maximum reminders per user (default: 100): "
    read MAX_REMINDERS
    MAX_REMINDERS=${MAX_REMINDERS:-100}
    
    echo -n "🧹 Cleanup interval in hours (default: 24): "
    read CLEANUP_INTERVAL
    CLEANUP_INTERVAL=${CLEANUP_INTERVAL:-24}
    
    echo -n "📋 Log level (INFO/DEBUG/WARNING/ERROR, default: INFO): "
    read LOG_LEVEL
    LOG_LEVEL=${LOG_LEVEL:-INFO}
}

# Function to create .env file
create_env_file() {
    print_status "Creating .env file..."
    
    cat > .env << EOF
# Telegram Bot Configuration
BOT_TOKEN=$BOT_TOKEN
OPENROUTER_KEY=$OPENROUTER_KEY

# Rate Limiting
MAX_REQUESTS_PER_MINUTE=$MAX_REQUESTS
MAX_REMINDERS_PER_USER=$MAX_REMINDERS

# System Configuration
CLEANUP_INTERVAL_HOURS=$CLEANUP_INTERVAL
LOG_LEVEL=$LOG_LEVEL
EOF

    # Set secure permissions for .env file
    chmod 600 .env
    print_status ".env file created with secure permissions"
}

# Function to create data directories
create_directories() {
    print_status "Creating data directories..."
    
    mkdir -p data/users
    chmod 700 data
    chmod 700 data/users
    
    print_status "Data directories created with secure permissions"
}

# Function to test installation
test_installation() {
    print_status "Testing installation..."
    

    
    # Test Python imports
    python3 -c "
import sys
try:
    import aiogram
    import aiohttp
    import jdatetime
    print('✅ All required packages imported successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"
    
    # Test configuration with environment variables
    BOT_TOKEN="$BOT_TOKEN" OPENROUTER_KEY="$OPENROUTER_KEY" python3 -c "
import os
import sys
from config import Config
try:
    config = Config()
    config.validate()
    print('✅ Configuration is valid')
except Exception as e:
    print(f'❌ Configuration error: {e}')
    sys.exit(1)
"
    
    print_status "Installation test completed successfully"
}

# Function to create systemd service (optional)
create_systemd_service() {
    echo
    echo -n "🔧 Do you want to create a systemd service for auto-start? (y/N): "
    read create_service
    
    if [[ $create_service =~ ^[Yy]$ ]]; then
        print_status "Creating systemd service..."
        
        SERVICE_FILE="/etc/systemd/system/telegram-reminder-bot.service"
        CURRENT_DIR=$(pwd)
        CURRENT_USER=$(whoami)
        
        sudo tee $SERVICE_FILE > /dev/null << EOF
[Unit]
Description=Telegram Reminder Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
Environment=PATH=$CURRENT_DIR/venv/bin
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

        sudo systemctl daemon-reload
        sudo systemctl enable telegram-reminder-bot.service
        
        print_status "Systemd service created and enabled"
        print_status "You can start the bot with: sudo systemctl start telegram-reminder-bot"
        print_status "Check status with: sudo systemctl status telegram-reminder-bot"
    fi
}

# Function to show completion message
show_completion() {
    echo
    echo -e "${GREEN}🎉 Installation completed successfully!${NC}"
    echo
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Start the bot:"
    echo -e "   ${YELLOW}./run.sh${NC}"
    echo
    echo "2. Or activate virtual environment and run manually:"
    echo -e "   ${YELLOW}source venv/bin/activate${NC}"
    echo -e "   ${YELLOW}python bot.py${NC}"
    echo
    echo "3. Run tests (optional):"
    echo -e "   ${YELLOW}source venv/bin/activate${NC}"
    echo -e "   ${YELLOW}python run_tests.py${NC}"
    echo
    echo -e "${BLUE}Configuration files:${NC}"
    echo "• .env - Environment variables (keep secure!)"
    echo "• data/ - Database and user data directory"
    echo "• bot.log - Application logs"
    echo
    echo -e "${BLUE}Useful commands:${NC}"
    echo "• View logs: tail -f bot.log"
    echo "• Stop bot: Ctrl+C (if running manually)"
    echo "• Update bot: git pull && ./install.sh"
    echo
    print_status "Happy bot running! 🤖"
}

# Main installation function
main() {
    print_header
    

    
    # Check if we're in the right directory
    if [ ! -f "bot.py" ] || [ ! -f "requirements.txt" ]; then
        print_error "Please run this script from the telegram-reminder-bot directory"
        print_error "Required files (bot.py, requirements.txt) not found"
        exit 1
    fi
    
    print_status "Starting installation process..."
    
    # Installation steps
    install_python
    install_pip
    install_dependencies
    collect_config
    create_env_file
    create_directories
    test_installation
    create_systemd_service
    show_completion
}

# Handle script interruption
trap 'print_error "Installation interrupted by user"; exit 1' INT

# Run main function
main "$@"
