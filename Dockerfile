# Backend Dockerfile for Biome Coaching Agent
# Optimized for Cloud Run deployment with MediaPipe and ADK

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for MediaPipe and OpenCV
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY biome_coaching_agent/ ./biome_coaching_agent/
COPY db/ ./db/
COPY api_server.py .
COPY schema.sql .

# Create uploads directory
RUN mkdir -p uploads

# Cloud Run sets PORT environment variable (defaults to 8080)
# Our app reads from PORT env var
ENV PORT=8080

# Expose the port
EXPOSE 8080

# Health check (using curl instead of requests library)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Start the FastAPI server
# Use PORT from environment (Cloud Run requirement)
CMD uvicorn api_server:app --host 0.0.0.0 --port $PORT --workers 1

