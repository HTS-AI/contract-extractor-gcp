# =========================================
# Stage 1: Build Frontend (Vite)
# =========================================
FROM node:20-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

# Use npm exec to avoid permission issue
RUN npm exec vite build


# =========================================
# Stage 2: Backend + Serve Built Frontend
# =========================================
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

COPY --from=frontend-build /frontend/dist ./frontend_build

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
