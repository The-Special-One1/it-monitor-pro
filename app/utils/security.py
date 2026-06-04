"""
IT Monitor Pro - Security Utilities
====================================

Cryptographic helpers for password hashing and verification.

Why bcrypt?
  - Industry standard for password storage
  - Built-in salt (prevents rainbow table attacks)
  - Adaptive cost factor (can be increased as hardware improves)
  - Slow by design (resists brute-force attacks)

Reference: https://en.wikipedia.org/wiki/Bcrypt

Security best practices:
  - NEVER store plain text passwords
  - NEVER log password hashes
  - NEVER compare hashes with `==` (use bcrypt's constant-time compare)
  - Rehash on login if cost factor was increased (future enhancement)
"""

import bcrypt


# Cost factor: 12 is a good balance between security and performance
# (each +1 doubles the time required).
# 10-12 is common in 2025; 14+ for high-security applications.
BCRYPT_ROUNDS = 12


def hash_password(plain_password: str) -> str:
    """
    Hash a plain text password using bcrypt.

    Args:
        plain_password: The user's chosen password.

    Returns:
        UTF-8 string containing the bcrypt hash.
        Format: $2b$12$<salt><hash> (60 chars total).

    Raises:
        ValueError: If password is empty or None.
    """
    if not plain_password:
        raise ValueError("Password cannot be empty")

    # Encode to bytes (bcrypt requires bytes)
    password_bytes = plain_password.encode("utf-8")

    # Generate salt + hash in one operation
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)

    # Return as string for easier DB storage
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Verify a plain password against a stored bcrypt hash.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        plain_password: The password attempt to verify.
        password_hash:  The stored bcrypt hash.

    Returns:
        True if the password matches, False otherwise.
        Returns False on any error (never raises for invalid inputs).
    """
    if not plain_password or not password_hash:
        return False

    try:
        password_bytes = plain_password.encode("utf-8")
        hash_bytes = password_hash.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except (ValueError, TypeError):
        # Malformed hash or invalid input → fail closed
        return False


def is_password_strong(password: str) -> tuple[bool, list[str]]:
    """
    Validate password strength against basic rules.

    Rules:
      - At least 8 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit

    Args:
        password: The password to evaluate.

    Returns:
        Tuple of (is_strong, list_of_errors).
        Example: (False, ["must contain at least one digit"])
    """
    errors = []

    if len(password) < 8:
        errors.append("must be at least 8 characters long")
    if not any(c.isupper() for c in password):
        errors.append("must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        errors.append("must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        errors.append("must contain at least one digit")

    return (len(errors) == 0, errors)