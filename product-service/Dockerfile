FROM python:3.11-slim

WORKDIR /app

COPY product-service /app/product-service

RUN pip install --no-cache-dir -r product-service/requirements.txt

COPY shared /app/shared
RUN pip install --no-cache-dir -e /app/shared

WORKDIR /app/product-service

EXPOSE 5001

CMD ["gunicorn", "main:app", "--host", "0.0.0.0", "--port", "5001", "--workers", "4", "--threads", "2", "--reload"]


