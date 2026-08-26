FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY scripts ./scripts
COPY deploy ./deploy
COPY .env.example ./
RUN pip install --no-cache-dir ".[api,dashboard]"

EXPOSE 8000 8501

ENV TRADING_MODE=paper
CMD ["python", "-m", "uvicorn", "app.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
