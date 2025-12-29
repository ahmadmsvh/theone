FROM python:3.11-slim

WORKDIR /app

# Install cron for scheduled tasks
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    && rm -rf /var/lib/apt/lists/*

COPY product-service /app/product-service

RUN pip install --no-cache-dir -r product-service/requirements.txt

COPY shared /app/shared
RUN pip install --no-cache-dir -e /app/shared

WORKDIR /app/product-service

# Make cleanup scripts executable
RUN chmod +x /app/product-service/scripts/cleanup_logs.py \
    && chmod +x /app/product-service/scripts/cleanup_logs.sh

# Set up cron job (crontab file should be in product-service/scripts/)
RUN if [ -f /app/product-service/scripts/crontab ]; then \
        crontab /app/product-service/scripts/crontab; \
    fi

# Create log file for cron output
RUN touch /tmp/cleanup_logs_cron.log

# Start cron service in the background and run the main application
CMD ["sh", "-c", "cron & exec gunicorn main:app --host 0.0.0.0 --port 5001 --workers 4 --threads 2 --reload"]


