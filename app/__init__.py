"""
IT Monitor Pro - Application Factory
=====================================

This module implements the Application Factory pattern, which is the
recommended way to structure a Flask application.

Benefits:
  - Multiple app instances with different configs (dev/test/prod)
  - Testable: each test can create a fresh app with test config
  - Lazy initialization: extensions are initialized when app is created
  - Avoids circular imports

Reference: https://flask.palletsprojects.com/en/latest/patterns/appfactories/
"""

from flask import Flask, jsonify

from app.config import get_config


def create_app(config_name: str = None) -> Flask:
    """
    Application factory.

    Args:
        config_name: Name of the configuration to use.
                     Options: 'development', 'testing', 'production'.
                     If None, reads from FLASK_ENV environment variable.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # ----------------------------------------------------------------
    # 1. Load configuration
    # ----------------------------------------------------------------
    config = get_config(config_name)
    app.config.from_object(config)

    # ----------------------------------------------------------------
       # ----------------------------------------------------------------
    # 2. Initialize extensions (db, jwt, cors, etc.)
    # ----------------------------------------------------------------
    from app.extensions import init_extensions
    init_extensions(app)

    # ----------------------------------------------------------------
    # 2b. Register models (so SQLAlchemy knows about them)
    # ----------------------------------------------------------------
    with app.app_context():
        from app.models import user  # noqa: F401 — import for side effects
        from app.extensions import db
        db.create_all()

    # ----------------------------------------------------------------
    # 3. Register blueprints (modular endpoints)
    # ----------------------------------------------------------------
    from app.api.health import health_bp
    app.register_blueprint(health_bp, url_prefix="/api/v1")

    from app.api.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix="/api/v1")

    # ----------------------------------------------------------------
    # 4. Root endpoint - API discovery
    # ----------------------------------------------------------------
    @app.route("/", methods=["GET"])
    def index():
        """Root endpoint for API discovery."""
        return jsonify({
            "service": "IT Monitor Pro API",
            "version": app.config.get("API_VERSION", "0.1.0"),
            "description": "Monitoring & incident management for IT operations",
            "endpoints": {
                "health":  "/api/v1/health",
                "docs":    "Coming soon: /docs",
            },
            "author": "Santo António",
        }), 200

    # ----------------------------------------------------------------
    # 5. Global error handlers
    # ----------------------------------------------------------------
    register_error_handlers(app)

    return app


def register_error_handlers(app: Flask) -> None:
    """
    Register global error handlers for common HTTP errors.

    This ensures all error responses follow a consistent JSON format,
    which is essential for API clients to handle errors programmatically.
    """

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            "error": "Bad Request",
            "message": str(error.description) if hasattr(error, "description") else "Invalid request",
            "status_code": 400,
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "error": "Not Found",
            "message": "The requested resource does not exist",
            "status_code": 404,
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            "error": "Method Not Allowed",
            "message": "The HTTP method is not supported for this endpoint",
            "status_code": 405,
        }), 405

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "status_code": 500,
        }), 500