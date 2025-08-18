#!/usr/bin/env bash
# Script to start the customer's application.
# This is a placeholder. Customers should replace this with the actual command to start their service.
set -e
APP_DIR="/var/www/app"
LOG_FILE="/tmp/codedeploy-start-app.log"
echo "--- Starting ApplicationStart hook ---" > "$LOG_FILE"
# Example: Start a simple Python web server in the background
# if [ -f "$APP_DIR/main.py" ]; then
#     echo "Starting main.py" >> "$LOG_FILE"
#     nohup python3.11 "$APP_DIR/main.py" > /tmp/app.log 2>&1 &
# fi
echo "ApplicationStart hook finished. If you have a long-running process, it should be running now." >> "$LOG_FILE" 