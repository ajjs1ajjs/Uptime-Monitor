FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY Uptime_Robot/ Uptime_Robot/

RUN pip install --no-cache-dir -e .

EXPOSE 8080

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["python", "-m", "Uptime_Robot", "--host", "0.0.0.0", "--port", "8080"]
