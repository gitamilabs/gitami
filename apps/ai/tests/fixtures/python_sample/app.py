"""Application entry point — ties all modules together."""
from user_model import create_user, User
from utils import format_response


def register_handler(email: str, password: str) -> dict:
    """Handle user registration requests."""
    user = create_user(email, password)
    return format_response({"email": user.email})


def login_handler(email: str, password: str, existing_user: User) -> dict:
    """Handle user login requests."""
    if existing_user.check_password(password):
        return format_response({"authenticated": True})
    return format_response({"authenticated": False}, status="error")


def main():
    """Start the application."""
    result = register_handler("test@example.com", "secret123")
    print(result)
