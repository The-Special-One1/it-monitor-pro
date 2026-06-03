"""
IT Monitor Pro - Configuration Module
======================================

Centralised configuration using the inheritance pattern.

Three environments are supported:
  - DevelopmentConfig: local development (debug mode, SQLite)
  - TestingConfig:     automated tests (in-memory DB, no JWT expiration)
  - ProductionConfig:  live deployment (loaded from environment vars)

All sensitive values (secrets, DB URLs) are loaded from environment
variables — never hardcoded — following the 12-Factor App principles.

Reference: https://12factor.net/config
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present (development convenience)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class BaseConfig:
    """Base configuration shared by all environments."""

    # --- Application metadata ---
    API_VERSION = "0.1.0"
    APP_NAME = "IT Monitor Pro"

    # --- Security ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production")

    # --- JWT (JSON Web Tokens) ---
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-dev-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_ERROR_MESSAGE_KEY = "message"  # consistent error format

    # --- Database ---
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # disables a noisy Flask-SQLAlchemy feature
    SQLALCHEMY_ECHO = False                  # set True to log all SQL queries

    # --- CORS ---
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")


class DevelopmentConfig(BaseConfig):
    """Local development configuration."""

    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'dev.db'}"
    )
    SQLALCHEMY_ECHO = True  # log SQL queries (helpful during development)


class TestingConfig(BaseConfig):
    """Testing configuration — used by pytest."""

    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"  # in-memory DB (fast, isolated)
    JWT_ACCESS_TOKEN_EXPIRES = False  # tokens never expire during tests
    WTF_CSRF_ENABLED = False           # disable CSRF for easier testing


class ProductionConfig(BaseConfig):
    """Production configuration — all secrets from environment variables."""

    DEBUG = False
    TESTING = False

    # Production MUST use environment variables
    SECRET_KEY = os.environ.get("SECRET_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    @classmethod
    def validate(cls):
        """Ensure all required production env vars are set."""
        required = ["SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL"]
        missing = [var for var in required if not os.environ.get(var)]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables for production: {missing}"
            )


# --- Config registry ---
config_by_name = {
    "development": DevelopmentConfig,
    "testing":     TestingConfig,
    "production":  ProductionConfig,
}


def get_config(config_name: str = None) -> BaseConfig:
    """
    Return the appropriate configuration class.

    Args:
        config_name: 'development', 'testing', or 'production'.
                     Falls back to FLASK_ENV env var, then 'development'.

    Returns:
        Configuration class (not an instance).
    """
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    config_class = config_by_name.get(config_name, DevelopmentConfig)

    # Validate production config early
    if config_name == "production":
        config_class.validate()

    return config_class