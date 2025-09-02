#!/bin/bash

# Telegram Reminder Bot Management Script
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
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Telegram Reminder Bot Manager ${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Commands:"
    echo "  start       Start the bot"
    echo "  stop        Stop the bot"
    echo "  restart     Restart the bot"
    echo "  status      Show bot status"
    echo "  logs        Show bot logs"
    echo "  test        Run tests"
    echo "  update      Update the bot"
    echo "  backup      Backup data"
    echo "  restore     Restore data"
    echo "  stats       Show database statistics"
    echo "  help        Show this help message"
    echo
}

# Function to check if bot is running
is_bot_running() {
    pgrep -f "python.*bot.py" > /dev/null
}

# Function to start bot
start_bot() {
    if is_bot_running; then
        print_warning "Bot is already running!"
        return 1
    fi
    
    print_status "Starting bot..."
    ./run.sh &
    sleep 2
    
    if is_bot_running; then
        print_status "Bot started successfully"
    else
        print_error "Failed to start bot"
        return 1
    fi
}

# Function to stop bot
stop_bot() {
    if ! is_bot_running; then
        print_warning "Bot is not running"
        return 1
    fi
    
    print_status "Stopping bot..."
    pkill -f "python.*bot.py" || true
    sleep 2
    
    if ! is_bot_running; then
        print_status "Bot stopped successfully"
    else
        print_error "Failed to stop bot"
        return 1
    fi
}

# Function to restart bot
restart_bot() {
    print_status "Restarting bot..."
    stop_bot || true
    sleep 1
    start_bot
}

# Function to show status
show_status() {
    if is_bot_running; then
        PID=$(pgrep -f "python.*bot.py")
        print_status "Bot is running (PID: $PID)"
        
        # Show memory usage
        if command -v ps >/dev/null 2>&1; then
            MEM=$(ps -p $PID -o %mem --no-headers 2>/dev/null | tr -d ' ')
            echo "Memory usage: ${MEM}%"
        fi
        
        # Show uptime
        if command -v ps >/dev/null 2>&1; then
            ETIME=$(ps -p $PID -o etime --no-headers 2>/dev/null | tr -d ' ')
            echo "Uptime: $ETIME"
        fi
    else
        print_warning "Bot is not running"
    fi
    
    # Check systemd service if exists
    if systemctl is-active --quiet telegram-reminder-bot 2>/dev/null; then
        print_status "Systemd service is active"
    elif systemctl is-enabled --quiet telegram-reminder-bot 2>/dev/null; then
        print_warning "Systemd service is enabled but not active"
    fi
}

# Function to show logs
show_logs() {
    if [ -f "bot.log" ]; then
        print_status "Showing bot logs (last 50 lines):"
        echo
        tail -n 50 bot.log
    else
        print_warning "No log file found"
    fi
}

# Function to run tests
run_tests() {
    if [ ! -d "venv" ]; then
        print_error "Virtual environment not found. Please run ./install.sh first"
        return 1
    fi
    
    print_status "Running tests..."
    source venv/bin/activate
    python run_tests.py
}

# Function to update bot
update_bot() {
    print_status "Updating bot..."
    
    # Check if git is available
    if ! command -v git >/dev/null 2>&1; then
        print_error "Git is not installed"
        return 1
    fi
    
    # Check if we're in a git repository
    if [ ! -d ".git" ]; then
        print_error "Not a git repository"
        return 1
    fi
    
    # Stop bot if running
    if is_bot_running; then
        print_status "Stopping bot for update..."
        stop_bot
        RESTART_AFTER_UPDATE=true
    fi
    
    # Pull latest changes
    git pull
    
    # Reinstall dependencies
    if [ -d "venv" ]; then
        source venv/bin/activate
        pip install -r requirements.txt
    fi
    
    # Restart bot if it was running
    if [ "$RESTART_AFTER_UPDATE" = true ]; then
        print_status "Restarting bot..."
        start_bot
    fi
    
    print_status "Update completed"
}

# Function to backup data
backup_data() {
    BACKUP_DIR="backups"
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
    
    print_status "Creating backup..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Create backup
    tar -czf "$BACKUP_FILE" data/ .env 2>/dev/null || {
        print_error "Failed to create backup"
        return 1
    }
    
    print_status "Backup created: $BACKUP_FILE"
    
    # Keep only last 10 backups
    ls -t "$BACKUP_DIR"/backup_*.tar.gz | tail -n +11 | xargs -r rm
    print_status "Old backups cleaned up"
}

# Function to restore data
restore_data() {
    BACKUP_DIR="backups"
    
    if [ ! -d "$BACKUP_DIR" ]; then
        print_error "No backup directory found"
        return 1
    fi
    
    # List available backups
    BACKUPS=($(ls -t "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null))
    
    if [ ${#BACKUPS[@]} -eq 0 ]; then
        print_error "No backups found"
        return 1
    fi
    
    echo "Available backups:"
    for i in "${!BACKUPS[@]}"; do
        echo "$((i+1)). $(basename "${BACKUPS[$i]}")"
    done
    
    echo -n "Select backup to restore (1-${#BACKUPS[@]}): "
    read selection
    
    if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le ${#BACKUPS[@]} ]; then
        BACKUP_FILE="${BACKUPS[$((selection-1))]}"
        
        print_warning "This will overwrite current data!"
        echo -n "Continue? (y/N): "
        read confirm
        
        if [[ $confirm =~ ^[Yy]$ ]]; then
            # Stop bot if running
            if is_bot_running; then
                stop_bot
                RESTART_AFTER_RESTORE=true
            fi
            
            print_status "Restoring from $BACKUP_FILE..."
            tar -xzf "$BACKUP_FILE"
            
            if [ "$RESTART_AFTER_RESTORE" = true ]; then
                start_bot
            fi
            
            print_status "Restore completed"
        else
            print_status "Restore cancelled"
        fi
    else
        print_error "Invalid selection"
        return 1
    fi
}

# Function to show database statistics
show_stats() {
    if [ ! -d "venv" ]; then
        print_error "Virtual environment not found"
        return 1
    fi
    
    if [ ! -f "data/reminders.db" ]; then
        print_warning "Database not found"
        return 1
    fi
    
    print_status "Database statistics:"
    
    source venv/bin/activate
    python3 -c "
from database import Database
import os

if os.path.exists('data/reminders.db'):
    db = Database('data/reminders.db')
    stats = db.get_stats()
    if stats:
        print(f'Total reminders: {stats[0]}')
        print(f'Active reminders: {stats[1]}')
        print(f'Completed reminders: {stats[2]}')
        print(f'Cancelled reminders: {stats[3]}')
        print(f'Unique users: {stats[4]}')
    db.close()
else:
    print('Database file not found')
"
}

# Main function
main() {
    case "${1:-help}" in
        start)
            start_bot
            ;;
        stop)
            stop_bot
            ;;
        restart)
            restart_bot
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        test)
            run_tests
            ;;
        update)
            update_bot
            ;;
        backup)
            backup_data
            ;;
        restore)
            restore_data
            ;;
        stats)
            show_stats
            ;;
        help|--help|-h)
            print_header
            show_usage
            ;;
        *)
            print_error "Unknown command: $1"
            echo
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
