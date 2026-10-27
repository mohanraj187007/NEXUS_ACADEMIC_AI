"""
Cryptographic Security & Authentication Utilities
Academic Attendance Pattern & Risk Analytics System (NEXUS ACADEMIC AI)

Provides FIPS/NIST-compliant PBKDF2-HMAC-SHA256 password hashing with random salt,
constant-time equality comparison to thwart timing attacks, cryptographically secure
session and reset token generation, input sanitization, and enterprise password policy validation.
"""

import hashlib
import hmac
import secrets
import re
from typing import Tuple, Optional


# Cryptographic Parameters (OWASP compliant)
PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 600000
SALT_BYTES = 16


def hash_password(password: str, salt_hex: Optional[str] = None) -> Tuple[str, str]:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with 600,000 iterations.
    Returns (hex_hash, hex_salt).
    """
    if salt_hex is None:
        salt = secrets.token_bytes(SALT_BYTES)
        salt_hex = salt.hex()
    else:
        salt = bytes.fromhex(salt_hex)

    key = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS
    )
    return key.hex(), salt_hex


def verify_password(password: str, stored_hash_hex: str, stored_salt_hex: str) -> bool:
    """
    Verifies a password candidate against stored PBKDF2-HMAC-SHA256 hash using
    constant-time comparison (hmac.compare_digest) to prevent side-channel timing attacks.
    """
    if not password or not stored_hash_hex or not stored_salt_hex:
        return False
    try:
        candidate_hash_hex, _ = hash_password(password, stored_salt_hex)
        return hmac.compare_digest(candidate_hash_hex, stored_hash_hex)
    except Exception:
        return False


def generate_secure_token(nbytes: int = 32) -> str:
    """Generates a cryptographically random, URL-safe session or reset token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """
    Produces a SHA-256 hex digest of a token so raw tokens are never
    persisted in the database or exposed in server logs.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validates enterprise academic password complexity:
    - Minimum 8 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one numerical digit (0-9)
    - At least one special symbol (!@#$%^&*...)
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one numerical digit (0-9)."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/]", password):
        return False, "Password must contain at least one special character (!@#$%^&*...)."
    return True, "Password meets enterprise complexity criteria."


def sanitize_identifier(identifier: str) -> str:
    """Sanitizes username or email input, trimming spaces and removing null bytes."""
    if not identifier:
        return ""
    clean = identifier.strip().replace("\x00", "")
    return clean.lower()
