# Stage 1: Build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# GitHub link on the results page (Vite inlines it at build time)
ARG VITE_REPO_URL=https://github.com/BuildWithInfovion/triagerace
ENV VITE_REPO_URL=$VITE_REPO_URL
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.11-slim
WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy sample repos and scenarios (needed at runtime)
COPY sample_repos/ ./sample_repos/
COPY scenarios/ ./scenarios/

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Set environment defaults
ENV TRIAGERACE_ENV=production
ENV TRIAGERACE_DB=/app/data/triagerace.db

# Create data directory for the DB
RUN mkdir -p /app/data

EXPOSE 8000

# Render (and most PaaS) inject $PORT; fall back to 8000 locally
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir backend"]
