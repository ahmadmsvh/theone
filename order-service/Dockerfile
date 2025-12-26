FROM python:3.11-slim

WORKDIR /app

COPY order-service /app/order-service

RUN pip install --no-cache-dir -r order-service/requirements.txt

COPY shared /app/shared
RUN pip install --no-cache-dir -e /app/shared

WORKDIR /app/order-service

EXPOSE 8002

CMD ["gunicorn", "main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8002"]

