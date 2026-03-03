# ======================================================
# Stage 1 — Build Frontend (React + Vite)
# ======================================================
FROM node:20-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

# Fix vite permission issue
RUN chmod -R 755 node_modules

RUN npm run build



# ======================================================
# Stage 2 — Python Backend
# ======================================================
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy EVERYTHING except frontend (important)
COPY . .

# Remove frontend source (not needed in final image)
RUN rm -rf frontend

# Copy built frontend from stage 1
COPY --from=frontend-build /frontend/dist ./frontend_build

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
