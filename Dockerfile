# Deploy on Cloud Run / any container host
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Gunicorn for production
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "app:app"]
