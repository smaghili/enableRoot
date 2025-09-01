#!/bin/bash

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
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Telegram Reminder Bot Setup  ${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

install_python() {
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
        print_status "Python $PYTHON_VERSION is already installed"
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

install_dependencies() {
    print_status "Installing dependencies..."
    if [ -f "requirements.txt" ]; then
        python3 -m pip install --user --break-system-packages -r requirements.txt
        print_status "Dependencies installed successfully"
    else
        print_error "requirements.txt not found!"
        exit 1
    fi
}

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

validate_bot_token() {
    local token="$1"
    if [[ $token =~ ^[0-9]{8,10}:[a-zA-Z0-9_-]{35}$ ]]; then
        return 0
    else
        return 1
    fi
}

validate_admin_id() {
    local admin_id="$1"
    if [[ $admin_id =~ ^[0-9]+$ ]] && [ ${#admin_id} -ge 5 ] && [ ${#admin_id} -le 12 ]; then
        return 0
    else
        return 1
    fi
}

collect_config() {
    print_status "Collecting configuration..."
    echo
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
    get_secure_input "🔑 Enter your OpenRouter API Key: " OPENROUTER_KEY false
    echo
    while true; do
        get_secure_input "👑 Enter your Telegram User ID (admin): " ADMIN_ID false
        if validate_admin_id "$ADMIN_ID"; then
            print_status "Admin ID format is valid"
            break
        else
            print_error "Invalid admin ID format. Must be 5-12 digits."
            print_warning "To get your ID, send /start to @userinfobot on Telegram"
        fi
    done
    echo
    print_status "Using default values for all other settings from config.json.example"
}

create_config_file() {
    print_status "Creating config.json file..."
    if [ ! -f "config.json.example" ]; then
        print_error "config.json.example not found!"
        exit 1
    fi
    cp config.json.example config.json
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/YOUR_BOT_TOKEN_HERE/$BOT_TOKEN/g" config.json
        sed -i '' "s/YOUR_OPENROUTER_API_KEY_HERE/$OPENROUTER_KEY/g" config.json
        sed -i '' "s/123456789/$ADMIN_ID/g" config.json
    else
        sed -i "s/YOUR_BOT_TOKEN_HERE/$BOT_TOKEN/g" config.json
        sed -i "s/YOUR_OPENROUTER_API_KEY_HERE/$OPENROUTER_KEY/g" config.json
        sed -i "s/123456789/$ADMIN_ID/g" config.json
    fi
    chmod 644 config.json
    print_status "config.json file created with secure permissions"
    print_status "Admin ID $ADMIN_ID has been configured as bot administrator"
}



create_directories() {
    print_status "Creating data directories..."
    mkdir -p data/users
    chmod 755 data
    chmod 755 data/users
    print_status "Data directories created with secure permissions"
}



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
        sudo systemctl start telegram-reminder-bot.service
        print_status "Systemd service created, enabled and started"
        print_status "Bot is now running automatically"
        print_status "Check status with: sudo systemctl status telegram-reminder-bot"
    else
        print_status "Starting bot manually..."
        nohup python3 bot.py > bot.log 2>&1 &
        print_status "Bot started in background (PID: $!)"
        print_status "Logs are being written to bot.log"
    fi
}

show_completion() {
    echo
    echo -e "${GREEN}🎉 Installation completed successfully!${NC}"
    echo
    echo -e "${BLUE}Installation completed!${NC}"
    echo "✅ Bot is now running automatically"
    echo
    echo "If you chose systemd service:"
    echo "• Bot is running as system service"
    echo "• Will auto-start on system boot"
    echo "• Check status: sudo systemctl status telegram-reminder-bot"
    echo
    echo "If you chose manual start:"
    echo "• Bot is running in background"
    echo "• Logs: tail -f bot.log"
    echo "• Stop: kill $(pgrep -f bot.py)"
    echo
    echo -e "${BLUE}Configuration files:${NC}"
    echo "• config.json - Main configuration (keep secure!)"
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

main() {
    print_header
    if [ ! -f "bot.py" ] || [ ! -f "requirements.txt" ]; then
        print_error "Please run this script from the telegram-reminder-bot directory"
        print_error "Required files (bot.py, requirements.txt) not found"
        exit 1
    fi
    print_status "Starting installation process..."
    install_python
    install_pip
    install_dependencies
    collect_config
    create_config_file
    create_directories
    create_systemd_service
    show_completion
}

trap 'print_error "Installation interrupted by user"; exit 1' INT

main "$@"
