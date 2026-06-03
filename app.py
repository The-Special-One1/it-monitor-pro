"""
IT Monitor Pro - Entry Point
=============================

Minimal entry point that uses the application factory.

For development:
    python app.py

For production (recommended):
    gunicorn --bind 0.0.0.0:5000 --workers 4 "app:app"
"""

import os

from app import create_app


# Create app instance using the factory
app = create_app(os.getenv("FLASK_ENV", "development"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=app.config.get("DEBUG", False),
    )