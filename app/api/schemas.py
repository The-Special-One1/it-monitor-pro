"""
IT Monitor Pro - API Schemas
=============================

Marshmallow schemas for request/response validation.

Why use schemas instead of manual validation?
  - Declarative: schema definition is self-documenting
  - Type safety: catches type errors before they hit the DB
  - Sanitization: auto-trim, lowercase, strip
  - Error messages: consistent 422 responses with field-level details
  - Separation of concerns: validation logic isolated from business logic

Reference: https://marshmallow.readthedocs.io/
"""

from marshmallow import Schema, fields, validate, validates, ValidationError, post_load

from app.utils.security import is_password_strong


# ============================================================
# Auth schemas (input validation)
# ============================================================

class RegisterSchema(Schema):
    """Validate POST /api/v1/auth/register payload."""

    email = fields.Email(
        required=True,
        error_messages={"required": "Email is required."},
    )
    password = fields.Str(
        required=True,
        load_only=True,
        error_messages={"required": "Password is required."},
    )
    full_name = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=100),
        error_messages={"required": "Full name is required."},
    )
    role = fields.Str(
        load_default="user",
        validate=validate.OneOf(["user", "support", "admin"]),
    )

    @validates("password")
    def validate_password_strength(self, value, **kwargs):
        """Enforce strong password rules."""
        is_strong, errors = is_password_strong(value)
        if not is_strong:
            raise ValidationError(
                "Password is not strong enough: " + "; ".join(errors)
            )

    @post_load
    def normalize_data(self, data, **kwargs):
        """Sanitize inputs after validation."""
        data["email"] = data["email"].lower().strip()
        data["full_name"] = data["full_name"].strip()
        return data


class LoginSchema(Schema):
    """Validate POST /api/v1/auth/login payload."""

    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)

    @post_load
    def normalize_email(self, data, **kwargs):
        data["email"] = data["email"].lower().strip()
        return data


# ============================================================
# Response schemas (output serialization)
# ============================================================

class UserResponseSchema(Schema):
    """Format User objects for JSON responses (excludes sensitive fields)."""

    class Meta:
        ordered = True

    id = fields.Int()
    email = fields.Email()
    full_name = fields.Str()
    role = fields.Str()
    is_active = fields.Bool()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class TokenResponseSchema(Schema):
    """Format JWT token response."""

    access_token = fields.Str(required=True)
    refresh_token = fields.Str()
    token_type = fields.Str(load_default="Bearer")
    expires_in = fields.Int()
    user = fields.Nested(UserResponseSchema)


# ============================================================
# Schema instances (singletons — reuse to save memory)
# ============================================================

register_schema = RegisterSchema()
login_schema = LoginSchema()
user_response_schema = UserResponseSchema()
token_response_schema = TokenResponseSchema()