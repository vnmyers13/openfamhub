FROM python:3.12-slim
ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="openfamhub-api" \
      org.opencontainers.image.version=$APP_VERSION

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_PATH=/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set by `deploy.sh publish` (e.g. 0.30.17 and the short git SHA); reported by /api/health.
ARG OPENFAMHUB_BUILD=dev
ARG OPENFAMHUB_COMMIT=unknown
ENV OPENFAMHUB_BUILD=$OPENFAMHUB_BUILD \
    OPENFAMHUB_COMMIT=$OPENFAMHUB_COMMIT

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
