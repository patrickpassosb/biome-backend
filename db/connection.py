"""
Database connection utilities for PostgreSQL using psycopg (v3).
Provides a context manager with connection pooling for better performance.
Optimized for Neon serverless PostgreSQL + Cloud Run.
"""
import contextlib
from typing import Iterator, Optional

import psycopg
from psycopg_pool import ConnectionPool

# Import logger - avoid circular import by importing locally if needed
try:
  from biome_coaching_agent.logging_config import get_logger
  from biome_coaching_agent.config import settings
  logger = get_logger(__name__)
except ImportError:
  # Fallback to basic logging if biome_coaching_agent not available
  import logging
  import os
  logger = logging.getLogger(__name__)
  
  # Fallback settings if config not available
  class _FallbackSettings:
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/biome_coaching")
  settings = _FallbackSettings()


# Global connection pool (initialized on first use)
_pool: Optional[ConnectionPool] = None


def _get_connection_string() -> str:
  """Get database connection string from centralized config."""
  logger.debug(f"Using DATABASE_URL from settings")
  return settings.database_url


def get_pool() -> ConnectionPool:
  """
  Get or create the database connection pool.
  
  Pool configuration optimized for Neon serverless + Cloud Run:
  - min_size=0: No minimum connections (serverless-friendly, scales to zero)
  - max_size=5: Allow up to 5 concurrent connections (sufficient for Cloud Run)
  - timeout=30: Wait max 30s for available connection
  - max_idle=120: Close idle connections after 2 minutes
  - max_lifetime=1800: Recycle connections after 30 minutes (Neon-friendly)
  - connect_timeout=10: Timeout connection attempts after 10 seconds
  - statement_timeout=60s: Timeout long-running queries
  
  Returns:
    ConnectionPool: Shared connection pool instance
  """
  global _pool
  
  if _pool is None:
    conn_string = _get_connection_string()
    logger.info("Initializing database connection pool (min=0, max=5) for Neon serverless")
    
    try:
      _pool = ConnectionPool(
        conn_string,
        min_size=0,  # No minimum for serverless (Neon can scale to zero)
        max_size=5,  # Smaller pool for Cloud Run + Neon serverless
        timeout=30,
        max_idle=120,  # Close idle connections after 2 minutes
        max_lifetime=1800,  # Recycle connections after 30 minutes (prevents stale connections)
        kwargs={
          "connect_timeout": 10,  # Timeout connection attempts after 10 seconds
          "options": "-c statement_timeout=60000",  # 60 second query timeout
        },
      )
      logger.info("Connection pool initialized successfully for Neon serverless")
    except Exception as e:
      logger.error(f"Failed to initialize connection pool: {e}", exc_info=True)
      raise
  
  return _pool


@contextlib.contextmanager
def get_db_connection() -> Iterator[psycopg.Connection]:
  """
  Yield a PostgreSQL connection from the pool.
  
  Uses connection pooling for better performance (50-70% faster).
  Handles commit/rollback automatically and returns connection to pool.
  
  Yields:
    psycopg.Connection: Database connection from pool
    
  Raises:
    psycopg.Error: Database connection or operation failed
  """
  pool = get_pool()
  logger.debug("Acquiring connection from pool")
  
  try:
    with pool.connection() as conn:
      logger.debug("Connection acquired from pool")
      try:
        yield conn
        conn.commit()
        logger.debug("Database transaction committed")
      except Exception as e:
        conn.rollback()
        logger.warning(f"Database transaction rolled back due to error: {e}")
        raise
  except psycopg.Error as conn_err:
    logger.error(f"Database operation failed: {conn_err}", exc_info=True)
    raise


def close_pool() -> None:
  """Close the connection pool gracefully (call on shutdown)."""
  global _pool
  if _pool is not None:
    logger.info("Closing database connection pool")
    _pool.close()
    _pool = None


