# core/auth.py
# Simple local auth for VectorAlgoAI (file-based, hashed passwords)

import os
import json
import hashlib
from typing import Tuple, Dict

USERS_DIR = "data"
USERS_FILE = os.path.join(USERS_DIR, "users.json")


def _ensure_users_file():
    os.makedirs(USERS_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load_users() -> Dict[str, dict]:
    _ensure_users_file()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
    except Exception:
        return {}


def _save_users(users: Dict[str, dict]) -> None:
    os.makedirs(USERS_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def register_user(email: str, password1: str, password2: str) -> Tuple[bool, str]:
    """
    Register a new user.
    Returns (success: bool, message: str).
    """
    email = (email or "").strip().lower()

    if not email or "@" not in email:
        return False, "Please enter a valid email."

    if not password1 or not password2:
        return False, "Password fields cannot be empty."

    if password1 != password2:
        return False, "Passwords do not match."

    if len(password1) < 6:
        return False, "Password must be at least 6 characters long."

    users = _load_users()
    if email in users:
        return False, "An account with this email already exists."

    users[email] = {
        "password_hash": _hash_password(password1),
        "role": "user",
    }
    _save_users(users)
    return True, "Account created successfully. You can now log in."


def authenticate_user(email: str, password: str) -> Tuple[bool, str]:
    """
    Authenticate user by email & password.
    Returns (success: bool, message: str).
    """
    email = (email or "").strip().lower()
    if not email or not password:
        return False, "Please enter both email and password."

    users = _load_users()
    if email not in users:
        return False, "No account found with this email."

    stored_hash = users[email].get("password_hash")
    if stored_hash != _hash_password(password):
        return False, "Incorrect password."

    return True, "Login successful."
