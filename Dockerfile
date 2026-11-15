# Stage 1: build the web interface
FROM node:22-slim AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# Stage 2: Python app that serves the API and the built web files
FROM python:3.13-slim
WORKDIR /app
# git is needed to read your public GitHub repositories
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-api.txt
COPY . .
COPY --from=web /web/out ./web/out
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
# Keys come from environment variables; your data lives in the /app/.crackmate volume.
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
