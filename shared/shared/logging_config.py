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

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        super().add_fields(log_record, record, message_dict)
        
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        log_record['level'] = record.levelname
        
        log_record['logger'] = record.name
        
        log_record['pid'] = record.process
        
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        
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

    root_logger = logging.getLogger()
    root_logger.handlers = []
    
    level = getattr(logging, log_level.upper(), "DEBUG")
    root_logger.setLevel(level)
    
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
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    for handler in root_logger.handlers:
        handler.addFilter(ServiceNameFilter(service_name))

    logging.getLogger("pika").setLevel(level)
    logging.getLogger("urllib3").setLevel(level)
    logging.getLogger("psycopg2").setLevel(level)
    
    logging.getLogger("pymongo").setLevel(logging.INFO)
    logging.getLogger("pymongo.topology").setLevel(logging.INFO)
    logging.getLogger("pymongo.connection").setLevel(logging.INFO)
    logging.getLogger("pymongo.serverSelection").setLevel(logging.INFO)
    logging.getLogger("pymongo.command").setLevel(logging.INFO)
    
    logging.info(f"Logging configured for service: {service_name}", extra={"service_name": service_name})


class ServiceNameFilter(logging.Filter):
    
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
    
    def filter(self, record: logging.LogRecord) -> bool:
        return True
