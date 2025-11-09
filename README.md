# Biome Backend - AI Fitness Form Coach

**Cloud Run Hackathon 2025 - AI Agents Category**

## Tech Stack

* Google ADK + Gemini 2.0 Flash
* FastAPI + Uvicorn
* MediaPipe Pose
* PostgreSQL

## Features

* Generic smart analysis for 100+ exercises
* Token optimization (1.2M → 5K tokens)
* Real-time form feedback with coaching cues
* Production-ready error handling

## Quick Start

```bash
pip install -r requirements.txt
python api_server.py
```

## Deploy to Cloud Run

```bash
gcloud run deploy biome-backend \
  --source . \
  --region us-central1 \
  --memory 4Gi \
  --cpu 2 \
  --timeout 300s \
  --allow-unauthenticated
```

## Architecture

See `docs/ARCHITECTURE.md` for complete system design.

