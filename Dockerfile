FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY advisor ./advisor

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "advisor.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
