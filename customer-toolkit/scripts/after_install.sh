#!/usr/bin/env bash
# Script to run after the new application version is installed.
set -e

APP_DIR="/var/www/app"
META_FILE="/opt/codedeploy-scripts/customer/deployment_meta.json"
LOG_FILE="/tmp/codedeploy-after-install.log"

# Function to send email notification
send_notification() {
    local status=$1
    local message=$2
    local email_subject="Deployment Status: $status"
    local email_body="Deployment to your instance has finished with status: $status.

Details:
$message

Timestamp: $(date)
"
    # Retrieve email from metadata file
    local to_email=$(jq -r .notification_email "$META_FILE")
    # Retrieve agent email from instance config
    local from_email=$(cat /etc/agent_email)
    
    # Retrieve region from instance metadata (IMDSv2)
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    local region=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .region)

    echo "Sending '$status' notification to $to_email from $from_email" >> "$LOG_FILE"
    
    # Print the command parameters for debugging
    echo "DEBUG AWS CLI command: aws ses send-email --from \"$from_email\" --to \"$to_email\" --subject \"$email_subject\" --text \"$email_body\" --region \"$region\"" >> "$LOG_FILE"
    
    aws ses send-email \
        --from "$from_email" \
        --to "$to_email" \
        --subject "$email_subject" \
        --text "$email_body" \
        --region "$region" >> "$LOG_FILE" 2>&1
}

echo "--- Starting AfterInstall hook ---" > "$LOG_FILE"

# Attempt to shut down any running server. Don't exit if it fails.
echo "Attempting to shut down existing server..." >> "$LOG_FILE"
shutdown_server >> "$LOG_FILE" 2>&1 || true

# Install Python dependencies
if [ -f "$APP_DIR/requirements.txt" ]; then
    echo "Found requirements.txt, installing dependencies..." >> "$LOG_FILE"
    if python3.11 -m pip install -r "$APP_DIR/requirements.txt" >> "$LOG_FILE" 2>&1; then
        echo "Dependencies installed successfully." >> "$LOG_FILE"
        send_notification "SUCCESS" "Application dependencies were installed successfully. The application is ready to be started."
    else
        echo "Failed to install dependencies." >> "$LOG_FILE"
        send_notification "FAILURE" "Could not install dependencies from requirements.txt. Please check the logs on the instance. Log file: $LOG_FILE"
        exit 1
    fi
else
    echo "No requirements.txt found, skipping dependency installation." >> "$LOG_FILE"
    send_notification "SUCCESS" "No requirements.txt file found. Deployment is considered successful."
fi

echo "--- Finished AfterInstall hook ---" >> "$LOG_FILE"
exit 0 