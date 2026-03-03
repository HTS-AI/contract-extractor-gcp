# Stage 1: Build Frontend (Vite)
FROM node:18-alpine AS frontend-build
WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN chmod -R 755 node_modules/.bin
RUN npm run build


# Stage 2: Production Backend + Serve Frontend
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/

# Copy Vite build output
COPY --from=frontend-build /frontend/dist ./frontend_build

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

WORKDIR /app/backend
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
