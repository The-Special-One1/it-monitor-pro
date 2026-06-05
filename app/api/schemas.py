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
from marshmallow.validate import OneOf, Length

from app.models.incident import (
    IncidentSeverity, IncidentStatus, IncidentCategory, IncidentSource,
)

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



# ============================================================
# INCIDENT SCHEMAS
# ============================================================

# Helper: extract Enum values for marshmallow.OneOf validation
_SEVERITY_VALUES = [e.value for e in IncidentSeverity]
_STATUS_VALUES = [e.value for e in IncidentStatus]
_CATEGORY_VALUES = [e.value for e in IncidentCategory]
_SOURCE_VALUES = [e.value for e in IncidentSource]


class IncidentCreateSchema(Schema):
    """
    Validate POST /api/v1/incidents payload.

    Used when a user (or the alerting engine) reports a new incident.
    """

    title = fields.Str(
        required=True,
        validate=Length(min=5, max=200),
        error_messages={"required": "Title is required."},
    )
    description = fields.Str(
        required=True,
        validate=Length(min=10, max=5000),
        error_messages={"required": "Description is required."},
    )
    severity = fields.Str(
        load_default=IncidentSeverity.MEDIUM.value,
        validate=OneOf(_SEVERITY_VALUES),
    )
    category = fields.Str(
        load_default=IncidentCategory.OTHER.value,
        validate=OneOf(_CATEGORY_VALUES),
    )
    source = fields.Str(
        load_default=IncidentSource.MANUAL.value,
        validate=OneOf(_SOURCE_VALUES),
    )
    sla_minutes = fields.Int(
        load_default=None,
        validate=validate.Range(min=1, max=43200),  # 1 min .. 30 days
    )

    @post_load
    def trim_strings(self, data, **kwargs):
        data["title"] = data["title"].strip()
        data["description"] = data["description"].strip()
        return data


class IncidentUpdateSchema(Schema):
    """
    Validate PATCH /api/v1/incidents/<id> payload.

    All fields are optional — only provided fields are updated.
    """

    title = fields.Str(validate=Length(min=5, max=200))
    description = fields.Str(validate=Length(min=10, max=5000))
    severity = fields.Str(validate=OneOf(_SEVERITY_VALUES))
    status = fields.Str(validate=OneOf(_STATUS_VALUES))
    category = fields.Str(validate=OneOf(_CATEGORY_VALUES))
    assigned_to_id = fields.Int(allow_none=True)
    sla_minutes = fields.Int(
        allow_none=True,
        validate=validate.Range(min=1, max=43200),
    )

    @post_load
    def trim_strings(self, data, **kwargs):
        if "title" in data:
            data["title"] = data["title"].strip()
        if "description" in data:
            data["description"] = data["description"].strip()
        return data


class IncidentFilterSchema(Schema):
    """
    Validate query string parameters for GET /api/v1/incidents.

    Example: ?status=OPEN&severity=CRITICAL&category=DISK&page=1&per_page=20
    """

    status = fields.Str(validate=OneOf(_STATUS_VALUES))
    severity = fields.Str(validate=OneOf(_SEVERITY_VALUES))
    category = fields.Str(validate=OneOf(_CATEGORY_VALUES))
    source = fields.Str(validate=OneOf(_SOURCE_VALUES))
    assigned_to_id = fields.Int()
    reported_by_id = fields.Int()
    include_deleted = fields.Bool(load_default=False)
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))


class IncidentResponseSchema(Schema):
    """Format Incident objects for JSON responses."""

    class Meta:
        ordered = True

    id = fields.Int()
    title = fields.Str()
    description = fields.Str()
    severity = fields.Method("get_severity")
    status = fields.Method("get_status")
    category = fields.Method("get_category")
    source = fields.Method("get_source")
    reported_by_id = fields.Int()
    assigned_to_id = fields.Int(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    resolved_at = fields.DateTime(allow_none=True)
    sla_minutes = fields.Int(allow_none=True)
    sla_breached = fields.Method("get_sla_breached")
    is_deleted = fields.Bool()

    # Convert SQLAlchemy Enum -> string value
    def get_severity(self, obj):
        return obj.severity.value if obj.severity else None

    def get_status(self, obj):
        return obj.status.value if obj.status else None

    def get_category(self, obj):
        return obj.category.value if obj.category else None

    def get_source(self, obj):
        return obj.source.value if obj.source else None

    def get_sla_breached(self, obj):
        return obj.is_sla_breached()


# ============================================================
# Schema instances (singletons)
# ============================================================

incident_create_schema = IncidentCreateSchema()
incident_update_schema = IncidentUpdateSchema()
incident_filter_schema = IncidentFilterSchema()
incident_response_schema = IncidentResponseSchema()
incidents_response_schema = IncidentResponseSchema(many=True)