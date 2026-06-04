"""
IT Monitor Pro - User Model
============================

SQLAlchemy model for application users with authentication support.

Features:
  - Password hashing via bcrypt (never store plain passwords)
  - Role-based access control (RBAC): admin, support, user
  - Soft delete via is_active flag (preserves audit trail)
  - Automatic timestamps (created_at, updated_at)
  - JSON serialization helper (excludes sensitive fields)

Security notes:
  - Passwords are NEVER stored in plain text
  - password_hash is excluded from to_dict() by default
  - Email uniqueness is enforced at the DB level
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.utils.security import hash_password, verify_password


class User(db.Model):
    """
    Represents a registered user of the IT Monitor Pro system.

    Maps to the 'users' table in the database.
    """

    __tablename__ = "users"

    # --- Primary key ---
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Authentication ---
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,  # speeds up login queries
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Profile ---
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # --- Authorization ---
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",  # default role
    )

    # --- Status ---
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ============================================================
    # Password handling (security-critical methods)
    # ============================================================

    def set_password(self, plain_password: str) -> None:
        """
        Hash a plain text password and store the hash.

        Args:
            plain_password: The user's chosen password (plain text).

        Note:
            The plain password is NEVER stored — only the bcrypt hash.
        """
        self.password_hash = hash_password(plain_password)

    def check_password(self, plain_password: str) -> bool:
        """
        Verify a plain password against the stored hash.

        Args:
            plain_password: The password attempt to verify.

        Returns:
            True if the password matches, False otherwise.
        """
        return verify_password(plain_password, self.password_hash)

    # ============================================================
    # Serialization
    # ============================================================

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Convert the user instance to a dictionary for JSON serialization.

        Args:
            include_sensitive: If True, includes fields like email.
                               Default False for public-facing responses.

        Returns:
            Dictionary representation of the user.
            password_hash is NEVER included.
        """
        data = {
            "id": self.id,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_sensitive:
            data["email"] = self.email
        return data

    # ============================================================
    # Class methods (queries)
    # ============================================================

    @classmethod
    def find_by_email(cls, email: str) -> Optional["User"]:
        """
        Find a user by their email address.

        Args:
            email: The email to search for.

        Returns:
            User instance if found, None otherwise.
        """
        return db.session.query(cls).filter_by(email=email.lower().strip()).first()

    @classmethod
    def find_by_id(cls, user_id: int) -> Optional["User"]:
        """
        Find a user by their ID.

        Args:
            user_id: The user's primary key.

        Returns:
            User instance if found, None otherwise.
        """
        return db.session.get(cls, user_id)

    # ============================================================
    # Representation
    # ============================================================

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"