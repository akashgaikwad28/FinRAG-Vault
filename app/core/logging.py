import logging
import sys
from pythonjsonlogger import jsonlogger
from datetime import datetime, timezone
from app.core.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON log formatter to inject mandatory enterprise fields."""
    
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Inject standard timestamp in ISO format
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Inject log level
        log_record["level"] = record.levelname
        
        # Inject location info
        log_record["logger"] = record.name
        log_record["file"] = record.pathname
        log_record["line"] = record.lineno

        # Set default values for request telemetry if not provided
        if "request_id" not in log_record:
            log_record["request_id"] = None
        if "user_id" not in log_record:
            log_record["user_id"] = None
        if "endpoint" not in log_record:
            log_record["endpoint"] = None
        if "execution_time" not in log_record:
            log_record["execution_time"] = None
        if "status_code" not in log_record:
            log_record["status_code"] = None


def setup_logging() -> None:
    """Configures system-wide structured logging for the application."""
    root_logger = logging.getLogger()
    
    # Select log level from core configurations
    log_level_str = settings.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    root_logger.setLevel(log_level)
    
    # Remove existing default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Console stream handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Define structured properties mapping for search aggregations
    format_str = "%(timestamp)s %(level)s %(message)s %(request_id)s %(user_id)s %(endpoint)s %(execution_time)s %(status_code)s"
    
    json_formatter = CustomJsonFormatter(format_str)
    console_handler.setFormatter(json_formatter)
    
    root_logger.addHandler(console_handler)
    
    # Suppress noise from base libraries if level is high
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("qdrant_client").setLevel(logging.WARNING)
    
    logging.info("Structured JSON logging initialized successfully.")
