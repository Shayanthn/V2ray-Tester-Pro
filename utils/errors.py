import logging
import traceback
from enum import Enum, auto
from typing import Optional

class ErrorCategory(Enum):
    NETWORK = auto()
    CONFIG_PARSING = auto()
    PROTOCOL_ERROR = auto()
    SYSTEM_ERROR = auto()
    VALIDATION_ERROR = auto()
    UNKNOWN = auto()

class AppError(Exception):
    """Base class for application-specific exceptions."""
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.category = category
        self.original_exception = original_exception

class NetworkError(AppError):
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.NETWORK, original_exception)

class ConfigError(AppError):
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.CONFIG_PARSING, original_exception)

class ProtocolError(AppError):
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.PROTOCOL_ERROR, original_exception)

class ValidationError(AppError):
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message, ErrorCategory.VALIDATION_ERROR, original_exception)

def log_error(logger: logging.Logger, error: Exception, context: str = ""):
    """
    Logs an error with structured information.
    """
    if isinstance(error, AppError):
        category = error.category.name
        msg = str(error)
        original = error.original_exception
    else:
        category = ErrorCategory.UNKNOWN.name
        msg = str(error)
        original = None

    log_msg = f"[{category}] {context}: {msg}"
    if original:
        log_msg += f" | Caused by: {type(original).__name__}: {str(original)}"
    
    logger.error(log_msg)
    logger.debug(traceback.format_exc())
