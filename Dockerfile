FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

COPY . /app/

EXPOSE 8080

CMD ["python", "-m", "cf_sync.api.server", "--host", "0.0.0.0", "--port", "8080"]
