FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN mkdir -p /app/policies /app/data

EXPOSE 8000

CMD ["uvicorn", "mig_core:app", "--host", "0.0.0.0", "--port", "8000"]
