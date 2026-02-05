import os
import json
import hashlib
from typing import Tuple

USERS_DIR = "data"
USERS_FILE = os.path.join(USERS_DIR, "users.json")

def _ensure_users_file():
    os.makedirs(USERS_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def _load_users():
    _ensure_users_file()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(email: str, password1: str, password2: str) -> Tuple[bool, str]:
    email = email.strip().lower()
    if not email or "@" not in email:
        return False, "Invalid email."
    if password1 != password2:
        return False, "Passwords do not match."
    if len(password1) < 6:
        return False, "Password too short (min 6 chars)."
    
    users = _load_users()
    if email in users:
        return False, "Email already registered."
    
    users[email] = {
        "password_hash": _hash_password(password1),
        "created": str(pd.Timestamp.now())
    }
    _save_users(users)
    return True, "Account created. You can log in now."

def authenticate_user(email: str, password: str) -> Tuple[bool, str]:
    email = email.strip().lower()
    users = _load_users()
    if email not in users:
        return False, "No account found."
    if users[email]["password_hash"] != _hash_password(password):
        return False, "Incorrect password."
    return True, "Login successful."
