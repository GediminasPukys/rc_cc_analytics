"""
Enhanced logging configuration for full transparency.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

def setup_logging():
    """Configure comprehensive logging for the application."""
    
    # Create logs directory
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    function_formatter = logging.Formatter(
        '%(asctime)s | FUNCTION_CALL | %(message)s | Args: %(arguments)s | Result: %(result)s | Duration: %(duration_ms).2fms',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler for all logs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(detailed_formatter)
    
    # File handler for all logs
    file_handler = logging.FileHandler(
        log_dir / f"clinic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # Special file handler for function calls
    function_handler = logging.FileHandler(
        log_dir / f"function_calls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    function_handler.setLevel(logging.INFO)
    function_handler.setFormatter(detailed_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Configure function calls logger
    function_logger = logging.getLogger("function.calls")
    function_logger.addHandler(function_handler)
    function_logger.propagate = False  # Don't propagate to root
    
    # Set levels for specific loggers
    logging.getLogger("clinic").setLevel(logging.DEBUG)
    logging.getLogger("livekit").setLevel(logging.INFO)
    logging.getLogger("openai").setLevel(logging.INFO)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    logger = logging.getLogger("logging_config")
    logger.info(f"Logging configured - Logs directory: {log_dir}")
    logger.info("Function calls will be logged separately for analysis")
    
    return log_dir