import os
from dotenv import load_dotenv

load_dotenv()

_bot_token = os.getenv("BOT_TOKEN")
_owner_chat_id = os.getenv("OWNER_CHAT_ID")

if not _bot_token:
    raise ValueError("BOT_TOKEN is not set in .env")
if not _owner_chat_id:
    raise ValueError("OWNER_CHAT_ID is not set in .env")

BOT_TOKEN: str = _bot_token
OWNER_CHAT_ID: int = int(_owner_chat_id)
TRIGGER_HOUR: int = int(os.getenv("TRIGGER_HOUR", "9"))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID")) if os.getenv("GROUP_CHAT_ID") else None


def is_owner(update) -> bool:
    return update.effective_chat.id == OWNER_CHAT_ID
