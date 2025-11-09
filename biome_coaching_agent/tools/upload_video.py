"""
Video upload tool for Biome Coaching Agent.

Validates the file and creates an analysis session record.
For hackathon/local dev, this copies to a local `uploads/` directory.
"""
import os
import shutil
import uuid
from typing import Optional

from google.adk.tools.tool_context import ToolContext

from db.connection import get_db_connection  # type: ignore
from db import queries  # type: ignore
from biome_coaching_agent.logging_config import get_logger  # type: ignore
from biome_coaching_agent.config import (  # type: ignore
    ALLOWED_VIDEO_EXTENSIONS,
    MIN_VIDEO_SIZE_BYTES,
    MAX_VIDEO_SIZE_BYTES,
)
from biome_coaching_agent.exceptions import (  # type: ignore
    ValidationError,
    DatabaseError,
)

# Initialize logger
logger = get_logger(__name__)

# Use centralized constants
ALLOWED_EXTENSIONS = ALLOWED_VIDEO_EXTENSIONS
MAX_BYTES = MAX_VIDEO_SIZE_BYTES


def _ensure_uploads_dir() -> str:
  """Ensure uploads directory exists."""
  uploads_dir = os.path.join(os.getcwd(), "uploads")
  os.makedirs(uploads_dir, exist_ok=True)
  logger.debug(f"Uploads directory ensured: {uploads_dir}")
  return uploads_dir


def upload_video(
  video_file_path: str,
  exercise_name: str,
  user_id: Optional[str] = None,
  tool_context: ToolContext = None,
) -> dict:
  """
  Store the workout video and create an analysis session.

  Args:
    video_file_path: Absolute or relative path to the source video file.
    exercise_name: Name of the exercise (e.g., "Squat").
    user_id: Optional user id (None for demo mode).
    tool_context: ADK tool context (unused).

  Returns:
    dict: {status, session_id, video_url, file_size_mb} or {status, error_type, message} on error
  """
  logger.info(
    f"Video upload initiated - exercise: {exercise_name}, "
    f"user_id: {user_id}, path: {video_file_path}"
  )
  
  try:
    # Validation: File exists
    if not os.path.isfile(video_file_path):
      logger.error(f"Video file not found: {video_file_path}")
      raise ValidationError(f"Video file not found: {video_file_path}")

    # Validation: File extension
    ext = os.path.splitext(video_file_path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
      logger.error(f"Unsupported file type: {ext}")
      raise ValidationError(
        f"Unsupported file type: {ext}. "
        f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
      )

    # Validation: File size
    file_size_bytes = os.path.getsize(video_file_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    logger.debug(f"File size: {file_size_mb:.2f} MB")
    
    # Check for empty files
    if file_size_bytes == 0:
      logger.error("File is empty (0 bytes)")
      raise ValidationError("File is empty")
    
    # Check for suspiciously small files (likely corrupted)
    if file_size_bytes < MIN_VIDEO_SIZE_BYTES:
      logger.error(f"File too small: {file_size_bytes} bytes (min: {MIN_VIDEO_SIZE_BYTES // 1024}KB)")
      raise ValidationError(f"File too small (minimum {MIN_VIDEO_SIZE_BYTES // 1024}KB)")
    
    # Check maximum size
    if file_size_bytes > MAX_BYTES:
      max_mb = MAX_BYTES / (1024 * 1024)
      logger.error(f"File too large: {file_size_mb:.2f} MB (max: {max_mb:.0f} MB)")
      raise ValidationError(
        f"File exceeds {max_mb:.0f}MB limit (size: {file_size_mb:.2f} MB)"
      )

    # Copy file to uploads directory
    uploads_dir = _ensure_uploads_dir()
    session_id = str(uuid.uuid4())
    dest_filename = f"{session_id}{ext}"
    dest_path = os.path.join(uploads_dir, dest_filename)
    
    logger.info(f"Copying video to: {dest_path}")
    try:
      shutil.copy2(video_file_path, dest_path)
      logger.info(f"Video copied successfully - session_id: {session_id}")
    except (IOError, OSError) as copy_err:
      logger.error(f"Failed to copy video file: {copy_err}")
      raise ValidationError(f"Failed to copy video file: {copy_err}")

    # Determine MIME type
    mime_type = {
      ".mp4": "video/mp4",
      ".mov": "video/quicktime",
      ".avi": "video/x-msvideo",
      ".webm": "video/webm",
    }.get(ext, "application/octet-stream")

    # Create database record
    try:
      with get_db_connection() as conn:
        queries.create_analysis_session(
          conn=conn,
          session_id=session_id,
          user_id=user_id,
          exercise_name=exercise_name,
          video_url=dest_path,
          duration=None,
          file_size=file_size_bytes,
        )
        queries.update_session_status(conn, session_id, "processing")
        
      logger.info(
        f"Database record created - session_id: {session_id}, "
        f"exercise: {exercise_name}, size: {file_size_mb:.2f} MB"
      )
    except Exception as db_err:
      logger.error(
        f"Database error during session creation: {db_err}",
        exc_info=True
      )
      # Clean up uploaded file since DB failed
      if os.path.exists(dest_path):
        try:
          os.remove(dest_path)
          logger.debug(f"Cleaned up orphaned file: {dest_path}")
        except Exception as cleanup_err:
          logger.warning(f"Failed to cleanup orphaned file: {cleanup_err}")
      raise DatabaseError(f"Failed to create session record: {db_err}")

    return {
      "status": "success",
      "session_id": session_id,
      "video_url": dest_path,
      "file_size_mb": round(file_size_mb, 2),
    }

  except ValidationError as ve:
    logger.warning(f"Validation error: {ve}")
    # Sanitize error message for client (avoid exposing internal paths)
    error_msg = str(ve)
    if "Video file not found" in error_msg or "path" in error_msg.lower():
      error_msg = "Invalid video file"
    return {"status": "error", "error_type": "validation", "message": error_msg}
  
  except DatabaseError as de:
    logger.error(f"Database error: {de}", exc_info=True)
    return {"status": "error", "error_type": "database", "message": str(de)}
  
  except Exception as e:
    logger.critical(f"Unexpected error during video upload: {e}", exc_info=True)
    return {
      "status": "error",
      "error_type": "unknown",
      "message": f"Unexpected error: {str(e)}"
    }


