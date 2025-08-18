#!/usr/bin/env bash
# Script to run before installing the new application version.
set -e
APP_DIR="/var/www/app"
if [ -d "$APP_DIR" ]; then
    echo "Cleaning up old application directory: $APP_DIR"
    rm -rf "$APP_DIR"
fi 