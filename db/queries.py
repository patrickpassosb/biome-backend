"""
Raw SQL query helpers for Biome Coaching Agent.

Phase 1-3: Session management and analysis result persistence.
"""
from typing import Any, Dict, Optional
from decimal import Decimal

import psycopg

# Import logger - avoid circular import by importing locally if needed
try:
  from biome_coaching_agent.logging_config import get_logger
  logger = get_logger(__name__)
except ImportError:
  # Fallback to basic logging if biome_coaching_agent not available
  import logging
  logger = logging.getLogger(__name__)


def ping(conn: psycopg.Connection) -> bool:
  """Simple connectivity check."""
  cur = conn.cursor()
  cur.execute("SELECT 1;")
  row = cur.fetchone()
  return bool(row and row[0] == 1)


# Phase 2: Session management
def create_analysis_session(
  conn: psycopg.Connection,
  session_id: str,
  user_id: Optional[str],
  exercise_name: str,
  video_url: str,
  duration: Optional[float],
  file_size: Optional[int],
) -> str:
  """Create a new analysis session record."""
  logger.debug(
    f"Creating analysis session - id: {session_id}, exercise: {exercise_name}, "
    f"user_id: {user_id}, file_size: {file_size}"
  )
  
  try:
    # Convert user_id to None if it's not a valid UUID (for demo mode)
    parsed_user_id = None
    if user_id:
      try:
        import uuid
        uuid.UUID(user_id)  # Validate it's a UUID
        parsed_user_id = user_id
      except (ValueError, AttributeError):
        # Not a valid UUID, use None for demo users
        parsed_user_id = None
    
    cur = conn.cursor()
    cur.execute(
      (
        "INSERT INTO analysis_sessions "
        "(id, user_id, exercise_name, video_url, video_duration, file_size, status, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'pending', NOW()) RETURNING id"
      ),
      (session_id, parsed_user_id, exercise_name, video_url, duration, file_size),
    )
    row = cur.fetchone()
    created_id = row[0]
    logger.info(f"Analysis session created successfully: {created_id}")
    return created_id
  except psycopg.Error as e:
    logger.error(f"Failed to create analysis session {session_id}: {e}", exc_info=True)
    raise


def get_analysis_session(
  conn: psycopg.Connection,
  session_id: str,
) -> Any:
  """Get analysis session by ID with explicit column selection."""
  cur = conn.cursor()
  cur.execute(
    "SELECT id, user_id, exercise_id, exercise_name, video_url, video_duration, "
    "status, created_at, started_at, completed_at, error_message "
    "FROM analysis_sessions WHERE id = %s",
    (session_id,)
  )
  return cur.fetchone()


def update_session_status(
  conn: psycopg.Connection,
  session_id: str,
  status: str,
  error_message: Optional[str] = None,
) -> None:
  """Update analysis session status."""
  logger.debug(f"Updating session {session_id} status to: {status}")
  
  try:
    cur = conn.cursor()
    if status == "completed":
      cur.execute(
        (
          "UPDATE analysis_sessions "
          "SET status = %s, error_message = %s, completed_at = NOW() WHERE id = %s"
        ),
        (status, error_message, session_id),
      )
      logger.info(f"Session {session_id} marked as completed")
    elif status == "processing":
      cur.execute(
        (
          "UPDATE analysis_sessions "
          "SET status = %s, error_message = %s, started_at = COALESCE(started_at, NOW()) WHERE id = %s"
        ),
        (status, error_message, session_id),
      )
      logger.info(f"Session {session_id} marked as processing")
    else:
      cur.execute(
        "UPDATE analysis_sessions SET status = %s, error_message = %s WHERE id = %s",
        (status, error_message, session_id),
      )
      if error_message:
        logger.warning(f"Session {session_id} status updated to {status} with error: {error_message}")
      else:
        logger.info(f"Session {session_id} status updated to: {status}")
  except psycopg.Error as e:
    logger.error(f"Failed to update session {session_id} status: {e}", exc_info=True)
    raise


# Phase 3: Analysis result persistence
def create_analysis_result(
  conn: psycopg.Connection,
  session_id: str,
  overall_score: float,
  total_frames: int,
  processing_time: Optional[float] = None,
) -> str:
  """Create analysis result record and return result ID."""
  cur = conn.cursor()
  cur.execute(
    (
      "INSERT INTO analysis_results "
      "(session_id, overall_score, total_frames, processing_time, created_at) "
      "VALUES (%s, %s, %s, %s, NOW()) RETURNING id"
    ),
    (session_id, Decimal(str(overall_score)), total_frames, Decimal(str(processing_time)) if processing_time else None),
  )
  row = cur.fetchone()
  return str(row[0])


def create_form_issue(
  conn: psycopg.Connection,
  result_id: str,
  issue_type: str,
  severity: str,
  frame_start: int,
  frame_end: int,
  coaching_cue: str,
  confidence_score: Optional[float] = None,
) -> None:
  """Create a form issue record."""
  cur = conn.cursor()
  cur.execute(
    (
      "INSERT INTO form_issues "
      "(result_id, issue_type, severity, frame_start, frame_end, coaching_cue, confidence_score, created_at) "
      "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())"
    ),
    (
      result_id,
      issue_type,
      severity,
      frame_start,
      frame_end,
      coaching_cue,
      Decimal(str(confidence_score)) if confidence_score is not None else None,
    ),
  )


def create_metric(
  conn: psycopg.Connection,
  result_id: str,
  metric_name: str,
  actual_value: str,
  target_value: str,
  status: str,
) -> None:
  """Create a metric record."""
  cur = conn.cursor()
  cur.execute(
    (
      "INSERT INTO metrics "
      "(result_id, metric_name, actual_value, target_value, status, created_at) "
      "VALUES (%s, %s, %s, %s, %s, NOW())"
    ),
    (result_id, metric_name, actual_value, target_value, status),
  )


def create_strength(
  conn: psycopg.Connection,
  result_id: str,
  strength_text: str,
) -> None:
  """Create a strength record."""
  cur = conn.cursor()
  cur.execute(
    (
      "INSERT INTO strengths "
      "(result_id, strength_text, created_at) "
      "VALUES (%s, %s, NOW())"
    ),
    (result_id, strength_text),
  )


def create_recommendation(
  conn: psycopg.Connection,
  result_id: str,
  recommendation_text: str,
  priority: int = 1,
) -> None:
  """Create a recommendation record."""
  cur = conn.cursor()
  cur.execute(
    (
      "INSERT INTO recommendations "
      "(result_id, recommendation_text, priority, created_at) "
      "VALUES (%s, %s, %s, NOW())"
    ),
    (result_id, recommendation_text, priority),
  )


def get_analysis_result_by_session(
  conn: psycopg.Connection,
  session_id: str,
) -> Optional[Dict[str, Any]]:
  """
  Get complete analysis result with all related data for a session.
  
  Returns nested dict with result, issues, metrics, strengths, recommendations.
  """
  cur = conn.cursor()
  
  # Get analysis result
  cur.execute(
    "SELECT id, session_id, overall_score, total_frames, processing_time, created_at "
    "FROM analysis_results WHERE session_id = %s ORDER BY created_at DESC LIMIT 1",
    (session_id,),
  )
  result_row = cur.fetchone()
  if not result_row:
    return None
  
  result_id = str(result_row[0])
  
  # Get form issues
  cur.execute(
    (
      "SELECT id, issue_type, severity, frame_start, frame_end, coaching_cue, confidence_score "
      "FROM form_issues WHERE result_id = %s ORDER BY severity DESC, frame_start"
    ),
    (result_id,),
  )
  issues = [
    {
      "id": str(row[0]),
      "issue_type": row[1],
      "severity": row[2],
      "frame_start": row[3],
      "frame_end": row[4],
      "coaching_cue": row[5],
      "confidence_score": float(row[6]) if row[6] else None,
    }
    for row in cur.fetchall()
  ]
  
  # Get metrics
  cur.execute(
    "SELECT id, metric_name, actual_value, target_value, status "
    "FROM metrics WHERE result_id = %s ORDER BY metric_name",
    (result_id,),
  )
  metrics = [
    {
      "id": str(row[0]),
      "metric_name": row[1],
      "actual_value": row[2],
      "target_value": row[3],
      "status": row[4],
    }
    for row in cur.fetchall()
  ]
  
  # Get strengths
  cur.execute(
    "SELECT id, strength_text FROM strengths WHERE result_id = %s ORDER BY created_at",
    (result_id,),
  )
  strengths = [{"id": str(row[0]), "strength_text": row[1]} for row in cur.fetchall()]
  
  # Get recommendations
  cur.execute(
    "SELECT id, recommendation_text, priority FROM recommendations WHERE result_id = %s ORDER BY priority, created_at",
    (result_id,),
  )
  recommendations = [
    {
      "id": str(row[0]),
      "recommendation_text": row[1],
      "priority": row[2],
    }
    for row in cur.fetchall()
  ]
  
  return {
    "result": {
      "id": result_id,
      "session_id": session_id,
      "overall_score": float(result_row[2]),
      "total_frames": result_row[3],
      "processing_time": float(result_row[4]) if result_row[4] else None,
      "created_at": result_row[5].isoformat() if result_row[5] else None,
    },
    "issues": issues,
    "metrics": metrics,
    "strengths": strengths,
    "recommendations": recommendations,
  }


