import logging

from telegram import Update
from telegram.ext import Application, MessageHandler, filters

from config import BOT_TOKEN, GROUP_CHAT_ID
from conversation import conv_handler
from scheduler import setup_scheduler
from participants import save_participant

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def track_group_member(update: Update, _) -> None:
    """Silently records the username of anyone who writes in the group chat."""
    user = update.effective_user
    if user and user.username:
        save_participant(f"@{user.username}")


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(conv_handler)

    if GROUP_CHAT_ID:
        application.add_handler(
            MessageHandler(filters.Chat(GROUP_CHAT_ID) & filters.TEXT, track_group_member)
        )
        logger.info(f"Tracking group chat {GROUP_CHAT_ID} for participant names")

    setup_scheduler(application)

    logger.info("Bot started. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
