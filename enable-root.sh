#!/bin/bash

# Check if the script is run as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

# Set root password
echo "Setting root password..."
passwd root

# Update SSH config to allow root login
SSHD_CONFIG="/etc/ssh/sshd_config"
echo "Updating SSH configuration to allow root login..."

# Backup original SSH config
cp $SSHD_CONFIG "$SSHD_CONFIG.bak"

# Modify PermitRootLogin setting
if grep -q "^PermitRootLogin" $SSHD_CONFIG; then
    sed -i "s/^PermitRootLogin.*/PermitRootLogin yes/" $SSHD_CONFIG
else
    echo "PermitRootLogin yes" >> $SSHD_CONFIG
fi

# Restart SSH service
echo "Restarting SSH service..."
systemctl restart sshd

echo "Root login is now enabled."

