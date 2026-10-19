FROM python:3.14-slim

WORKDIR /app
RUN pip install --no-cache-dir \
    "fastapi>=0.136.0,<0.137.0" \
    "uvicorn>=0.49.0,<0.50.0" \
    "pymysql>=1.1.0,<2.0.0" \
    "opentelemetry-distro==0.66b1" \
    "opentelemetry-exporter-otlp-proto-http>=1.45.0,<2.0.0" \
    "opentelemetry-instrumentation-fastapi==0.66b1" \
    "opentelemetry-instrumentation-pymysql==0.66b1"
COPY app.py ./

USER nobody
EXPOSE 8000
CMD ["opentelemetry-instrument", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
