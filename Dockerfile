FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
COPY prompts ./prompts
COPY data ./data
COPY frontend ./frontend

RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir "uvicorn[standard]"

RUN python scripts/build_reference_data.py

ENV APP_MODE=mock
EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
