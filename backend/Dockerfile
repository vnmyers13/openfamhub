FROM python:3.12-alpine

LABEL version="0.28"
LABEL description="OpenFamHub API Backend"

WORKDIR /app

RUN apk add --no-cache curl

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app
RUN mkdir -p /data/db /data/photos /data/backups && chown -R app:app /data

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
