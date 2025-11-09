"""
Centralized logging configuration for Biome Coaching Agent.

Provides both development and production (Cloud Logging) formatters.
"""
import json
import logging
import sys
import os
from typing import Optional


def setup_logger(
    name: str,
    level: Optional[str] = None,
) -> logging.Logger:
    """
    Configure and return a logger instance for development.
    
    Args:
        name: Logger name (usually __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Defaults to INFO or value from LOG_LEVEL env var
    
    Returns:
        Configured logger instance
    """
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler with formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))
    
    # Format: timestamp - name - level - message
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    return logger


def setup_cloud_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Setup JSON structured logging for Cloud Logging compatibility.
    
    Cloud Logging expects JSON-formatted logs with specific fields.
    
    Args:
        name: Logger name
        level: Log level (defaults to INFO)
    
    Returns:
        Configured logger instance with JSON formatting
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    handler = logging.StreamHandler(sys.stdout)
    
    class JsonFormatter(logging.Formatter):
        """Format logs as JSON for Cloud Logging."""
        
        def format(self, record):
            log_obj = {
                'timestamp': self.formatTime(record, '%Y-%m-%dT%H:%M:%S.%fZ'),
                'severity': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
            }
            
            # Add exception info if present
            if record.exc_info:
                log_obj['exception'] = self.formatException(record.exc_info)
            
            # Add extra fields if present
            if hasattr(record, 'session_id'):
                log_obj['session_id'] = record.session_id
            if hasattr(record, 'user_id'):
                log_obj['user_id'] = record.user_id
            if hasattr(record, 'exercise_name'):
                log_obj['exercise_name'] = record.exercise_name
            
            return json.dumps(log_obj)
    
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get appropriate logger based on environment.
    
    Uses Cloud Logging format if CLOUD_RUN env var is set,
    otherwise uses development format.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    is_cloud = os.getenv("CLOUD_RUN", "false").lower() == "true"
    
    if is_cloud:
        return setup_cloud_logger(name)
    else:
        return setup_logger(name)

