import logging
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application, ContextTypes

from config import OWNER_CHAT_ID, TRIGGER_HOUR

logger = logging.getLogger(__name__)

_MOSCOW_TZ = ZoneInfo("Europe/Moscow")


async def _quarterly_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a reminder to the owner to start the quarterly data collection."""
    logger.info("Sending quarterly reminder to owner")
    await context.bot.send_message(
        chat_id=OWNER_CHAT_ID,
        text=(
            "Привет! Начался новый квартал 📅\n\n"
            "Пора собрать деньги за подписки. Напиши /start чтобы начать."
        ),
    )


def setup_scheduler(application: Application) -> None:
    """Register the quarterly cron job. Call after building the Application."""
    application.job_queue.run_custom(
        callback=_quarterly_reminder,
        job_kwargs={
            "trigger": CronTrigger(
                month="1,4,7,10",
                day=1,
                hour=TRIGGER_HOUR,
                minute=0,
                second=0,
                timezone=_MOSCOW_TZ,
            )
        },
    )
    logger.info(
        f"Quarterly reminder scheduled for 1st of Jan/Apr/Jul/Oct at {TRIGGER_HOUR}:00 Moscow time"
    )
