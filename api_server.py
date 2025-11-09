"""
Custom API server for Biome Coaching Agent with video upload support.
Uses ADK Runner to orchestrate agent workflow with Gemini AI reasoning.
"""
import os
import uuid
import shutil
import time
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, Field, validator
from enum import Enum

# Import ADK components
from google.adk.runners import InMemoryRunner
from google.genai import types

# Import agent and tools
from biome_coaching_agent.agent import root_agent
from biome_coaching_agent.config import (
    settings,
    ALLOWED_VIDEO_EXTENSIONS,
    MIN_VIDEO_SIZE_BYTES,
    MAX_VIDEO_SIZE_BYTES,
    DEMO_USER_ID,
)
from biome_coaching_agent.logging_config import get_logger
from biome_coaching_agent.exceptions import (
    ValidationError,
    DatabaseError,
    PoseExtractionError,
    AnalysisError,
)
from db.connection import get_db_connection
from db import queries

# Initialize logger
logger = get_logger(__name__)


# ============================================
# REQUEST VALIDATION MODELS
# ============================================

class ExerciseType(str, Enum):
    """Allowed exercise types for analysis"""
    SQUAT = "Squat"
    PUSHUP = "Push-up"
    DEADLIFT = "Deadlift"
    PLANK = "Plank"
    LUNGE = "Lunge"
    PULLUP = "Pull-up"
    BENCH_PRESS = "Bench Press"
    SHOULDER_PRESS = "Shoulder Press"
    ROW = "Row"
    OVERHEAD_PRESS = "Overhead Press"
    HIP_THRUST = "Hip Thrust"


# ============================================
# STARTUP CONFIGURATION
# ============================================

# Validate configuration on startup
try:
    settings.validate()
    logger.info("Configuration validated successfully")
except ValueError as e:
    logger.critical(f"Configuration validation failed: {e}")
    raise

app = FastAPI(
    title="Biome Coaching API",
    description="AI-powered fitness form coaching API",
    version="1.0.0"
)

# Initialize rate limiter to prevent abuse
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Enable CORS for React frontend
# Production: Use environment variable CORS_ORIGINS
# Development: Allow common local dev ports
if settings.is_production:
    cors_origins = [origin.strip() for origin in settings.cors_origins.split(",")]
else:
    # Development mode - allow common local ports
    cors_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
        "http://localhost:8001",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8001",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
)

# Ensure uploads directory exists
UPLOADS_DIR = Path(settings.uploads_dir)
UPLOADS_DIR.mkdir(exist_ok=True)
logger.info(f"Uploads directory: {UPLOADS_DIR.absolute()}")

# Initialize ADK Runner for agent orchestration
runner = InMemoryRunner(
    app_name="biome_coaching_agent",
    agent=root_agent,
)
logger.info(f"ADK Runner initialized - Agent: {root_agent.name}, Model: {root_agent.model}, Tools: {len(root_agent.tools)}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "biome-coaching-api",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "analyze": "/api/analyze",
            "results": "/api/results/{session_id}"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with dependency verification"""
    checks = {}
    overall_healthy = True
    
    # Check database
    try:
        with get_db_connection() as conn:
            queries.ping(conn)
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        overall_healthy = False
        logger.error(f"Health check - database failed: {e}")
    
    # Check MediaPipe availability
    try:
        import mediapipe
        checks["mediapipe"] = "available"
    except ImportError as e:
        checks["mediapipe"] = f"missing: {str(e)}"
        overall_healthy = False
        logger.error(f"Health check - MediaPipe missing: {e}")
    
    # Check uploads directory writable
    try:
        test_file = UPLOADS_DIR / ".health_check"
        test_file.touch()
        test_file.unlink()
        checks["storage"] = "writable"
    except Exception as e:
        checks["storage"] = f"error: {str(e)}"
        overall_healthy = False
        logger.error(f"Health check - storage failed: {e}")
    
    # Check Gemini API key configured
    checks["gemini_key"] = "configured" if settings.google_api_key else "missing"
    if not settings.google_api_key:
        overall_healthy = False
    
    status_code = 200 if overall_healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if overall_healthy else "unhealthy",
            "service": "biome-coaching-api",
            "checks": checks
        }
    )


@app.post("/api/analyze")
@limiter.limit("5/minute")  # Max 5 uploads per minute per IP
@limiter.limit("20/hour")   # Max 20 uploads per hour per IP
async def analyze_video_endpoint(
    request: Request,  # Required by slowapi for rate limiting
    video: UploadFile = File(...),
    exercise_name: str = Form(...),
    user_id: Optional[str] = Form(None),
):
    """
    Upload and analyze a workout video.
    
    This endpoint orchestrates the full analysis workflow:
    1. Saves the uploaded video
    2. Runs pose extraction using MediaPipe
    3. Analyzes form using Gemini AI
    4. Saves results to database
    5. Returns complete analysis
    
    Args:
        video: Uploaded video file
        exercise_name: Name of exercise being performed
        user_id: Optional user identifier
    
    Returns:
        Complete analysis results with issues, metrics, strengths, and recommendations
    """
    start_time = time.time()
    temp_path = None
    
    try:
        logger.info(
            f"Analysis request received - exercise: {exercise_name}, "
            f"user_id: {user_id}, filename: {video.filename}"
        )
        
        # Validation: Exercise name
        valid_exercises = [e.value for e in ExerciseType]
        if exercise_name not in valid_exercises:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": f"Invalid exercise: '{exercise_name}'. Must be one of: {', '.join(valid_exercises)}",
                    "step": "validation"
                }
            )
        
        # Validation: User ID format
        if user_id and user_id != "demo_user":
            try:
                uuid.UUID(user_id)
            except ValueError:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "user_id must be a valid UUID or 'demo_user'", "step": "validation"}
                )
        
        # Validation: File type
        if not video.content_type or not video.content_type.startswith('video/'):
            raise HTTPException(
                status_code=400,
                detail={"error": "File must be a video (mp4, mov, avi, webm)", "step": "validation"}
            )
        
        # Validation: Read file size
        video.file.seek(0, 2)  # Seek to end
        file_size_bytes = video.file.tell()
        video.file.seek(0)  # Reset to beginning
        
        # Validation: Empty file
        if file_size_bytes == 0:
            raise HTTPException(
                status_code=400,
                detail={"error": "File is empty", "step": "validation"}
            )
        
        # Validation: File too small (likely corrupted)
        if file_size_bytes < MIN_VIDEO_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={"error": f"File too small (minimum {MIN_VIDEO_SIZE_BYTES // 1024}KB)", "step": "validation"}
            )
        
        # Validation: File too large
        if file_size_bytes > MAX_VIDEO_SIZE_BYTES:
            size_mb = file_size_bytes / (1024 * 1024)
            max_mb = MAX_VIDEO_SIZE_BYTES / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail={"error": f"File too large: {size_mb:.1f}MB (max {max_mb:.0f}MB)", "step": "validation"}
            )
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Save uploaded file temporarily
        # SECURITY: Use only session_id, ignore user-provided filename to prevent path traversal
        # SECURITY: Validate extension against whitelist
        raw_ext = Path(video.filename).suffix.lower() if video.filename else ".mp4"
        safe_ext = raw_ext if raw_ext in ALLOWED_VIDEO_EXTENSIONS else ".mp4"
        temp_path = UPLOADS_DIR / f"temp_{session_id}{safe_ext}"
        logger.debug(f"Saving uploaded file to temporary location: {temp_path}")
        
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        
        file_size = temp_path.stat().st_size
        logger.info(f"File saved: {file_size} bytes")
        
        try:
            # Create ADK session for agent orchestration
            adk_session = await runner.session_service.create_session(
                app_name="biome_coaching_agent",
                user_id=user_id or "demo_user"
            )
            logger.info(f"ADK session created: {adk_session.id}")
            
            # Build prompt for ADK agent to orchestrate workflow
            prompt = (
                f"Process this {exercise_name} workout video for form analysis. "
                f"The video file is located at: {str(temp_path)}. "
                f"Follow your complete workflow: "
                f"1) Use upload_video tool with video_file_path='{str(temp_path)}', exercise_name='{exercise_name}', user_id='{user_id or 'demo_user'}'. "
                f"2) Use extract_pose_landmarks tool with the session_id returned from upload. "
                f"3) Use analyze_workout_form tool with the pose data and exercise name. "
                f"4) Use save_analysis_results tool to save everything to the database. "
                f"After completing all steps, confirm the session_id so I can retrieve the results."
            )
            
            # Let ADK agent orchestrate the entire workflow using Gemini reasoning
            user_message = types.Content(
                role='user',
                parts=[types.Part.from_text(text=prompt)]
            )
            
            logger.info(f"🤖 Sending workflow to ADK agent (Gemini will orchestrate)...")
            
            # Run agent with timeout to prevent hung requests
            # Track session_id from tool results to avoid race condition
            tracked_session_id = None
            
            try:
                async with asyncio.timeout(180):  # 3 minute maximum timeout
                    agent_response_text = ""
                    async for event in runner.run_async(
                        user_id=user_id or "demo_user",
                        session_id=adk_session.id,
                        new_message=user_message,
                    ):
                        # Extract session_id from upload_video tool result
                        if hasattr(event, 'tool_name') and event.tool_name == "upload_video":
                            if hasattr(event, 'tool_result') and event.tool_result:
                                result = event.tool_result
                                if isinstance(result, dict) and result.get("status") == "success":
                                    tracked_session_id = result.get("session_id")
                                    logger.info(f"Tracked session_id from upload_video tool: {tracked_session_id}")
                        
                        # Log agent activity
                        if event.content and event.content.parts:
                            for part in event.content.parts:
                                if part.text:
                                    if event.author == "model":
                                        agent_response_text += part.text
                                        logger.debug(f"Agent response: {part.text[:100]}...")
                
                logger.info(f"ADK agent completed workflow orchestration")
            
            except asyncio.TimeoutError:
                logger.error(f"Analysis timeout after 180 seconds for exercise: {exercise_name}")
                raise HTTPException(
                    status_code=504,
                    detail={
                        "error": "Analysis timeout - video too long or complex. Try a shorter video (max 2 minutes)",
                        "step": "processing"
                    }
                )
            
        finally:
            # Always cleanup temp file
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug("Temporary file cleaned up")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to cleanup temp file: {cleanup_err}")
        
        # Use tracked session_id from tool result (prevents race condition)
        # Fallback to database query only if tracking failed
        if tracked_session_id:
            session_id = tracked_session_id
            logger.info(f"Using tracked session_id from upload_video tool: {session_id}")
        else:
            # Fallback: Query database (WARNING: potential race condition in multi-user scenarios)
            logger.warning("Session ID not tracked from tool result, falling back to database query")
            db_user_id = None if user_id == "demo_user" else user_id
            
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT id FROM analysis_sessions 
                    WHERE exercise_name = %s 
                    AND (user_id = %s OR user_id IS NULL)
                    AND created_at > NOW() - INTERVAL '5 minutes'
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (exercise_name, db_user_id)
                )
                session_row = cur.fetchone()
                if not session_row:
                    raise HTTPException(
                        status_code=500,
                        detail={"error": "Agent completed but session not found"}
                    )
                session_id = str(session_row[0])
            
            logger.info(f"Retrieved session_id from database (fallback): {session_id}")
        
        processing_time = time.time() - start_time
        logger.info(
            f"Analysis complete for session {session_id} in {processing_time:.2f}s via ADK agent orchestration"
        )
        
        # Retrieve results from database (saved by agent's save_analysis_results tool)
        with get_db_connection() as conn:
            result_data = queries.get_analysis_result_by_session(conn, session_id)
        
        if not result_data:
            raise HTTPException(
                status_code=500,
                detail={"error": "Agent completed workflow but results not found in database"}
            )
        
        # Extract data from database result
        result_info = result_data["result"]
        issues = result_data["issues"]
        metrics = result_data["metrics"]
        strengths = result_data["strengths"]
        recommendations = result_data["recommendations"]
        
        # Return complete analysis in format expected by frontend
        return JSONResponse({
            "status": "success",
            "session_id": session_id,
            "result_id": result_info["id"],
            "overall_score": float(result_info["overall_score"]),
            "total_frames": result_info["total_frames"],
            "processing_time": round(processing_time, 2),
            "issues": issues,
            "metrics": metrics,
            "strengths": [s["strength_text"] for s in strengths],
            "recommendations": [{"recommendation_text": r["recommendation_text"], "priority": r["priority"]} for r in recommendations],
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.critical(f"Unexpected error in analyze endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Internal server error: {str(e)}",
                "step": "unknown"
            }
        )


@app.get("/api/results/{session_id}")
async def get_results(session_id: str):
    """
    Get analysis results for a session.
    
    Args:
        session_id: The analysis session ID (UUID format)
    
    Returns:
        Complete analysis results if available
    """
    try:
        # Validate UUID format
        try:
            uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid session_id format (must be UUID)"
            )
        
        logger.info(f"Fetching results for session {session_id}")
        
        with get_db_connection() as conn:
            result = queries.get_analysis_result_by_session(conn, session_id)
        
        if not result:
            logger.warning(f"No results found for session {session_id}")
            raise HTTPException(
                status_code=404,
                detail="Results not found for this session"
            )
        
        logger.info(f"Results retrieved successfully for session {session_id}")
        return JSONResponse(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching results for session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve results: {str(e)}"
        )


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Get session information including status.
    
    Args:
        session_id: The analysis session ID (UUID format)
    
    Returns:
        Session details including status
    """
    try:
        # Validate UUID format
        try:
            uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid session_id format (must be UUID)"
            )
        
        logger.debug(f"Fetching session info for {session_id}")
        
        with get_db_connection() as conn:
            session_row = queries.get_analysis_session(conn, session_id)
        
        if not session_row:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Parse the row with explicit indices (matches SELECT order in queries.py)
        # Order: id, user_id, exercise_id, exercise_name, video_url, video_duration, status, created_at, started_at, completed_at, error_message
        return JSONResponse({
            "session_id": str(session_row[0]),  # id
            "user_id": str(session_row[1]) if session_row[1] else None,  # user_id
            "exercise_name": session_row[3],  # exercise_name
            "video_url": session_row[4],  # video_url
            "status": session_row[6],  # status
            "created_at": session_row[7].isoformat() if session_row[7] else None,  # created_at
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Configure server using centralized settings
    logger.info(f"Starting Biome Coaching API server on {settings.host}:{settings.port}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # SECURITY: Log database host without credentials
    if '@' in settings.database_url:
        # Extract host:port/database from connection string (no credentials)
        db_info = settings.database_url.split('@')[-1]
    else:
        db_info = 'configured'
    logger.info(f"Database: {db_info}")
    
    uvicorn.run(
        "api_server:app",
        host=settings.host,
        port=settings.port,
        reload=False,  # Disabled to prevent interruptions during analysis
        log_level=settings.log_level
    )

