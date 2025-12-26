FROM python:3.11-slim

WORKDIR /app

COPY auth-service /app/auth-service

RUN pip install --no-cache-dir -r auth-service/requirements.txt

COPY shared /app/shared
RUN pip install --no-cache-dir -e /app/shared

WORKDIR /app/auth-service

EXPOSE 8001

CMD ["gunicorn", "--bind", "0.0.0.0:8001", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "main:app"]
# gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
