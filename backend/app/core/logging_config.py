"""
Logging configuration.
"""

import logging
import sys
from app.config import settings


def setup_logging():
    """Configure application logging."""
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    
    # Create logger
    logger = logging.getLogger("wangp")
    logger.setLevel(log_level)
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    
    # Add handler
    if not logger.handlers:
        logger.addHandler(handler)
    
    return logger


logger = setup_logging()
