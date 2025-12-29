#!/bin/bash
# Wrapper script for log cleanup cronjob

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to service directory
cd "$SERVICE_DIR" || exit 1

# Run the Python cleanup script
# Use python3 from the system or venv
if [ -f "$SERVICE_DIR/venv/bin/python3" ]; then
    "$SERVICE_DIR/venv/bin/python3" "$SERVICE_DIR/scripts/cleanup_logs.py" >> /tmp/cleanup_logs_cron.log 2>&1
elif [ -f "/app/product-service/venv/bin/python3" ]; then
    /app/product-service/venv/bin/python3 /app/product-service/scripts/cleanup_logs.py >> /tmp/cleanup_logs_cron.log 2>&1
else
    python3 "$SERVICE_DIR/scripts/cleanup_logs.py" >> /tmp/cleanup_logs_cron.log 2>&1
fi

