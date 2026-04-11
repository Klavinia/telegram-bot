import json
import os

_FILE = os.path.join(os.path.dirname(__file__), "participants.json")


def load_participants() -> list[str]:
    """Returns list of @usernames seen in the group chat."""
    if not os.path.exists(_FILE):
        return []
    with open(_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_participant(username: str) -> None:
    """Adds a @username to the file if not already present."""
    current = load_participants()
    if username not in current:
        current.append(username)
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False)
