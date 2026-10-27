FROM python:3.14-slim

ENV PYTHONPYCACHEPREFIX=/tmp/pycache \
    PYTHONUNBUFFERED=1 \
    PDM_CHECK_UPDATE=false

WORKDIR /app
COPY --from=grafana/k6:1.3.0 /usr/bin/k6 /usr/local/bin/k6
RUN pip install --no-cache-dir "pdm==2.29.1" "unearth==0.18.3" "hishel==1.3.1"
COPY pyproject.toml pdm.lock README.md ./
COPY src ./src
RUN pdm install --frozen-lockfile --no-editable
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN /app/.venv/bin/playwright install --with-deps --only-shell chromium

USER nobody
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "gherkin_runner.main:app_from_environment", "--factory", "--host", "0.0.0.0", "--port", "8000"]
