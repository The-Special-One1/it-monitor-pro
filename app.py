"""
IT Monitor Pro - Flask Application Entry Point

A monitoring and incident management system designed to support
IT operations, API integrations, and SLA-based escalation.

Author: Santo António
Stack:  Python · Flask · SQLAlchemy · psutil
"""

from datetime import datetime, timezone
from flask import Flask, jsonify


def create_app():
    """
    Application factory pattern.

    Creates and configures a Flask application instance.
    Using a factory keeps the app testable and flexible
    (e.g. different configs for dev/test/production).
    """
    app = Flask(__name__)

    # ----------------------------------------------------------------
    # Health check endpoint
    # ----------------------------------------------------------------
    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint.

        Used by:
          - Container orchestrators (Docker, Kubernetes)
          - Load balancers
          - Monitoring tools (uptime checks)

        Returns 200 OK if the service is alive.
        """
        return jsonify({
            "status": "healthy",
            "service": "IT Monitor Pro",
            "version": "0.1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    # ----------------------------------------------------------------
    # Root endpoint - API discovery
    # ----------------------------------------------------------------
    @app.route("/", methods=["GET"])
    def index():
        """
        Root endpoint that lists available API endpoints.
        Useful for API discovery and documentation.
        """
        return jsonify({
            "service": "IT Monitor Pro API",
            "version": "0.1.0",
            "description": "Monitoring & incident management for IT operations",
            "endpoints": {
                "health": "/health",
                "docs": "Coming soon: /docs",
            },
            "author": "Santo António",
        }), 200

    return app


# ----------------------------------------------------------------
# Entry point when running directly with: python app.py
# ----------------------------------------------------------------
if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",   # accept connections from any IP (needed for WSL/Docker)
        port=5000,
        debug=True,        # auto-reload on code changes (dev only)
    )