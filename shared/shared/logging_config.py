import logging
import sys
import os
from datetime import datetime
from typing import Any, Dict
from pythonjsonlogger import jsonlogger
from shared.config import get_settings

settings = get_settings()

log_level = settings.app.log_level

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        """Add custom fields to log record"""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO format
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add log level
        log_record['level'] = record.levelname
        
        # Add logger name
        log_record['logger'] = record.name
        
        # Add process info
        log_record['pid'] = record.process
        
        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        if hasattr(record, 'service_name'):
            log_record['service'] = record.service_name
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id


def setup_logging(
    service_name: str = os.getenv("SERVICE_NAME"),
    log_level: str = log_level,
    json_output: bool = settings.app.json_output,
    log_file: str = settings.app.log_file
):

    # Remove existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers = []
    
    # Set log level
    level = getattr(logging, log_level.upper(), "DEBUG")
    root_logger.setLevel(level)
    
    # Create formatter
    if json_output:
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            timestamp=True
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Set service name as default attribute
    for handler in root_logger.handlers:
        handler.addFilter(ServiceNameFilter(service_name))
    
    # Configure third-party loggers
    logging.getLogger("pika").setLevel(level)
    logging.getLogger("urllib3").setLevel(level)
    logging.getLogger("psycopg2").setLevel(level)
    
    # Reduce PyMongo logging verbosity (suppress DEBUG heartbeat messages)
    # Set to WARNING to only show warnings and errors, not routine operations
    logging.getLogger("pymongo").setLevel(logging.INFO)
    logging.getLogger("pymongo.topology").setLevel(logging.INFO)
    logging.getLogger("pymongo.connection").setLevel(logging.INFO)
    logging.getLogger("pymongo.serverSelection").setLevel(logging.INFO)
    logging.getLogger("pymongo.command").setLevel(logging.INFO)
    
    logging.info(f"Logging configured for service: {service_name}", extra={"service_name": service_name})


class ServiceNameFilter(logging.Filter):
    """Filter to add service name to log records"""
    
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.service_name = self.service_name
        return True


def get_logger(name: str, service_name: str = None) -> logging.Logger:

    logger = logging.getLogger(name)
    if service_name:
        for handler in logger.handlers:
            handler.addFilter(ServiceNameFilter(service_name))
    return logger


class RequestContextFilter(logging.Filter):
    """Filter to add request context to log records"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # This can be extended to extract request context from thread-local storage
        # For now, it's a placeholder for future enhancement
        return True
