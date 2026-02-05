# core/strategy_store.py
# Per-user strategy storage for VectorAlgoAI (file-based JSON)

import os
import json
from datetime import datetime
from typing import Dict, List, Tuple

DATA_DIR = "data"
STRATEGIES_FILE = os.path.join(DATA_DIR, "strategies.json")


def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(STRATEGIES_FILE):
        with open(STRATEGIES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load_all() -> Dict[str, List[dict]]:
    _ensure_file()
    try:
        with open(STRATEGIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
    except Exception:
        return {}


def _save_all(data: Dict[str, List[dict]]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STRATEGIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_user_strategies(email: str) -> List[dict]:
    """
    Return a list of strategies for the given user email.
    Each strategy dict: { "name", "yaml", "created_at", "updated_at" }
    """
    email = (email or "").strip().lower()
    if not email:
        return []
    data = _load_all()
    return data.get(email, [])


def save_user_strategy(email: str, name: str, yaml_text: str) -> Tuple[bool, str]:
    """
    Save or update a strategy for a given user.
    Returns (success, message).
    """
    email = (email or "").strip().lower()
    name = (name or "").strip()

    if not email:
        return False, "User not specified."
    if not name:
        return False, "Strategy name cannot be empty."
    if not yaml_text:
        return False, "Strategy YAML cannot be empty."

    data = _load_all()
    user_strats = data.get(email, [])

    now_str = datetime.utcnow().isoformat() + "Z"

    # Check if strategy with same name exists -> update
    updated = False
    for strat in user_strats:
        if strat.get("name") == name:
            strat["yaml"] = yaml_text
            strat["updated_at"] = now_str
            updated = True
            break

    if not updated:
        user_strats.append(
            {
                "name": name,
                "yaml": yaml_text,
                "created_at": now_str,
                "updated_at": now_str,
            }
        )

    data[email] = user_strats
    _save_all(data)

    if updated:
        return True, f"Strategy '{name}' updated for {email}."
    else:
        return True, f"Strategy '{name}' saved for {email}."


def delete_user_strategy(email: str, name: str) -> Tuple[bool, str]:
    """
    Delete a strategy by name for the given user.
    Returns (success, message).
    """
    email = (email or "").strip().lower()
    name = (name or "").strip()

    if not email:
        return False, "User not specified."
    if not name:
        return False, "Strategy name cannot be empty."

    data = _load_all()
    user_strats = data.get(email, [])

    new_list = [s for s in user_strats if s.get("name") != name]
    if len(new_list) == len(user_strats):
        return False, f"No strategy named '{name}' found."

    data[email] = new_list
    _save_all(data)
    return True, f"Strategy '{name}' deleted."
