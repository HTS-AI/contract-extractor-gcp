# =========================================
# Stage 1: Build Frontend (Vite)
# =========================================
FROM node:20-slim AS frontend-build

WORKDIR /frontend

# Copy only package files first (better layer caching)
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Fix permission issue for vite binary
RUN chmod -R 755 node_modules/.bin

# Copy frontend source code
COPY frontend/ ./

# Build production files (outputs to dist/)
RUN npm run build


# =========================================
# Stage 2: Backend + Serve Built Frontend
# =========================================
FROM python:3.10-slim

WORKDIR /app

# Install minimal system dependencies (only if required)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend from Stage 1
COPY --from=frontend-build /frontend/dist ./frontend_build

# Cloud Run requires listening on $PORT
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

# Start FastAPI using uvicorn
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
