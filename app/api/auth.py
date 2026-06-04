"""
IT Monitor Pro - Authentication Blueprint
==========================================

REST endpoints for user authentication using JWT (JSON Web Tokens).

Endpoints:
  POST /api/v1/auth/register   → Create a new user account
  POST /api/v1/auth/login      → Authenticate and receive JWT tokens
  GET  /api/v1/auth/me         → Get current user info (protected)
  POST /api/v1/auth/refresh    → Renew access token using refresh token

Security:
  - Passwords hashed with bcrypt before storage
  - JWT tokens signed with HMAC-SHA256
  - Access tokens expire in 1 hour (configurable)
  - Refresh tokens expire in 30 days
  - Failed login attempts are logged for security audit
"""

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.schemas import (
    register_schema,
    login_schema,
    user_response_schema,
)
from app.extensions import db
from app.models.user import User


# Set up logger for security audit
logger = logging.getLogger(__name__)

# Create the blueprint
auth_bp = Blueprint("auth", __name__)


# ============================================================
# POST /register
# ============================================================
@auth_bp.route("/auth/register", methods=["POST"])
def register():
    """
    Register a new user account.

    Request body (JSON):
        {
            "email":     "user@example.com",
            "password":  "StrongPass1",
            "full_name": "John Doe",
            "role":      "user"  (optional, defaults to "user")
        }

    Responses:
        201 Created:        User created successfully
        400 Bad Request:    Missing JSON body
        409 Conflict:       Email already registered
        422 Unprocessable:  Validation failed (weak password, invalid email, etc.)
    """
    # Ensure JSON content
    if not request.is_json:
        return jsonify({
            "error": "Bad Request",
            "message": "Content-Type must be application/json",
            "status_code": 400,
        }), 400

    # Validate payload against schema
    try:
        data = register_schema.load(request.get_json())
    except ValidationError as err:
        logger.warning(f"Registration validation failed: {err.messages}")
        return jsonify({
            "error": "Validation Error",
            "message": "Invalid input data",
            "details": err.messages,
            "status_code": 422,
        }), 422

    # Check if email already exists
    if User.find_by_email(data["email"]):
        logger.info(f"Registration attempt with existing email: {data['email']}")
        return jsonify({
            "error": "Conflict",
            "message": "An account with this email already exists",
            "status_code": 409,
        }), 409

    # Create user
    try:
        user = User(
            email=data["email"],
            full_name=data["full_name"],
            role=data.get("role", "user"),
        )
        user.set_password(data["password"])

        db.session.add(user)
        db.session.commit()

        logger.info(f"New user registered: {user.email} (role={user.role})")

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "Conflict",
            "message": "An account with this email already exists",
            "status_code": 409,
        }), 409
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Unexpected error during registration: {exc}")
        return jsonify({
            "error": "Internal Server Error",
            "message": "Could not create user account",
            "status_code": 500,
        }), 500

    return jsonify({
        "message": "User registered successfully",
        "user": user_response_schema.dump(user),
    }), 201


# ============================================================
# POST /login
# ============================================================
@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """
    Authenticate user and return JWT tokens.

    Request body (JSON):
        {
            "email":    "user@example.com",
            "password": "StrongPass1"
        }

    Responses:
        200 OK:             Login successful, returns tokens + user info
        400 Bad Request:    Missing JSON body
        401 Unauthorized:   Invalid credentials OR inactive account
        422 Unprocessable:  Validation failed
    """
    if not request.is_json:
        return jsonify({
            "error": "Bad Request",
            "message": "Content-Type must be application/json",
            "status_code": 400,
        }), 400

    try:
        data = login_schema.load(request.get_json())
    except ValidationError as err:
        return jsonify({
            "error": "Validation Error",
            "message": "Invalid input data",
            "details": err.messages,
            "status_code": 422,
        }), 422

    # Find user
    user = User.find_by_email(data["email"])

    # IMPORTANT: Same error message whether user doesn't exist OR password wrong
    # This prevents user enumeration attacks (telling attackers if email exists)
    if not user or not user.check_password(data["password"]):
        logger.warning(f"Failed login attempt for: {data['email']}")
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid email or password",
            "status_code": 401,
        }), 401

    # Check if account is active
    if not user.is_active:
        logger.warning(f"Login attempt on inactive account: {user.email}")
        return jsonify({
            "error": "Unauthorized",
            "message": "Account is deactivated. Contact your administrator.",
            "status_code": 401,
        }), 401

    # Generate tokens
    # identity = user ID (string for compatibility)
    # additional_claims = info to embed in the token (no extra DB calls needed)
    identity = str(user.id)
    claims = {
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
    }

    access_token = create_access_token(identity=identity, additional_claims=claims)
    refresh_token = create_refresh_token(identity=identity)

    logger.info(f"Successful login: {user.email} (role={user.role})")

    return jsonify({
        "message": "Login successful",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "user": user_response_schema.dump(user),
    }), 200


# ============================================================
# GET /me (PROTECTED)
# ============================================================
@auth_bp.route("/auth/me", methods=["GET"])
@jwt_required()
def get_current_user():
    """
    Get the currently authenticated user's information.

    Headers:
        Authorization: Bearer <access_token>

    Responses:
        200 OK:           Returns user details
        401 Unauthorized: Missing/invalid/expired token (handled by JWT extension)
        404 Not Found:    User no longer exists (e.g., deleted after token issued)
    """
    user_id = get_jwt_identity()
    user = User.find_by_id(int(user_id))

    if not user:
        return jsonify({
            "error": "Not Found",
            "message": "User no longer exists",
            "status_code": 404,
        }), 404

    if not user.is_active:
        return jsonify({
            "error": "Unauthorized",
            "message": "Account is deactivated",
            "status_code": 401,
        }), 401

    return jsonify({
        "user": user_response_schema.dump(user),
    }), 200


# ============================================================
# POST /refresh (uses refresh token)
# ============================================================
@auth_bp.route("/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    """
    Issue a new access token using a valid refresh token.

    Headers:
        Authorization: Bearer <refresh_token>

    Responses:
        200 OK:           Returns new access token
        401 Unauthorized: Missing/invalid/expired refresh token
    """
    user_id = get_jwt_identity()
    user = User.find_by_id(int(user_id))

    if not user or not user.is_active:
        return jsonify({
            "error": "Unauthorized",
            "message": "User account is invalid or deactivated",
            "status_code": 401,
        }), 401

    # Re-embed claims (in case role changed since last login)
    claims = {
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
    }

    new_access_token = create_access_token(
        identity=str(user.id),
        additional_claims=claims,
    )

    logger.info(f"Token refreshed for: {user.email}")

    return jsonify({
        "access_token": new_access_token,
        "token_type": "Bearer",
    }), 200