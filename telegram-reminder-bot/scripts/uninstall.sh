#!/bin/bash

# Telegram Reminder Bot Uninstall Script
# Author: AI Assistant
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
    echo -e "${BLUE}===================================${NC}"
    echo -e "${BLUE}  Telegram Reminder Bot Uninstall  ${NC}"
    echo -e "${BLUE}===================================${NC}"
    echo
}

# Function to stop systemd service
stop_service() {
    if systemctl is-active --quiet telegram-reminder-bot 2>/dev/null; then
        print_status "Stopping telegram-reminder-bot service..."
        sudo systemctl stop telegram-reminder-bot
        sudo systemctl disable telegram-reminder-bot
        print_status "Service stopped and disabled"
    fi
    
    if [ -f "/etc/systemd/system/telegram-reminder-bot.service" ]; then
        print_status "Removing systemd service file..."
        sudo rm -f /etc/systemd/system/telegram-reminder-bot.service
        sudo systemctl daemon-reload
        print_status "Service file removed"
    fi
}

# Function to remove files
remove_files() {
    echo
    print_warning "This will remove the following:"
    echo "• Virtual environment (venv/)"
    echo "• Log files (*.log)"
    echo "• Compiled Python files (__pycache__/)"
    echo
    print_warning "The following will be KEPT:"
    echo "• Database and user data (data/)"
    echo "• Configuration file (.env)"
    echo "• Source code files"
    echo
    
    echo -n "Continue with cleanup? (y/N): "
    read confirm_cleanup
    
    if [[ $confirm_cleanup =~ ^[Yy]$ ]]; then
        print_status "Cleaning up installation files..."
        
        # Remove virtual environment
        if [ -d "venv" ]; then
            rm -rf venv
            print_status "Virtual environment removed"
        fi
        
        # Remove log files
        rm -f *.log
        print_status "Log files removed"
        
        # Remove Python cache
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find . -name "*.pyc" -delete 2>/dev/null || true
        print_status "Python cache files removed"
        
        print_status "Cleanup completed"
    else
        print_status "Cleanup cancelled"
    fi
}

# Function to remove data (optional)
remove_data() {
    echo
    echo -n "⚠️  Do you want to remove ALL data including database and user files? (y/N): "
    read confirm_data
    
    if [[ $confirm_data =~ ^[Yy]$ ]]; then
        print_warning "This action cannot be undone!"
        echo -n "Type 'DELETE' to confirm: "
        read confirm_delete
        
        if [ "$confirm_delete" = "DELETE" ]; then
            if [ -d "data" ]; then
                rm -rf data
                print_status "Data directory removed"
            fi
            
            if [ -f ".env" ]; then
                rm -f .env
                print_status "Configuration file removed"
            fi
            
            print_status "All data removed"
        else
            print_status "Data removal cancelled"
        fi
    fi
}

# Main uninstall function
main() {
    print_header
    
    # Check if we're in the right directory
    if [ ! -f "bot.py" ]; then
        print_error "Please run this script from the telegram-reminder-bot directory"
        exit 1
    fi
    
    print_status "Starting uninstall process..."
    
    stop_service
    remove_files
    remove_data
    
    echo
    print_status "Uninstall completed!"
    echo
    print_status "Thank you for using Telegram Reminder Bot! 🤖"
}

# Handle script interruption
trap 'print_error "Uninstall interrupted by user"; exit 1' INT

# Run main function
main "$@"
