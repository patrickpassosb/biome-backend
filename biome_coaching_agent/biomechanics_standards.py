"""
Biomechanics Standards and Thresholds for Exercise Form Analysis.

Defines evidence-based angle thresholds, severity criteria, and penalty scores
for various exercises. Centralizes all "magic numbers" for easy tuning.
"""
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class SquatStandards:
    """Biomechanics standards for squat exercise analysis."""
    
    # Depth Standards (knee flexion angle)
    GOOD_DEPTH_MAX_ANGLE: float = 95.0  # < 95° = good depth (thighs parallel)
    OPTIMAL_DEPTH_ANGLE: float = 90.0   # 90° = ideal parallel squat
    INSUFFICIENT_DEPTH_THRESHOLD: float = 110.0  # > 110° = insufficient depth
    SEVERE_DEPTH_THRESHOLD: float = 120.0  # > 120° = severe issue
    EXCESSIVE_DEPTH_MIN: float = 70.0  # < 70° = potential knee strain
    
    # Knee Alignment Standards (symmetry)
    MAX_KNEE_ASYMMETRY_GOOD: float = 10.0  # < 10° = symmetric movement
    MAX_KNEE_ASYMMETRY_WARNING: float = 15.0  # < 15° = warning
    MAX_KNEE_ASYMMETRY_SEVERE: float = 25.0  # > 25° = severe asymmetry
    
    # Hip Angle Standards (torso position)
    MIN_HIP_ANGLE_TARGET: float = 150.0  # > 150° = upright torso
    HIP_ANGLE_WARNING: float = 145.0  # < 145° = leaning forward
    HIP_ANGLE_SEVERE: float = 135.0  # < 135° = excessive forward lean
    
    # Penalty Scores (deducted from overall score of 10.0)
    DEPTH_PENALTY_MAX: float = 3.0
    ASYMMETRY_PENALTY_MAX: float = 2.0
    FORWARD_LEAN_PENALTY_MAX: float = 2.0
    EXCESSIVE_DEPTH_PENALTY_MAX: float = 1.5
    
    # Confidence Scores (how confident AI is in detection)
    DEPTH_ISSUE_CONFIDENCE: float = 0.85
    ASYMMETRY_ISSUE_CONFIDENCE: float = 0.75
    FORWARD_LEAN_CONFIDENCE: float = 0.70


@dataclass(frozen=True)
class GenericStandards:
    """Universal biomechanics standards for all exercises."""
    
    # Movement Symmetry (applies to all bilateral exercises)
    MAX_KNEE_ASYMMETRY_GOOD: float = 10.0
    MAX_KNEE_ASYMMETRY_WARNING: float = 15.0
    MAX_KNEE_ASYMMETRY_SEVERE: float = 25.0
    
    MAX_HIP_ASYMMETRY_GOOD: float = 8.0
    MAX_HIP_ASYMMETRY_WARNING: float = 10.0
    MAX_HIP_ASYMMETRY_SEVERE: float = 20.0
    
    # Range of Motion Standards
    EXCELLENT_ROM_THRESHOLD: float = 60.0  # > 60° = great ROM
    GOOD_ROM_THRESHOLD: float = 50.0  # > 50° = good ROM
    WARNING_ROM_THRESHOLD: float = 30.0  # < 30° = limited ROM
    POOR_ROM_THRESHOLD: float = 20.0  # < 20° = very limited
    
    # Core Stability (hip variance during upper body movements)
    EXCELLENT_STABILITY_MAX: float = 15.0  # < 15° variance = stable
    GOOD_STABILITY_MAX: float = 20.0  # < 20° = good stability
    WARNING_STABILITY_MAX: float = 25.0  # > 25° = unstable
    SEVERE_STABILITY_MAX: float = 35.0  # > 35° = very unstable
    
    # Penalty Scores
    ASYMMETRY_PENALTY_MAX: float = 2.5
    ROM_PENALTY_MAX: float = 1.5
    STABILITY_PENALTY_MAX: float = 1.5
    
    # Confidence Scores
    ASYMMETRY_CONFIDENCE: float = 0.80
    ROM_CONFIDENCE: float = 0.75
    STABILITY_CONFIDENCE: float = 0.70


@dataclass(frozen=True)
class FrameEstimation:
    """Frame range estimation constants (for identifying issue timeframes)."""
    
    # Squat frame ranges (as % of total video)
    SQUAT_DESCENT_START: float = 0.2  # Issues typically start after initial descent (20%)
    SQUAT_BOTTOM_END: float = 0.8  # Issues end before final ascent (80%)
    
    # Generic frame ranges
    GENERIC_ISSUE_START: float = 0.25
    GENERIC_ISSUE_END: float = 0.75
    
    # Full movement
    FULL_MOVEMENT_START: float = 0.0
    FULL_MOVEMENT_END: float = 1.0


# Singleton instances
SQUAT_STANDARDS = SquatStandards()
GENERIC_STANDARDS = GenericStandards()
FRAME_EST = FrameEstimation()


# ============================================
# SCORING CONSTANTS
# ============================================

PERFECT_SCORE = 10.0
MIN_SCORE = 0.0

# Score interpretation thresholds
EXCELLENT_SCORE_MIN = 8.0  # 8-10 = excellent form
GOOD_SCORE_MIN = 6.0  # 6-7.9 = good form with minor issues
NEEDS_WORK_MAX = 5.9  # < 6 = needs significant improvement


# ============================================
# RECOMMENDATION PRIORITIES
# ============================================

PRIORITY_CRITICAL = 1  # Fix immediately (injury risk)
PRIORITY_IMPORTANT = 2  # Improve soon (effectiveness/imbalance)
PRIORITY_OPTIONAL = 3  # Nice to have (optimization)

