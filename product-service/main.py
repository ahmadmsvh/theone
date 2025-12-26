from flask import Flask, jsonify
import os

from app.core.database import get_db_manager
from app.api.v1.products import bp as products_bp
from app.utils import run_async
from shared.logging_config import setup_logging, get_logger
from shared.config import get_settings

settings = get_settings()
setup_logging(service_name=os.getenv("SERVICE_NAME"), log_level=settings.app.log_level)
logger = get_logger(__name__, os.getenv("SERVICE_NAME"))


def create_app(config=None, init_db=True):

    app = Flask(__name__)
    
    # Load configuration if provided
    if config:
        app.config.update(config)
    
    # Register blueprints
    app.register_blueprint(products_bp)
    
    # Register routes
    @app.route("/")
    def home():
        """Health check endpoint"""
        return jsonify({"message": "product-service-running", "status": "ok"})
    
    @app.route("/health")
    def health_check():
        """Health check with database connection"""
        try:
            db_manager = get_db_manager()
            is_healthy = run_async(db_manager.health_check())
            if is_healthy:
                return jsonify({
                    "status": "healthy",
                    "service": "product-service",
                    "database": "connected"
                }), 200
            else:
                return jsonify({
                    "status": "unhealthy",
                    "service": "product-service",
                    "database": "disconnected"
                }), 503
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                "status": "unhealthy",
                "service": "product-service",
                "error": str(e)
            }), 503
    
    # Initialize database if requested
    if init_db:
        _init_database()
    
    return app


def _init_database():

    try:
        db_manager = get_db_manager()
        run_async(db_manager.connect())
        run_async(db_manager.create_indexes())
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


# Create app instance with automatic database initialization
app = create_app()


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True, host="0.0.0.0", port=5001)
