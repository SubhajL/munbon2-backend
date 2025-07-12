"""Structured logging configuration for Munbon services."""

import sys
import structlog
from typing import Any, Dict, Optional
from structlog.types import Processor


def add_service_info(service_name: str) -> Processor:
    """Add service information to log entries."""
    def processor(
        logger: Any,
        method_name: str,
        event_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        event_dict["service"] = service_name
        return event_dict
    
    return processor


def configure_logging(
    service_name: str,
    log_level: str = "INFO",
    json_logs: bool = True
) -> None:
    """
    Configure structured logging for the service.
    
    Args:
        service_name: Name of the service
        log_level: Logging level
        json_logs: Whether to output JSON logs
    """
    processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_service_info(service_name),
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            ]
        ),
    ]
    
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    import logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (usually module name)
        
    Returns:
        Configured logger instance
    """
    return structlog.get_logger(name)