"""
Configuration loader for Biome Coaching Agent.
Loads environment variables and exposes typed accessors.

Centralized configuration for backend, database, and deployment.
"""
import os
from dataclasses import dataclass
from typing import Optional

try:
  # Optional: load from .env if present during local dev
  from dotenv import load_dotenv  # type: ignore
  load_dotenv()
except Exception:
  # dotenv is optional; ignore if not installed yet
  pass


@dataclass(frozen=True)
class Settings:
  """Application settings loaded from environment variables."""
  
  # Database Configuration
  database_url: str = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/biome_coaching"
  )
  
  # API Keys
  google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
  
  # Server Configuration
  port: int = int(os.getenv("PORT", "8080"))
  host: str = os.getenv("HOST", "0.0.0.0")
  reload: bool = os.getenv("RELOAD", "true").lower() == "true"
  
  # Application Settings
  debug: bool = os.getenv("DEBUG", "true").lower() == "true"
  log_level: str = os.getenv("LOG_LEVEL", "info")
  
  # File Upload Configuration
  uploads_dir: str = os.getenv("UPLOADS_DIR", "uploads")
  max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
  
  # MediaPipe Configuration
  mediapipe_model_complexity: int = int(os.getenv("MEDIAPIPE_MODEL_COMPLEXITY", "1"))
  pose_detection_fps: int = int(os.getenv("POSE_DETECTION_FPS", "10"))
  
  # ADK/Gemini Configuration
  adk_model: str = os.getenv("ADK_MODEL", "gemini-2.0-flash")
  adk_temperature: float = float(os.getenv("ADK_TEMPERATURE", "0.7"))
  
  # Cloud Storage (Optional)
  gcs_bucket_name: Optional[str] = os.getenv("GCS_BUCKET_NAME")
  s3_bucket_name: Optional[str] = os.getenv("S3_BUCKET_NAME")
  aws_region: Optional[str] = os.getenv("AWS_REGION")
  
  # CORS Configuration
  cors_origins: str = os.getenv(
    "CORS_ORIGINS", 
    "http://localhost:3000,http://localhost:8001,http://localhost:8081"
  )
  
  def validate(self) -> None:
    """Validate required configuration values."""
    if not self.google_api_key:
      raise ValueError(
        "GOOGLE_API_KEY environment variable is required. "
        "Get your key from: https://makersuite.google.com/app/apikey"
      )
    
    if not self.database_url:
      raise ValueError("DATABASE_URL environment variable is required")
  
  @property
  def is_production(self) -> bool:
    """Check if running in production mode."""
    return not self.debug
  
  @property
  def max_upload_size_bytes(self) -> int:
    """Get max upload size in bytes."""
    return self.max_upload_size_mb * 1024 * 1024


settings = Settings()


# ============================================
# CONSTANTS
# ============================================

# File validation constants
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.webm'}
MIN_VIDEO_SIZE_BYTES = 1024  # 1KB minimum
MAX_VIDEO_SIZE_BYTES = 100 * 1024 * 1024  # 100MB maximum

# Demo user constant (NULL UUID for database)
DEMO_USER_ID = None


