"""Core utility functions used across the application."""


def validate_email(email: str) -> bool:
    """Check if an email address is valid."""
    return "@" in email and "." in email


def hash_password(password: str) -> str:
    """Hash a password for secure storage."""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


def format_response(data: dict, status: str = "success") -> dict:
    """Wrap data in a standard API response envelope."""
    return {"status": status, "data": data}
