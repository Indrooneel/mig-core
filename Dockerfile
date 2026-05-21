FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY policies/ ./policies/

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "mig_core.py"]
