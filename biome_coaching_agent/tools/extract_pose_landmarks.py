"""
Pose extraction tool using MediaPipe.

Processes the stored video at a reduced FPS to extract 33 pose landmarks
and computes simple joint angle metrics for hackathon demo.
"""
from typing import Any, Dict, List, Optional

import cv2  # type: ignore
import numpy as np  # type: ignore

from google.adk.tools.tool_context import ToolContext

from db.connection import get_db_connection  # type: ignore
from db import queries  # type: ignore
from biome_coaching_agent.logging_config import get_logger  # type: ignore
from biome_coaching_agent.exceptions import (  # type: ignore
    ValidationError,
    PoseExtractionError,
    DatabaseError,
    SessionNotFoundError,
)

# Initialize logger
logger = get_logger(__name__)


def _angle_between(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
  """Compute angle at p2 formed by p1-p2-p3 in degrees."""
  v1 = p1 - p2
  v2 = p3 - p2
  denom = (np.linalg.norm(v1) * np.linalg.norm(v2)) + 1e-8
  cosang = float(np.clip(np.dot(v1, v2) / denom, -1.0, 1.0))
  return float(np.degrees(np.arccos(cosang)))


def _calc_joint_angles(landmarks: List[Dict[str, float]]) -> Dict[str, float]:
  """Calculate a few representative angles (knee and hip)."""
  # MediaPipe indices: hip 24/23, knee 26/25, ankle 28/27
  def lp(idx: int) -> np.ndarray:
    lm = landmarks[idx]
    return np.array([lm["x"], lm["y"]], dtype=np.float32)

  left_knee = _angle_between(lp(23), lp(25), lp(27))
  right_knee = _angle_between(lp(24), lp(26), lp(28))
  # Hip angle: shoulder-hip-knee approximation using 12/11, 24/23, 26/25
  left_hip = _angle_between(lp(11), lp(23), lp(25))
  right_hip = _angle_between(lp(12), lp(24), lp(26))
  return {
    "left_knee": left_knee,
    "right_knee": right_knee,
    "left_hip": left_hip,
    "right_hip": right_hip,
  }


def _aggregate_metrics(angle_series: List[Dict[str, float]]) -> Dict[str, Any]:
  keys = angle_series[0].keys() if angle_series else []
  agg: Dict[str, Any] = {"count": len(angle_series)}
  for k in keys:
    vals = np.array([frame[k] for frame in angle_series], dtype=np.float32)
    agg[f"{k}_avg"] = float(np.mean(vals))
    agg[f"{k}_min"] = float(np.min(vals))
    agg[f"{k}_max"] = float(np.max(vals))
  return agg


def extract_pose_landmarks(
  session_id: str,
  fps: int = 3,  # Reduced from 10 to 3 FPS to avoid token limit
  tool_context: ToolContext = None,
) -> dict:
  """
  Extract pose landmarks and joint angles for a given session's video.

  Args:
    session_id: Analysis session id whose video will be processed.
    fps: Target processing fps for speed.
    tool_context: ADK tool context (unused).

  Returns:
    dict: {status, detected_exercise, total_frames, metrics, frames} or {status, error_type, message} on error
  """
  logger.info(f"Starting pose extraction - session_id: {session_id}, fps: {fps}")
  
  try:
    # Get session from database
    try:
      with get_db_connection() as conn:
        row = queries.get_analysis_session(conn, session_id)
    except Exception as db_err:
      logger.error(f"Database error fetching session {session_id}: {db_err}")
      raise DatabaseError(f"Failed to fetch session: {db_err}")
    
    if not row:
      logger.error(f"Session not found: {session_id}")
      raise SessionNotFoundError(f"Session not found: {session_id}")

    # Extract video path from row
    # Row layout depends on cursor factory; safest is to lookup by column order
    video_url = None
    for col in row:
      if isinstance(col, str) and ("/" in col or "\\" in col) and (
        col.endswith(".mp4") or col.endswith(".mov") or 
        col.endswith(".avi") or col.endswith(".webm")
      ):
        video_url = col
        break
    
    if not video_url:
      logger.error(f"No video path in session {session_id}")
      raise ValidationError("Video path not found in session")
    
    logger.debug(f"Processing video: {video_url}")

    # Open video
    cap = cv2.VideoCapture(video_url)
    if not cap.isOpened():
      logger.error(f"Failed to open video file: {video_url}")
      raise PoseExtractionError(f"Failed to open video: {video_url}")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = max(int(round(native_fps / max(fps, 1))), 1)
    logger.info(
      f"Video opened - native_fps: {native_fps}, total_frames: {total_frame_count}, "
      f"processing every {frame_interval} frames"
    )

    # Import MediaPipe (lazy import to avoid protobuf conflicts)
    try:
      import mediapipe as mp  # type: ignore
      logger.debug("MediaPipe imported successfully")
    except Exception as imp_err:
      logger.error(f"Failed to import MediaPipe: {imp_err}")
      cap.release()
      raise PoseExtractionError(f"MediaPipe import failed: {imp_err}")

    mp_pose = mp.solutions.pose
    pose = None
    
    # MEMORY LEAK FIX: Ensure pose and cap are always closed
    try:
      pose = mp_pose.Pose(model_complexity=1)

      frames: List[Dict[str, Any]] = []
      angle_series: List[Dict[str, float]] = []
      idx = 0
      processed_count = 0
      no_detection_count = 0
      
      while True:
        ret, frame = cap.read()
        if not ret:
          break
        
        if idx % frame_interval != 0:
          idx += 1
          continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)
        
        if not res.pose_landmarks:
          no_detection_count += 1
          idx += 1
          continue

        # Process landmarks
        lm_list: List[Dict[str, float]] = []
        for lm in res.pose_landmarks.landmark:
          lm_list.append({"x": float(lm.x), "y": float(lm.y), "z": float(lm.z)})

        angles = _calc_joint_angles(lm_list)
        angle_series.append(angles)
        frames.append({"frame": idx, "landmarks": lm_list, "angles": angles})
        processed_count += 1
        idx += 1

      if not frames:
        logger.warning(
          f"No person detected in video: {video_url} "
          f"(checked {idx} frames, no detections: {no_detection_count})"
        )
        raise PoseExtractionError(
          "No person detected in video. Ensure the video shows a person in good lighting "
          "with full body visible in frame."
        )

      metrics = _aggregate_metrics(angle_series)
      
      logger.info(
        f"Pose extraction complete - session: {session_id}, "
        f"total_frames: {idx}, processed: {processed_count}, "
        f"detected: {len(frames)}, skipped: {no_detection_count}"
      )

      # For ADK: Return ONLY metrics + sample frames to avoid token limit
      # Sample max 20 frames evenly distributed across video
      max_sample_frames = 20
      if len(frames) > max_sample_frames:
        step = len(frames) // max_sample_frames
        sampled_frames = frames[::step][:max_sample_frames]
        logger.info(f"Sampled {len(sampled_frames)} frames from {len(frames)} total for Gemini analysis")
      else:
        sampled_frames = frames
      
      # Remove full landmarks from sampled frames, keep only angles
      lightweight_frames = [
        {"frame": f["frame"], "angles": f["angles"]} 
        for f in sampled_frames
      ]

      return {
        "status": "success",
        "total_frames": len(frames),
        "metrics": metrics,
        "sample_frames": lightweight_frames,  # Only angles from sampled frames
      }
    
    except Exception as pose_err:
      # Handle errors during pose extraction
      logger.error(f"Error during pose processing: {pose_err}")
      raise
    finally:
      # Always cleanup resources
      if pose:
        pose.close()
      cap.release()
      logger.debug("MediaPipe Pose resources cleaned up")

  except SessionNotFoundError as snfe:
    logger.error(f"Session not found: {snfe}")
    return {
      "status": "error",
      "error_type": "session_not_found",
      "message": str(snfe)
    }
  
  except (ValidationError, PoseExtractionError) as known_err:
    logger.error(f"Pose extraction failed for {session_id}: {known_err}")
    return {
      "status": "error",
      "error_type": type(known_err).__name__,
      "message": str(known_err)
    }
  
  except DatabaseError as de:
    logger.error(f"Database error: {de}", exc_info=True)
    return {
      "status": "error",
      "error_type": "database",
      "message": str(de)
    }
  
  except Exception as e:
    logger.critical(
      f"Unexpected error during pose extraction for {session_id}: {e}",
      exc_info=True
    )
    return {
      "status": "error",
      "error_type": "unknown",
      "message": f"Unexpected error: {str(e)}"
    }


