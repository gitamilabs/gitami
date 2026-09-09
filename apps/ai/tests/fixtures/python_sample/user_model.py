"""User model and authentication logic."""
from utils import validate_email, hash_password


class User:
    """Represents a registered user in the system."""

    def __init__(self, email: str, password: str):
        self.email = email
        self.password_hash = hash_password(password)

    def check_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        return self.password_hash == hash_password(password)


def create_user(email: str, password: str) -> User:
    """Validate input and create a new User instance."""
    if not validate_email(email):
        raise ValueError("Invalid email address")
    return User(email, password)
