import json
import os

_FILE = os.path.join(os.path.dirname(__file__), "bot_state.json")


def load_state():
    """Returns saved state dict, or None if no state has been saved yet."""
    if not os.path.exists(_FILE):
        return None
    with open(_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(user_data: dict) -> None:
    """Persists the key fields from user_data to disk after a successful run."""
    state = {
        "spotify_months":   user_data["spotify_months"],
        "netflix_months":   user_data["netflix_months"],
        "spotify_sharers":  user_data["spotify_sharers"],
        "netflix_sharers":  user_data["netflix_sharers"],
        "spotify_names":    user_data["spotify_names"],
        "netflix_names":    user_data["netflix_names"],
    }
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def months_summary(months: list) -> str:
    """Returns '5.32 EUR/мес' if all months equal, or '5.32 / 6.00 / 5.50 EUR' if different."""
    if len(set(months)) == 1:
        return f"{months[0]:.2f} EUR/мес"
    return " / ".join(f"{m:.2f}" for m in months) + " EUR"
