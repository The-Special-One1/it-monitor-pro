"""
IT Monitor Pro - Flask Extensions
==================================

Centralised initialization of Flask extensions using the lazy pattern.

Why lazy initialization?
  Extensions are instantiated at module level (without an app),
  then bound to specific apps via `extension.init_app(app)`.
  This is required for the Application Factory pattern to work correctly.

Reference: https://flask.palletsprojects.com/en/latest/extensiondev/
"""

from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


# ----------------------------------------------------------------
# Base class for all SQLAlchemy models (modern SQLAlchemy 2.x style)
# ----------------------------------------------------------------
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ----------------------------------------------------------------
# Extension instances (created once, bound later)
# ----------------------------------------------------------------
db = SQLAlchemy(model_class=Base)
jwt = JWTManager()
cors = CORS()


def init_extensions(app: Flask) -> None:
    """
    Bind all extensions to the Flask app.

    Called from the application factory after config is loaded.

    Args:
        app: The Flask application instance to bind extensions to.
    """
    # Database
    db.init_app(app)

    # JWT Authentication
    jwt.init_app(app)
    _register_jwt_handlers(jwt)

    # CORS (Cross-Origin Resource Sharing)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*")}},
        supports_credentials=True,
    )


def _register_jwt_handlers(jwt_manager: JWTManager) -> None:
    """
    Register custom JWT error handlers.

    These handlers ensure consistent JSON error responses for
    authentication failures — critical for API troubleshooting.
    """

    @jwt_manager.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {
            "error": "Token Expired",
            "message": "The access token has expired. Please log in again.",
            "status_code": 401,
        }, 401

    @jwt_manager.invalid_token_loader
    def invalid_token_callback(error_string):
        return {
            "error": "Invalid Token",
            "message": f"Token validation failed: {error_string}",
            "status_code": 422,
        }, 422

    @jwt_manager.unauthorized_loader
    def missing_token_callback(error_string):
        return {
            "error": "Authorization Required",
            "message": "Missing Authorization header. Include 'Bearer <token>'.",
            "status_code": 401,
        }, 401

    @jwt_manager.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return {
            "error": "Token Revoked",
            "message": "This token has been revoked. Please log in again.",
            "status_code": 401,
        }, 401