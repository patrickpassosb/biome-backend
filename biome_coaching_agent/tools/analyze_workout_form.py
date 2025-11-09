"""
Form analysis tool for Biome Coaching Agent.

Analyzes pose data and generates coaching feedback with specific cues,
severity scores, and actionable recommendations.

Features:
- Squat-specific analysis with precision biomechanics evaluation
- Generic smart analysis for all other exercises (Shoulder Press, Deadlift, etc.)
- Universal checks: symmetry, range of motion, core stability
- Production-ready error handling and logging
"""
from typing import Any, Dict, List

from google.adk.tools.tool_context import ToolContext
from biome_coaching_agent.logging_config import get_logger  # type: ignore
from biome_coaching_agent.exceptions import AnalysisError, ValidationError  # type: ignore
from biome_coaching_agent.biomechanics_standards import (  # type: ignore
    SQUAT_STANDARDS,
    GENERIC_STANDARDS,
    FRAME_EST,
    PERFECT_SCORE,
    EXCELLENT_SCORE_MIN,
    GOOD_SCORE_MIN,
    PRIORITY_CRITICAL,
    PRIORITY_IMPORTANT,
    PRIORITY_OPTIONAL,
)

# Initialize logger
logger = get_logger(__name__)


def _calculate_squat_score(metrics: Dict[str, Any]) -> float:
  """Calculate overall form score (0-10) for squat exercise using biomechanics standards."""
  score = PERFECT_SCORE
  penalties: List[float] = []

  # Check depth: min_knee_angle < 90° is good depth
  min_knee_angle = min(
    metrics.get("left_knee_min", 180),
    metrics.get("right_knee_min", 180)
  )
  if min_knee_angle > SQUAT_STANDARDS.INSUFFICIENT_DEPTH_THRESHOLD:
    # Insufficient depth
    penalty = min(
      (min_knee_angle - SQUAT_STANDARDS.OPTIMAL_DEPTH_ANGLE) / 20,
      SQUAT_STANDARDS.DEPTH_PENALTY_MAX
    )
    penalties.append(penalty)
  elif min_knee_angle < SQUAT_STANDARDS.EXCESSIVE_DEPTH_MIN:
    # Excessive depth (potential knee strain)
    penalty = (SQUAT_STANDARDS.EXCESSIVE_DEPTH_MIN - min_knee_angle) / 10
    penalties.append(min(penalty, SQUAT_STANDARDS.EXCESSIVE_DEPTH_PENALTY_MAX))

  # Check knee alignment - asymmetry penalty
  avg_left_knee = metrics.get("left_knee_avg", 180)
  avg_right_knee = metrics.get("right_knee_avg", 180)
  asymmetry = abs(avg_left_knee - avg_right_knee)
  if asymmetry > SQUAT_STANDARDS.MAX_KNEE_ASYMMETRY_WARNING:
    penalties.append(
      min(
        asymmetry / SQUAT_STANDARDS.MAX_KNEE_ASYMMETRY_WARNING * 1.5,
        SQUAT_STANDARDS.ASYMMETRY_PENALTY_MAX
      )
    )

  # Check hip hinge - should maintain upright torso
  avg_hip = (metrics.get("left_hip_avg", 180) + metrics.get("right_hip_avg", 180)) / 2
  if avg_hip < SQUAT_STANDARDS.MIN_HIP_ANGLE_TARGET:
    # Excessive forward lean
    penalties.append(
      min(
        (SQUAT_STANDARDS.MIN_HIP_ANGLE_TARGET - avg_hip) / 20,
        SQUAT_STANDARDS.FORWARD_LEAN_PENALTY_MAX
      )
    )

  # Apply penalties
  total_penalty = sum(penalties)
  final_score = max(0.0, score - total_penalty)

  return round(final_score, 1)


def _identify_squat_issues(
  metrics: Dict[str, Any],
  total_frames: int,
) -> List[Dict[str, Any]]:
  """Identify specific form issues with severity and frame ranges."""
  issues: List[Dict[str, Any]] = []

  min_knee_angle = min(
    metrics.get("left_knee_min", 180),
    metrics.get("right_knee_min", 180)
  )

  # Issue 1: Insufficient depth
  if min_knee_angle > SQUAT_STANDARDS.GOOD_DEPTH_MAX_ANGLE:
    severity = "severe" if min_knee_angle > SQUAT_STANDARDS.SEVERE_DEPTH_THRESHOLD else "moderate"
    # Estimate frame range using standardized timing
    frame_start = int(total_frames * FRAME_EST.SQUAT_DESCENT_START)
    frame_end = int(total_frames * FRAME_EST.SQUAT_BOTTOM_END)

    issues.append({
      "issue_type": "Insufficient Squat Depth",
      "severity": severity,
      "frame_start": frame_start,
      "frame_end": frame_end,
      "coaching_cue": (
        f"Lower your hips until your thighs are parallel to the floor "
        f"(target knee angle < {SQUAT_STANDARDS.OPTIMAL_DEPTH_ANGLE:.0f}°). "
        f"Currently reaching {min_knee_angle:.0f}°. "
        "Focus on pushing your hips back and down, not just your knees forward."
      ),
      "confidence_score": SQUAT_STANDARDS.DEPTH_ISSUE_CONFIDENCE,
    })

  # Issue 2: Knee valgus (knees caving inward)
  avg_left_knee = metrics.get("left_knee_avg", 180)
  avg_right_knee = metrics.get("right_knee_avg", 180)
  asymmetry = abs(avg_left_knee - avg_right_knee)
  if asymmetry > 15:
    severity = "severe" if asymmetry > 25 else "moderate"
    # Estimate frame range (hackathon simplification)
    frame_start = int(total_frames * 0.25)
    frame_end = int(total_frames * 0.75)

    issues.append({
      "issue_type": "Knee Asymmetry/Valgus",
      "severity": severity,
      "frame_start": frame_start,
      "frame_end": frame_end,
      "coaching_cue": (
        f"Keep both knees aligned. You have {asymmetry:.0f}° difference between legs. "
        "Push your knees outward to track over your toes. Focus on engaging your glutes."
      ),
      "confidence_score": 0.75,
    })

  # Issue 3: Excessive forward lean (hip angle too closed)
  avg_hip = (metrics.get("left_hip_avg", 180) + metrics.get("right_hip_avg", 180)) / 2
  if avg_hip < 145:
    severity = "severe" if avg_hip < 135 else "moderate"
    frame_start = int(total_frames * 0.1)
    frame_end = int(total_frames * 0.9)

    issues.append({
      "issue_type": "Excessive Forward Lean",
      "severity": severity,
      "frame_start": frame_start,
      "frame_end": frame_end,
      "coaching_cue": (
        f"Maintain a more upright torso. Your hip angle is {avg_hip:.0f}° (target > 150°). "
        "Keep your chest up, core braced, and focus on sitting back into the squat."
      ),
      "confidence_score": 0.70,
    })

  return issues


# ============================================
# GENERIC ANALYSIS (Works for ANY exercise)
# ============================================

def _calculate_generic_score(metrics: Dict[str, Any], exercise_name: str) -> float:
  """
  Calculate overall form score (0-10) for any exercise based on universal biomechanics.
  
  Evaluates:
  - Movement symmetry (left vs right)
  - Range of motion consistency
  - Core stability (minimal compensatory movement)
  - Joint angle health (avoiding extreme positions)
  """
  score = 10.0
  penalties: List[float] = []
  
  # 1. Check bilateral symmetry (applies to all exercises)
  left_knee = metrics.get("left_knee_avg", 180)
  right_knee = metrics.get("right_knee_avg", 180)
  knee_asymmetry = abs(left_knee - right_knee)
  
  if knee_asymmetry > 15:
    # Significant asymmetry = injury risk
    penalty = min((knee_asymmetry - 15) / 10 * 2.0, 2.5)
    penalties.append(penalty)
  
  left_hip = metrics.get("left_hip_avg", 180)
  right_hip = metrics.get("right_hip_avg", 180)
  hip_asymmetry = abs(left_hip - right_hip)
  
  if hip_asymmetry > 10:
    penalty = min((hip_asymmetry - 10) / 10 * 1.5, 2.0)
    penalties.append(penalty)
  
  # 2. Check range of motion (good movement uses full range)
  knee_range = abs(metrics.get("left_knee_max", 180) - metrics.get("left_knee_min", 0))
  
  if knee_range < 20:
    # Very limited ROM = poor movement quality
    penalties.append(1.5)
  elif knee_range < 40:
    # Moderate ROM = room for improvement
    penalties.append(0.5)
  
  # 3. Check core stability (hips shouldn't move excessively in upper body exercises)
  hip_max = max(metrics.get("left_hip_max", 180), metrics.get("right_hip_max", 180))
  hip_min = min(metrics.get("left_hip_min", 0), metrics.get("right_hip_min", 0))
  hip_variance = hip_max - hip_min
  
  # For exercises where hips should be stable (overhead press, etc.)
  if hip_variance > 25:
    penalty = min((hip_variance - 25) / 20, 1.5)
    penalties.append(penalty)
  
  # Apply penalties
  total_penalty = sum(penalties)
  final_score = max(0.0, score - total_penalty)
  
  logger.debug(
    f"Generic score calculation for {exercise_name}: "
    f"base=10.0, penalties={penalties}, final={final_score:.1f}"
  )
  
  return round(final_score, 1)


def _identify_generic_issues(
  metrics: Dict[str, Any],
  exercise_name: str,
  total_frames: int,
) -> List[Dict[str, Any]]:
  """
  Identify common form issues that apply to most exercises.
  
  Detects:
  - Asymmetric movement patterns (injury risk)
  - Limited range of motion (reduced effectiveness)
  - Core instability (compensatory movement)
  """
  issues: List[Dict[str, Any]] = []
  
  # Issue 1: Movement asymmetry (left vs right imbalance)
  left_knee = metrics.get("left_knee_avg", 180)
  right_knee = metrics.get("right_knee_avg", 180)
  knee_asymmetry = abs(left_knee - right_knee)
  
  left_hip = metrics.get("left_hip_avg", 180)
  right_hip = metrics.get("right_hip_avg", 180)
  hip_asymmetry = abs(left_hip - right_hip)
  
  max_asymmetry = max(knee_asymmetry, hip_asymmetry)
  
  if max_asymmetry > 15:
    severity = "severe" if max_asymmetry > 25 else "moderate"
    frame_start = int(total_frames * 0.2)
    frame_end = int(total_frames * 0.8)
    
    issues.append({
      "issue_type": "Asymmetric Movement Pattern",
      "severity": severity,
      "frame_start": frame_start,
      "frame_end": frame_end,
      "coaching_cue": (
        f"Your left and right sides show {max_asymmetry:.0f}° difference in movement. "
        f"This asymmetry can lead to muscle imbalances and injury over time. "
        f"Focus on moving both sides equally. Consider reducing weight to perfect symmetry, "
        f"and strengthen your weaker side with unilateral exercises."
      ),
      "confidence_score": 0.80,
    })
  
  # Issue 2: Limited range of motion
  knee_range = abs(metrics.get("left_knee_max", 180) - metrics.get("left_knee_min", 0))
  
  if knee_range < 40:
    severity = "moderate" if knee_range < 20 else "minor"
    frame_start = 0
    frame_end = total_frames - 1
    
    issues.append({
      "issue_type": "Limited Range of Motion",
      "severity": severity,
      "frame_start": frame_start,
      "frame_end": frame_end,
      "coaching_cue": (
        f"Increase your range of motion for {exercise_name}. Full-range movements "
        f"activate more muscle fibers and improve flexibility. Your current range is "
        f"{knee_range:.0f}°. Focus on controlled movement through the complete range. "
        f"If mobility is limiting you, work on flexibility before adding weight."
      ),
      "confidence_score": 0.75,
    })
  
  # Issue 3: Core instability (excessive hip movement during upper body exercises)
  hip_max = max(metrics.get("left_hip_max", 180), metrics.get("right_hip_max", 180))
  hip_min = min(metrics.get("left_hip_min", 0), metrics.get("right_hip_min", 0))
  hip_variance = hip_max - hip_min
  
  # High variance in hip angle suggests core instability or compensatory movement
  if hip_variance > 25:
    severity = "moderate" if hip_variance > 35 else "minor"
    frame_start = int(total_frames * 0.25)
    frame_end = int(total_frames * 0.75)
    
    issues.append({
      "issue_type": "Core Stability Issue",
      "severity": severity,
      "frame_start": frame_start,
      "frame_end": frame_end,
      "coaching_cue": (
        f"Keep your core braced and hips stable throughout {exercise_name}. "
        f"Your hip angle varies by {hip_variance:.0f}° during the movement. "
        f"Engage your core muscles before each rep, maintain a neutral spine, "
        f"and avoid using momentum or body English to move the weight."
      ),
      "confidence_score": 0.70,
    })
  
  logger.debug(f"Generic analysis identified {len(issues)} issues for {exercise_name}")
  
  return issues


def _generate_generic_metrics(metrics: Dict[str, Any], exercise_name: str) -> List[Dict[str, Any]]:
  """Generate exercise-agnostic metric comparisons."""
  metric_list: List[Dict[str, Any]] = []
  
  # Metric 1: Movement symmetry (universal)
  left_knee = metrics.get("left_knee_avg", 180)
  right_knee = metrics.get("right_knee_avg", 180)
  knee_asymmetry = abs(left_knee - right_knee)
  
  left_hip = metrics.get("left_hip_avg", 180)
  right_hip = metrics.get("right_hip_avg", 180)
  hip_asymmetry = abs(left_hip - right_hip)
  
  max_asymmetry = max(knee_asymmetry, hip_asymmetry)
  
  metric_list.append({
    "metric_name": "Movement Symmetry",
    "actual_value": f"{max_asymmetry:.0f}° difference",
    "target_value": "< 10°",
    "status": "good" if max_asymmetry < 10 else ("warning" if max_asymmetry < 20 else "error"),
  })
  
  # Metric 2: Range of motion (universal)
  knee_range = abs(metrics.get("left_knee_max", 180) - metrics.get("left_knee_min", 0))
  
  metric_list.append({
    "metric_name": "Range of Motion",
    "actual_value": f"{knee_range:.0f}°",
    "target_value": "> 40°",
    "status": "good" if knee_range > 50 else ("warning" if knee_range > 30 else "error"),
  })
  
  # Metric 3: Core stability (universal)
  hip_max = max(metrics.get("left_hip_max", 180), metrics.get("right_hip_max", 180))
  hip_min = min(metrics.get("left_hip_min", 0), metrics.get("right_hip_min", 0))
  hip_variance = hip_max - hip_min
  
  metric_list.append({
    "metric_name": "Core Stability",
    "actual_value": f"{hip_variance:.0f}° variance",
    "target_value": "< 20°",
    "status": "good" if hip_variance < 20 else ("warning" if hip_variance < 30 else "error"),
  })
  
  return metric_list


def _generate_generic_strengths(
  metrics: Dict[str, Any],
  issues: List[Dict[str, Any]],
  exercise_name: str,
) -> List[str]:
  """Generate positive feedback for any exercise based on metrics."""
  strengths: List[str] = []
  
  # Strength 1: Good symmetry
  left_knee = metrics.get("left_knee_avg", 180)
  right_knee = metrics.get("right_knee_avg", 180)
  knee_asymmetry = abs(left_knee - right_knee)
  
  left_hip = metrics.get("left_hip_avg", 180)
  right_hip = metrics.get("right_hip_avg", 180)
  hip_asymmetry = abs(left_hip - right_hip)
  
  if knee_asymmetry < 10 and hip_asymmetry < 8:
    strengths.append(f"Excellent bilateral symmetry! Both sides of your body are moving evenly during {exercise_name}.")
  
  # Strength 2: Good range of motion
  knee_range = abs(metrics.get("left_knee_max", 180) - metrics.get("left_knee_min", 0))
  if knee_range > 60:
    strengths.append(f"Great range of motion! You're using the full movement range for {exercise_name}.")
  
  # Strength 3: Stable core
  hip_variance = abs(metrics.get("left_hip_max", 180) - metrics.get("left_hip_min", 0))
  if hip_variance < 15:
    strengths.append("Solid core stability! Your hips remain stable throughout the movement.")
  
  # Strength 4: No severe issues
  severe_issues = [i for i in issues if i.get("severity") == "severe"]
  if not severe_issues and issues:
    strengths.append("No severe form issues detected. You're on the right track!")
  
  # Strength 5: Perfect form
  if not issues:
    strengths.append(f"Outstanding {exercise_name} form! Keep up the excellent technique.")
  
  # Ensure at least one positive message
  if not strengths:
    strengths.append(f"Good effort on your {exercise_name}! Focus on the cues below to refine your technique.")
  
  return strengths


def _generate_generic_recommendations(
  issues: List[Dict[str, Any]],
  overall_score: float,
  exercise_name: str,
) -> List[Dict[str, Any]]:
  """Generate improvement recommendations for any exercise."""
  recommendations: List[Dict[str, Any]] = []
  
  # Low score = need fundamentals
  if overall_score < 6.0:
    recommendations.append({
      "recommendation_text": (
        f"Focus on mastering the basics of {exercise_name} with reduced weight or bodyweight. "
        f"Use video feedback or a mirror to monitor your form. Consider working with a trainer "
        f"for personalized guidance on this movement pattern."
      ),
      "priority": 1,
    })
  
  # Asymmetry issue = unilateral work needed
  has_asymmetry = any("Asymmetry" in issue.get("issue_type", "") or "Asymmetric" in issue.get("issue_type", "") for issue in issues)
  if has_asymmetry:
    recommendations.append({
      "recommendation_text": (
        f"Address the left-right imbalance with unilateral exercises (single-arm/leg variations). "
        f"This builds balanced strength and reduces injury risk. Include mobility work for "
        f"your weaker side."
      ),
      "priority": 2,
    })
  
  # ROM issue = mobility work needed
  has_rom_issue = any("Range of Motion" in issue.get("issue_type", "") for issue in issues)
  if has_rom_issue:
    recommendations.append({
      "recommendation_text": (
        f"Improve your mobility with dynamic stretching and foam rolling before {exercise_name}. "
        f"Full range of motion is crucial for muscle activation and joint health. "
        f"Practice the movement slowly without weight to build better patterns."
      ),
      "priority": 2,
    })
  
  # Stability issue = core work needed
  has_stability_issue = any("Stability" in issue.get("issue_type", "") for issue in issues)
  if has_stability_issue:
    recommendations.append({
      "recommendation_text": (
        f"Strengthen your core with planks, dead bugs, and anti-rotation exercises. "
        f"A stable core prevents compensatory movements and transfers more power to the target muscles. "
        f"Brace your core before each rep of {exercise_name}."
      ),
      "priority": 2,
    })
  
  # Good score = progressive overload
  if overall_score >= 8.0:
    recommendations.append({
      "recommendation_text": (
        f"Your {exercise_name} form is solid! Consider progressive overload: gradually increase "
        f"weight, reps, or time under tension. You can also try advanced variations to continue "
        f"building strength and skill."
      ),
      "priority": 3,
    })
  
  # Ensure at least one recommendation
  if not recommendations:
    recommendations.append({
      "recommendation_text": (
        f"Keep practicing {exercise_name} with consistent form. Record yourself regularly "
        f"to track improvements and catch issues early."
      ),
      "priority": 3,
    })
  
  return recommendations


def _generate_metrics(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
  """Generate metric comparisons (actual vs target)."""
  metric_list: List[Dict[str, Any]] = []

  # Knee depth metric
  min_knee = min(metrics.get("left_knee_min", 180), metrics.get("right_knee_min", 180))
  metric_list.append({
    "metric_name": "Knee Flexion (Depth)",
    "actual_value": f"{min_knee:.0f}°",
    "target_value": "< 90°",
    "status": "good" if min_knee < 95 else ("warning" if min_knee < 110 else "error"),
  })

  # Knee symmetry metric
  asymmetry = abs(metrics.get("left_knee_avg", 180) - metrics.get("right_knee_avg", 180))
  metric_list.append({
    "metric_name": "Knee Symmetry",
    "actual_value": f"{asymmetry:.0f}° difference",
    "target_value": "< 10°",
    "status": "good" if asymmetry < 10 else ("warning" if asymmetry < 20 else "error"),
  })

  # Hip angle metric
  avg_hip = (metrics.get("left_hip_avg", 180) + metrics.get("right_hip_avg", 180)) / 2
  metric_list.append({
    "metric_name": "Hip Angle (Torso Position)",
    "actual_value": f"{avg_hip:.0f}°",
    "target_value": "> 150°",
    "status": "good" if avg_hip > 155 else ("warning" if avg_hip > 145 else "error"),
  })

  return metric_list


def _generate_strengths(metrics: Dict[str, Any], issues: List[Dict[str, Any]]) -> List[str]:
  """Generate positive feedback for correct form elements."""
  strengths: List[str] = []

  min_knee = min(metrics.get("left_knee_min", 180), metrics.get("right_knee_min", 180))
  if min_knee < 95:
    strengths.append("Excellent squat depth! You're achieving proper range of motion.")

  asymmetry = abs(metrics.get("left_knee_avg", 180) - metrics.get("right_knee_avg", 180))
  if asymmetry < 10:
    strengths.append("Great knee alignment and symmetry throughout the movement.")

  if not issues:
    strengths.append("Outstanding form! Keep up the excellent technique.")

  if not strengths:
    strengths.append("Good effort! Focus on the cues below to improve your form.")

  return strengths


def _generate_recommendations(
  issues: List[Dict[str, Any]],
  overall_score: float,
) -> List[Dict[str, Any]]:
  """Generate improvement recommendations."""
  recommendations: List[Dict[str, Any]] = []

  if overall_score < 6.0:
    recommendations.append({
      "recommendation_text": (
        "Practice bodyweight squats with a focus on proper form before adding weight. "
        "Use a mirror or video feedback to monitor your technique."
      ),
      "priority": 1,
    })

  has_depth_issue = any("Depth" in issue.get("issue_type", "") for issue in issues)
  if has_depth_issue:
    recommendations.append({
      "recommendation_text": (
        "Work on hip mobility and ankle flexibility to improve squat depth. "
        "Consider exercises like goblet squats to practice the movement pattern."
      ),
      "priority": 2,
    })

  has_valgus = any("Valgus" in issue.get("issue_type", "") or "Asymmetry" in issue.get("issue_type", "") for issue in issues)
  if has_valgus:
    recommendations.append({
      "recommendation_text": (
        "Strengthen your glutes and hip abductors with exercises like clamshells, "
        "lateral band walks, and hip thrusts to prevent knee caving."
      ),
      "priority": 2,
    })

  if overall_score >= 8.0:
    recommendations.append({
      "recommendation_text": "Your form is solid! Consider gradually increasing load or adding variations like pause squats.",
      "priority": 3,
    })

  return recommendations


def analyze_workout_form(
  pose_data: dict,
  exercise_name: str,
  tool_context: ToolContext = None,
) -> dict:
  """
  Analyze workout form from pose data and generate coaching feedback.

  Args:
    pose_data: Dictionary containing pose extraction results:
      {
        "status": "success",
        "total_frames": int,
        "metrics": {left_knee_avg, left_knee_min, ...},
        "frames": [{frame, landmarks, angles}, ...]
      }
    exercise_name: Name of exercise (e.g., "Squat")
    tool_context: ADK tool context (unused).

  Returns:
    dict: {
      status: "success" | "error",
      overall_score: float (0-10),
      total_frames: int,
      issues: [{issue_type, severity, frame_start, frame_end, coaching_cue, confidence_score}, ...],
      metrics: [{metric_name, actual_value, target_value, status}, ...],
      strengths: [str, ...],
      recommendations: [{recommendation_text, priority}, ...],
    } or {status, error_type, message} on error
  """
  logger.info(f"Starting form analysis - exercise: {exercise_name}")
  
  try:
    # Validate pose data status
    if pose_data.get("status") != "success":
      error_msg = pose_data.get("message", "Pose data extraction failed")
      logger.error(f"Pose data invalid: {error_msg}")
      raise ValidationError(f"Invalid pose data: {error_msg}")

    metrics = pose_data.get("metrics", {})
    total_frames = pose_data.get("total_frames", 0)

    if not metrics:
      logger.error("No metrics available for analysis")
      raise ValidationError("No metrics available for analysis")
    
    logger.debug(f"Analyzing {total_frames} frames with metrics: {list(metrics.keys())}")

    # Check exercise type and analyze accordingly
    exercise_lower = exercise_name.lower()
    
    if exercise_lower in ["squat", "squats"]:
      # Squat-specific analysis (high precision for this exercise)
      logger.info(f"Using squat-specific analysis for {exercise_name}")
      overall_score = _calculate_squat_score(metrics)
      logger.debug(f"Squat score calculated: {overall_score}/10")

      issues = _identify_squat_issues(metrics, total_frames)
      logger.debug(f"Squat-specific issues identified: {len(issues)}")
      
      # Use squat-specific metrics
      metrics_list = _generate_metrics(metrics)
      strengths = _generate_strengths(metrics, issues)
      recommendations = _generate_recommendations(issues, overall_score)
      
    else:
      # Generic analysis for all other exercises (Shoulder Press, Deadlift, Push-up, etc.)
      logger.info(f"Using generic smart analysis for {exercise_name}")
      overall_score = _calculate_generic_score(metrics, exercise_name)
      logger.debug(f"Generic score calculated: {overall_score}/10")

      issues = _identify_generic_issues(metrics, exercise_name, total_frames)
      logger.debug(f"Generic issues identified: {len(issues)}")
      
      # Use generic metrics and feedback
      metrics_list = _generate_generic_metrics(metrics, exercise_name)
      strengths = _generate_generic_strengths(metrics, issues, exercise_name)
      recommendations = _generate_generic_recommendations(issues, overall_score, exercise_name)
    
    logger.debug(
      f"Analysis complete - score: {overall_score}/10, issues: {len(issues)}, "
      f"metrics: {len(metrics_list)}, strengths: {len(strengths)}, recommendations: {len(recommendations)}"
    )

    logger.info(
      f"Form analysis complete - exercise: {exercise_name}, "
      f"score: {overall_score}/10, issues: {len(issues)}, "
      f"strengths: {len(strengths)}"
    )

    return {
      "status": "success",
      "overall_score": overall_score,
      "total_frames": total_frames,
      "issues": issues,
      "metrics": metrics_list,
      "strengths": strengths,
      "recommendations": recommendations,
    }
  
  except ValidationError as ve:
    logger.warning(f"Validation error during analysis: {ve}")
    return {
      "status": "error",
      "error_type": "validation",
      "message": str(ve)
    }
  
  except Exception as e:
    logger.critical(f"Unexpected error during form analysis: {e}", exc_info=True)
    return {
      "status": "error",
      "error_type": "unknown",
      "message": f"Analysis failed: {str(e)}"
    }

