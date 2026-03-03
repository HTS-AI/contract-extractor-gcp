# ======================================================
# Stage 1 — Build Frontend (React + Vite)
# ======================================================
FROM node:20-slim AS frontend-build

WORKDIR /frontend

# Copy package files first (better caching)
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy rest of frontend code
COPY frontend/ ./

# Fix permission issue for vite (IMPORTANT)
RUN chmod -R 755 node_modules

# Build frontend
RUN npm run build



# ======================================================
# Stage 2 — Backend (FastAPI)
# ======================================================
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend from Stage 1
COPY --from=frontend-build /frontend/dist ./frontend_build

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

# Start FastAPI app
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
