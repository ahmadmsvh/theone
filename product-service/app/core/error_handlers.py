
from functools import wraps
from flask import jsonify, request
from pydantic import ValidationError as PydanticValidationError
import os
from typing import Callable, Any
from shared.logging_config import get_logger

logger = get_logger(__name__, os.getenv("SERVICE_NAME"))


class APIError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(APIError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


def handle_api_errors(f: Callable) -> Callable:
    @wraps(f)
    async def wrapper(*args, **kwargs):
        try:
            return await f(*args, **kwargs)
        except PydanticValidationError as e:
            logger.warning(f"Validation error in {f.__name__}: {e}")
            return jsonify({
                "error": "Validation error",
                "details": e.errors()
            }), 400
        except PermissionError as e:
            logger.warning(f"Permission denied in {f.__name__}: {e}")
            return jsonify({"error": str(e)}), 403
        except ValueError as e:
            logger.warning(f"Value error in {f.__name__}: {e}")
            return jsonify({"error": str(e)}), 400
        except NotFoundError as e:
            logger.info(f"Resource not found in {f.__name__}: {e.message}")
            return jsonify({"error": e.message}), 404
        except APIError as e:
            logger.warning(f"API error in {f.__name__}: {e.message}")
            return jsonify({"error": e.message}), e.status_code
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {e}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500
    
    return wrapper


def validate_request(schema_class):
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        async def wrapper(*args, **kwargs):
            try:
                data = schema_class(**request.json)
                kwargs['validated_data'] = data
                return await f(*args, **kwargs)
            except PydanticValidationError as e:
                logger.warning(f"Request validation failed in {f.__name__}: {e}")
                return jsonify({
                    "error": "Validation error",
                    "details": e.errors()
                }), 400
        return wrapper
    return decorator


def not_found_response(message: str = "Resource not found") -> tuple:
    return jsonify({"error": message}), 404


def bad_request_response(message: str, details: list = None) -> tuple:
    response = {"error": message}
    if details:
        response["details"] = details
    return jsonify(response), 400


def forbidden_response(message: str = "Access denied") -> tuple:
    return jsonify({"error": message}), 403


def internal_error_response(message: str = "Internal server error") -> tuple:
    return jsonify({"error": message}), 500

