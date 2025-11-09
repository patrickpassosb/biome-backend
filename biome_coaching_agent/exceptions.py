"""
Custom exceptions for Biome Coaching Agent.

Provides specific exception types for better error handling and logging.
"""


class BiomeError(Exception):
    """Base exception for all Biome application errors."""
    pass


class VideoProcessingError(BiomeError):
    """Error during video processing or manipulation."""
    pass


class DatabaseError(BiomeError):
    """Database operation failed."""
    pass


class ValidationError(BiomeError):
    """Input validation failed."""
    pass


class PoseExtractionError(BiomeError):
    """Pose landmark extraction failed."""
    pass


class AnalysisError(BiomeError):
    """Form analysis failed."""
    pass


class SessionNotFoundError(BiomeError):
    """Requested analysis session does not exist."""
    pass


class ConfigurationError(BiomeError):
    """Application configuration error."""
    pass

