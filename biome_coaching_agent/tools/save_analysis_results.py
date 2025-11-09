"""
Save analysis results tool for Biome Coaching Agent.

Persists complete analysis results to PostgreSQL database including
form issues, metrics, strengths, and recommendations.
"""
import time
from typing import Any, Dict

from google.adk.tools.tool_context import ToolContext

from db.connection import get_db_connection  # type: ignore
from db import queries  # type: ignore
from biome_coaching_agent.logging_config import get_logger  # type: ignore
from biome_coaching_agent.exceptions import (  # type: ignore
    ValidationError,
    DatabaseError,
)

# Initialize logger
logger = get_logger(__name__)


def save_analysis_results(
  session_id: str,
  analysis_data: dict,
  tool_context: ToolContext = None,
) -> dict:
  """
  Save complete analysis results to database.

  Args:
    session_id: Analysis session ID.
    analysis_data: Dictionary containing analysis results:
      {
        "overall_score": float (0-10),
        "total_frames": int,
        "issues": [{issue_type, severity, frame_start, frame_end, coaching_cue, confidence_score}, ...],
        "metrics": [{metric_name, actual_value, target_value, status}, ...],
        "strengths": [str, ...],
        "recommendations": [{recommendation_text, priority}, ...],
      }
    tool_context: ADK tool context (unused).

  Returns:
    dict: {status: "success" | "error", result_id: str, message: str} or {status, error_type, message} on error
  """
  logger.info(f"Saving analysis results for session: {session_id}")
  logger.debug(f"Received analysis_data keys: {list(analysis_data.keys())}")
  
  try:
    # Validate analysis data - check for required fields
    overall_score = analysis_data.get("overall_score")
    total_frames = analysis_data.get("total_frames")
    
    if overall_score is None or total_frames is None:
      error_msg = f"Missing required fields: overall_score={overall_score}, total_frames={total_frames}"
      logger.error(f"Invalid analysis data for session {session_id}: {error_msg}")
      logger.error(f"Full analysis_data received: {analysis_data}")
      raise ValidationError(error_msg)
    
    processing_time = analysis_data.get("processing_time", None)

    issues = analysis_data.get("issues", [])
    metrics_list = analysis_data.get("metrics", [])
    strengths = analysis_data.get("strengths", [])
    recommendations = analysis_data.get("recommendations", [])

    logger.debug(
      f"Analysis summary - session: {session_id}, score: {overall_score}, "
      f"frames: {total_frames}, issues: {len(issues)}, metrics: {len(metrics_list)}, "
      f"strengths: {len(strengths)}, recommendations: {len(recommendations)}"
    )

    # Record processing time if not provided
    if processing_time is None:
      processing_time = 0.0  # Default, could track start/end in future

    try:
      with get_db_connection() as conn:
        # Create analysis result record
        result_id = queries.create_analysis_result(
          conn=conn,
          session_id=session_id,
          overall_score=overall_score,
          total_frames=total_frames,
          processing_time=processing_time,
        )
        logger.debug(f"Created analysis result record: {result_id}")

        # Save form issues
        for idx, issue in enumerate(issues):
          queries.create_form_issue(
            conn=conn,
            result_id=result_id,
            issue_type=issue.get("issue_type", "Unknown Issue"),
            severity=issue.get("severity", "moderate"),
            frame_start=issue.get("frame_start", 0),
            frame_end=issue.get("frame_end", 0),
            coaching_cue=issue.get("coaching_cue", ""),
            confidence_score=issue.get("confidence_score"),
          )
        logger.debug(f"Saved {len(issues)} form issues")

        # Save metrics
        for metric in metrics_list:
          queries.create_metric(
            conn=conn,
            result_id=result_id,
            metric_name=metric.get("metric_name", "Unknown"),
            actual_value=metric.get("actual_value", ""),
            target_value=metric.get("target_value", ""),
            status=metric.get("status", "warning"),
          )
        logger.debug(f"Saved {len(metrics_list)} metrics")

        # Save strengths
        for strength_text in strengths:
          queries.create_strength(
            conn=conn,
            result_id=result_id,
            strength_text=strength_text,
          )
        logger.debug(f"Saved {len(strengths)} strengths")

        # Save recommendations
        for rec in recommendations:
          queries.create_recommendation(
            conn=conn,
            result_id=result_id,
            recommendation_text=rec.get("recommendation_text", ""),
            priority=rec.get("priority", 1),
          )
        logger.debug(f"Saved {len(recommendations)} recommendations")

        # Update session status to completed
        queries.update_session_status(conn, session_id, "completed", None)
        logger.info(f"Session {session_id} marked as completed")

        # Commit transaction (handled by context manager)

    except Exception as db_err:
      logger.error(f"Database error saving results for session {session_id}: {db_err}", exc_info=True)
      raise DatabaseError(f"Failed to save results to database: {db_err}")

    logger.info(
      f"Successfully saved analysis results - session: {session_id}, "
      f"result_id: {result_id}, issues: {len(issues)}, metrics: {len(metrics_list)}"
    )

    return {
      "status": "success",
      "result_id": result_id,
      "message": f"Saved analysis results: {len(issues)} issues, {len(metrics_list)} metrics, {len(strengths)} strengths",
    }
  
  except ValidationError as ve:
    logger.warning(f"Validation error saving results: {ve}")
    # Try to mark session as failed
    try:
      with get_db_connection() as conn:
        queries.update_session_status(conn, session_id, "failed", str(ve))
    except Exception as update_err:
      logger.error(f"Failed to update session status on validation error: {update_err}")
    
    return {
      "status": "error",
      "error_type": "validation",
      "message": str(ve)
    }
  
  except DatabaseError as de:
    logger.error(f"Database error: {de}", exc_info=True)
    # Try to mark session as failed
    try:
      with get_db_connection() as conn:
        queries.update_session_status(conn, session_id, "failed", str(de))
    except Exception as update_err:
      logger.error(f"Failed to update session status on database error: {update_err}")
    
    return {
      "status": "error",
      "error_type": "database",
      "message": str(de)
    }
  
  except Exception as e:
    logger.critical(f"Unexpected error saving results for session {session_id}: {e}", exc_info=True)
    # Try to mark session as failed
    try:
      with get_db_connection() as conn:
        queries.update_session_status(conn, session_id, "failed", str(e))
    except Exception as update_err:
      logger.error(f"Failed to update session status on unexpected error: {update_err}")

    return {
      "status": "error",
      "error_type": "unknown",
      "message": f"Failed to save results: {str(e)}"
    }

