FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/ apps/
COPY packages/ packages/
COPY infrastructure/ infrastructure/
COPY pyproject.toml .

RUN pip install --no-cache-dir \
    -e packages/trading-core \
    -e packages/exchange \
    -e apps/api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
