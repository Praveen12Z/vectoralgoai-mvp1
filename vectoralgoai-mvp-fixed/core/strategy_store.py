import os
import json
from datetime import datetime
from typing import List, Tuple

DATA_DIR = "data"
STRATEGIES_FILE = os.path.join(DATA_DIR, "strategies.json")

def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(STRATEGIES_FILE):
        with open(STRATEGIES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def _load_all() -> dict:
    _ensure_file()
    try:
        with open(STRATEGIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except:
        return {}

def _save_all(data: dict):
    with open(STRATEGIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_user_strategies(email: str) -> List[dict]:
    email = (email or "").strip().lower()
    if not email:
        return []
    all_data = _load_all()
    return all_data.get(email, [])

def save_user_strategy(email: str, name: str, yaml_text: str) -> Tuple[bool, str]:
    email = (email or "").strip().lower()
    name = (name or "").strip()
    if not email or not name or not yaml_text:
        return False, "Missing required fields"

    all_data = _load_all()
    user_strats = all_data.get(email, [])

    now = datetime.utcnow().isoformat() + "Z"
    found = False
    for s in user_strats:
        if s.get("name") == name:
            s["yaml"] = yaml_text
            s["updated_at"] = now
            found = True
            break

    if not found:
        user_strats.append({
            "name": name,
            "yaml": yaml_text,
            "created_at": now,
            "updated_at": now
        })

    all_data[email] = user_strats
    _save_all(all_data)
    return True, f"Strategy '{name}' {'updated' if found else 'saved'}."

def delete_user_strategy(email: str, name: str) -> Tuple[bool, str]:
    email = (email or "").strip().lower()
    name = (name or "").strip()
    if not email or not name:
        return False, "Missing fields"

    all_data = _load_all()
    user_strats = all_data.get(email, [])
    new_list = [s for s in user_strats if s.get("name") != name]

    if len(new_list) == len(user_strats):
        return False, f"No strategy named '{name}' found."

    all_data[email] = new_list
    _save_all(all_data)
    return True, f"Strategy '{name}' deleted."