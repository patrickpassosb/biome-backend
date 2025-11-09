# Biome Coaching Agent - System Architecture

> **Built for Cloud Run Hackathon 2025** 🏆  
> **Category:** AI Agents  
> **Tech Stack:** Google ADK + Gemini 2.0 Flash + MediaPipe + FastAPI + React

---

## 🏗️ System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           USER INTERACTION                                │
│                    (Web Browser / Mobile Device)                          │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
                              │ Upload Video (MP4/MOV/WebM)
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    REACT FRONTEND (PORT 8001)                             │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  Components:                                                         │ │
│  │  • Landing Page (Hero + CTA)                                        │ │
│  │  • Upload UI (Drag-drop + Webcam recording)                         │ │
│  │  • Analyzing Page (Real-time agent status)                          │ │
│  │  • Results Display (Score + Issues + Video player with markers)    │ │
│  │                                                                       │ │
│  │  Tech: React 19 + TypeScript + Tailwind CSS + React Router          │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
                              │ HTTP POST /api/analyze (FormData)
                              │ Environment: REACT_APP_API_URL
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│               FASTAPI BACKEND (PORT 8000 / Cloud Run: 8080)              │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  Endpoints:                                                          │ │
│  │  • POST /api/analyze      - Main analysis endpoint (video upload)   │ │
│  │  • GET  /api/results/{id} - Fetch analysis results                  │ │
│  │  • GET  /health           - Health check (DB + MediaPipe + ADK)     │ │
│  │  • GET  /                 - API info                                 │ │
│  │                                                                       │ │
│  │  Features:                                                           │ │
│  │  • CORS enabled for frontend                                         │ │
│  │  • File validation (size, type, extension)                          │ │
│  │  • Error handling with structured responses                          │ │
│  │  • Logging (console + file)                                          │ │
│  │                                                                       │ │
│  │  Tech: FastAPI + Uvicorn + Pydantic                                  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │
                              │ Initializes & Orchestrates
                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     GOOGLE ADK AGENT (Root Agent)                         │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  Configuration:                                                      │ │
│  │  • Name: biome_coaching_agent                                        │ │
│  │  • Model: gemini-2.0-flash (fast + cost-effective)                  │ │
│  │  • Runner: InMemoryRunner (ADK orchestration)                        │ │
│  │  • Reasoning: Form analysis + coaching feedback generation           │ │
│  │                                                                       │ │
│  │  Instruction Prompt Includes:                                        │ │
│  │  • Workflow: 4-step tool execution sequence                         │ │
│  │  • Squat form standards (knee angle, hip angle, alignment)          │ │
│  │  • Coaching guidelines (encouraging, specific, actionable)          │ │
│  │  • Severity scoring (severe/moderate/minor + penalty system)        │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌────────────────────── ADK TOOLS (4) ───────────────────────────────┐  │
│  │                                                                      │  │
│  │  1️⃣ upload_video                                                    │  │
│  │     ├─> Validate file (type, size, extension)                      │  │
│  │     ├─> Generate UUID session ID                                   │  │
│  │     ├─> Save to uploads/ directory                                 │  │
│  │     └─> Create analysis_sessions record in DB                      │  │
│  │                                                                      │  │
│  │  2️⃣ extract_pose_landmarks                                          │  │
│  │     ├─> Load video from session (OpenCV)                           │  │
│  │     ├─> Process @ 3 FPS (every 10th frame)                         │  │
│  │     ├─> MediaPipe: Extract 33 pose landmarks per frame             │  │
│  │     ├─> Calculate joint angles (knee, hip, elbow)                  │  │
│  │     ├─> Aggregate metrics (avg, min, max for each angle)           │  │
│  │     └─> **TOKEN OPTIMIZATION:**                                     │  │
│  │         • Sample max 20 frames from 481 total                      │  │
│  │         • Return only angles (not full 33 landmarks)               │  │
│  │         • Reduces context: ~5K tokens vs 1.2M tokens ✅            │  │
│  │                                                                      │  │
│  │  3️⃣ analyze_workout_form                                            │  │
│  │     ├─> Receive metrics from extract_pose_landmarks               │  │
│  │     ├─> Detect form issues with severity                           │  │
│  │     │   • Insufficient depth (knee angle > 100°)                   │  │
│  │     │   • Knee asymmetry/valgus (difference > 15°)                 │  │
│  │     │   • Excessive forward lean (hip angle < 145°)                │  │
│  │     ├─> Generate coaching cues (actionable, specific)              │  │
│  │     ├─> Calculate overall score (0-10 with penalty system)         │  │
│  │     ├─> Identify strengths (positive reinforcement)                │  │
│  │     └─> Create recommendations (prioritized action items)          │  │
│  │                                                                      │  │
│  │  4️⃣ save_analysis_results                                           │  │
│  │     ├─> Persist complete analysis to PostgreSQL                    │  │
│  │     ├─> Insert into 5 related tables:                              │  │
│  │     │   • analysis_results (score, timing)                         │  │
│  │     │   • form_issues (type, severity, frames, cue)                │  │
│  │     │   • metrics (actual vs target values)                        │  │
│  │     │   • strengths (positive feedback)                            │  │
│  │     │   • recommendations (next steps)                             │  │
│  │     └─> Update session status to 'completed'                       │  │
│  │                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │
                 ┌───────────┴──────────────┐
                 │                          │
                 ▼                          ▼
┌──────────────────────────┐  ┌────────────────────────────┐
│   MEDIAPIPE POSE         │  │   GOOGLE GEMINI 2.0 FLASH  │
│   (Computer Vision)      │  │   (AI Reasoning Engine)     │
│                          │  │                             │
│  • 33-landmark detection │  │  • Form analysis logic      │
│  • Pose tracking         │  │  • Coaching cue generation  │
│  • Angle calculations    │  │  • Severity assessment      │
│  • Frame-by-frame        │  │  • Natural language output  │
│                          │  │                             │
│  Lib: mediapipe==0.10.9  │  │  Via: Google ADK            │
│       opencv-python      │  │  Context: 1M tokens max     │
└──────────────────────────┘  └────────────────────────────┘
                 │
                 │ Saves to
                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        POSTGRESQL DATABASE                                │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  Schema (9 Tables):                                                  │ │
│  │                                                                       │ │
│  │  📊 CORE TABLES:                                                     │ │
│  │  1. users             - User accounts (email, password_hash)        │ │
│  │  2. exercises         - Exercise catalog (Squat, Deadlift, etc.)    │ │
│  │  3. analysis_sessions - Video metadata (status, video_url, timing)  │ │
│  │  4. analysis_results  - Overall score, frame count, processing time │ │
│  │                                                                       │ │
│  │  📋 ANALYSIS DETAILS:                                                │ │
│  │  5. form_issues       - Detected problems (type, severity, cue)     │ │
│  │  6. metrics           - Measurements (actual vs target values)      │ │
│  │  7. strengths         - Positive feedback points                    │ │
│  │  8. recommendations   - Action items for improvement                │ │
│  │                                                                       │ │
│  │  📈 PROGRESS TRACKING:                                               │ │
│  │  9. user_progress     - Trends over time (improvement tracking)     │ │
│  │                                                                       │ │
│  │  Connection: psycopg (v3) with connection pooling                   │ │
│  │  Deployment: Local (dev) / Cloud SQL (production)                   │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow Sequence

```
1. USER uploads video
   ↓
2. FRONTEND validates & sends to /api/analyze
   ↓
3. FASTAPI saves temp file, creates ADK session
   ↓
4. ADK RUNNER sends prompt to Gemini with tools available
   ↓
5. GEMINI orchestrates tool calls:
   
   Step 1: upload_video(video_path, exercise_name)
           └─> Returns: {session_id}
   
   Step 2: extract_pose_landmarks(session_id)
           └─> MediaPipe processes 481 frames @ 3 FPS
           └─> Calculates angles for all frames
           └─> **Samples 20 frames + returns metrics**
           └─> Returns: {metrics, sample_frames, total_frames}
   
   Step 3: analyze_workout_form(pose_data, exercise_name)
           └─> Gemini analyzes metrics vs standards
           └─> Identifies issues with severity
           └─> Generates coaching cues
           └─> Returns: {score, issues, metrics, strengths, recommendations}
   
   Step 4: save_analysis_results(session_id, analysis_data)
           └─> Inserts into 5 DB tables
           └─> Updates session status = 'completed'
           └─> Returns: {result_id, confirmation}
   ↓
6. FASTAPI fetches complete results from DB
   ↓
7. FRONTEND displays results with video player
```

---

## 🎯 Key Architecture Decisions

### **1. ADK Tool Pattern (Not Microservices)**
- ✅ **Chosen:** Single agent with 4 tools
- ❌ **Not:** Separate microservices for vision/analysis
- **Why:** ADK's agent-orchestrated pattern is more efficient, simpler to debug, and fits hackathon timeline

### **2. Token Optimization Strategy**
- **Problem:** 481 frames × 33 landmarks = 1.2M tokens → Exceeds Gemini's 1M limit
- **Solution:** 
  - Extract all frames for accurate analysis
  - Sample 20 representative frames
  - Return only angles (not full landmarks)
  - Result: ~5K tokens (240x reduction)

### **3. Database Choice: PostgreSQL**
- ✅ **Chosen:** PostgreSQL with raw SQL
- ❌ **Not:** ORM (SQLAlchemy), NoSQL (Firestore)
- **Why:** 
  - Relational data (sessions → results → issues)
  - Raw SQL = fast for hackathon
  - Easy to migrate to Cloud SQL

### **4. Frontend-Backend Separation**
- **Development:** Frontend (8001), Backend (8000)
- **Production:** Both on Cloud Run, configurable via `REACT_APP_API_URL`
- **Bonus:** Deploy separately for +0.4 hackathon points

---

## 📦 Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Frontend** | React | 19.2.0 | UI framework |
| | TypeScript | 4.9.5 | Type safety |
| | Tailwind CSS | 3.4.0 | Styling |
| | React Router | 7.9.4 | Navigation |
| **Backend** | FastAPI | 0.104.0+ | API framework |
| | Uvicorn | 0.34.0+ | ASGI server |
| | Python | 3.11 | Runtime (MediaPipe requires 3.11) |
| **AI/ML** | Google ADK | 1.16.0+ | Agent framework |
| | Gemini | 2.0-flash | LLM for reasoning |
| | MediaPipe | 0.10.9 | Pose estimation |
| | OpenCV | 4.8.0+ | Video processing |
| **Database** | PostgreSQL | 15+ | Relational DB |
| | psycopg | 3.1.0+ | Python connector |
| **Deployment** | Docker | - | Containerization |
| | Cloud Run | - | Serverless hosting |

---

## 🔒 Production Readiness Checklist

### ✅ **IMPLEMENTED:**
- [x] Error handling in all tools (try/except with structured returns)
- [x] Database connection pooling (psycopg context managers)
- [x] Input validation (file type, size, extension)
- [x] CORS configuration (development + production modes)
- [x] Health check endpoint (/health)
- [x] Logging (console + file with rotation)
- [x] Token optimization (Gemini context limit)
- [x] Type hints on all functions (ADK requirement)
- [x] Dockerfiles (backend + frontend)
- [x] Environment variable configuration

### ⚠️ **NEEDED FOR PRODUCTION:**
- [ ] Cloud SQL connection (currently local PostgreSQL)
- [ ] Cloud Storage for videos (currently local uploads/)
- [ ] Secret management (Cloud Secret Manager)
- [ ] Rate limiting (prevent abuse)
- [ ] Monitoring & alerting (Cloud Logging + Monitoring)
- [ ] Load testing (concurrent users)
- [ ] User authentication (OAuth / JWT)
- [ ] Video retention policy (auto-cleanup old files)

### 📋 **HACKATHON SUBMISSION:**
- [x] Working demo (full end-to-end flow)
- [x] Architecture diagram (this document)
- [ ] Demo video (<3 minutes)
- [ ] Public GitHub repo
- [ ] Cloud Run deployment
- [ ] README with setup instructions

---

## 🚀 Deployment Architecture (Cloud Run)

```
┌─────────────────────────────────────────────────┐
│           GOOGLE CLOUD PLATFORM                 │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │  Cloud Run Service: biome-frontend        │ │
│  │  • Container: Dockerfile.frontend         │ │
│  │  • Port: 8080                             │ │
│  │  • Memory: 512Mi                          │ │
│  │  • CPU: 1                                 │ │
│  │  • Env: REACT_APP_API_URL=<backend-url>  │ │
│  └───────────────────────────────────────────┘ │
│                      │                          │
│                      │ HTTPS                    │
│                      ▼                          │
│  ┌───────────────────────────────────────────┐ │
│  │  Cloud Run Service: biome-backend         │ │
│  │  • Container: Dockerfile.backend          │ │
│  │  • Port: 8080                             │ │
│  │  • Memory: 4Gi (MediaPipe heavy)          │ │
│  │  • CPU: 2                                 │ │
│  │  • Timeout: 300s (video processing)       │ │
│  │  • Env: DATABASE_URL, GEMINI_API_KEY      │ │
│  └───────────────────────────────────────────┘ │
│                      │                          │
│                      │                          │
│                      ▼                          │
│  ┌───────────────────────────────────────────┐ │
│  │  Cloud SQL (PostgreSQL 15)                │ │
│  │  • Instance: biome-db                     │ │
│  │  • Database: biome_coaching               │ │
│  │  • Connection: Private IP                 │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │  Cloud Storage Bucket                     │ │
│  │  • Name: biome-videos                     │ │
│  │  • Purpose: Video file storage            │ │
│  │  • Lifecycle: Delete after 30 days        │ │
│  └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## 📊 Performance Metrics

| Metric | Target | Actual (Dev) | Notes |
|--------|--------|--------------|-------|
| Video Processing Time | <60s | 30-40s | 481 frames @ 3 FPS |
| Pose Extraction | <30s | 18-22s | MediaPipe processing |
| Gemini Analysis | <10s | 5-8s | With token optimization |
| Database Save | <2s | 0.5-1s | All 5 tables |
| Total Analysis | <60s | 35-45s | Full workflow ✅ |
| Frontend Load | <2s | <1s | React build optimized |
| API Response Time | <100ms | 50-80ms | /health endpoint |

---

## 🏆 Hackathon Compliance

### **Core Requirements:**
- ✅ Uses Google ADK (4 tools + agent orchestration)
- ✅ Solves real problem (injury prevention via form analysis)
- ✅ Original work (created during contest period)
- ✅ Cloud Run deployment ready (Dockerfiles + instructions)

### **Bonus Points Available:**
- ✅ **+0.4** Using Google AI Model (Gemini 2.0 Flash)
- ⏳ **+0.4** Multiple Cloud Run services (deploy frontend separately)
- ⏳ **+0.4** Blog post (document build process)
- ⏳ **+0.4** Social media post (#CloudRunHackathon)

**Maximum Score:** 6.6/6.6 (if all bonuses completed)

---

**Built with ❤️ for Cloud Run Hackathon 2025**
