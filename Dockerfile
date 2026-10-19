FROM python:3.14-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[telemetry]"

USER nobody
EXPOSE 8000
CMD ["opentelemetry-instrument", "uvicorn", "hello_api.main:app_from_environment", "--factory", "--host", "0.0.0.0", "--port", "8000"]
