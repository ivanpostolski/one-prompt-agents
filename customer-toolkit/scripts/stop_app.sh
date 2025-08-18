#!/usr/bin/env bash
# Script to stop the customer's application.
# This is a placeholder. Customers should replace this with the actual command to stop their service.
set -e
LOG_FILE="/tmp/codedeploy-stop-app.log"
echo "--- Starting ApplicationStop hook ---" > "$LOG_FILE"
# Example: Find and kill a running Python process.
# This is a simple example and might not be suitable for all applications.
# pkill -f 'python3.11 /var/www/app/main.py' || echo "No process to kill"
echo "ApplicationStop hook finished. Any long-running processes should be stopped now." >> "$LOG_FILE" 