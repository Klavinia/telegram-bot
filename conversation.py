import logging
import re
from datetime import date

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from config import is_owner
from calculator import (
    get_previous_quarter,
    format_math_explanation,
    month_range_label,
    RUSSIAN_MONTHS,
)
from exchange import get_eur_rub_rate
from message_builder import build_final_message
from participants import load_participants
from storage import load_state, save_state, months_summary

logger = logging.getLogger(__name__)

# Conversation states
(
    ASK_SPOTIFY_MONTHLY,
    ASK_SPOTIFY_SAME_MONTHS,
    ASK_SPOTIFY_M1,
    ASK_SPOTIFY_M2,
    ASK_SPOTIFY_M3,
    ASK_NETFLIX_MONTHLY,
    ASK_NETFLIX_SAME_MONTHS,
    ASK_NETFLIX_M1,
    ASK_NETFLIX_M2,
    ASK_NETFLIX_M3,
    ASK_SPOTIFY_SHARERS,
    ASK_NETFLIX_SHARERS,
    CONFIRM_CALCULATIONS,
    ASK_SPOTIFY_NAMES,
    ASK_NETFLIX_NAMES,
    CONFIRM_SAVED_STATE,
) = range(16)

_YES_NO = ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
_REMOVE = ReplyKeyboardRemove()


def _is_yes(text: str) -> bool:
    return text.strip().lower() in {"да", "yes", "y", "ок", "ok", "ага", "д"}


def _parse_float(text: str) -> float:
    return float(text.strip().replace(",", "."))


def _parse_int(text: str) -> int:
    return int(text.strip())


def _parse_names(text: str) -> list[str]:
    parts = re.split(r"[\s,]+", text.strip())
    names = []
    for p in parts:
        if not p:
            continue
        names.append(p if p.startswith("@") else f"@{p}")
    return names


def _quarter_months(user_data: dict) -> tuple[int, int, int]:
    _, first_month, _ = user_data["quarter_info"]
    return first_month, first_month + 1, first_month + 2


# ── Entry point ───────────────────────────────────────────────────────────────

async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_owner(update):
        return ConversationHandler.END

    trigger_date = date.today()
    year, first_month, last_month = get_previous_quarter(trigger_date)
    period = month_range_label(first_month, last_month, year)

    context.user_data["trigger_date"] = trigger_date
    context.user_data["quarter_info"] = (year, first_month, last_month)

    saved = load_state()
    if saved:
        spotify_sum = months_summary(saved["spotify_months"])
        netflix_sum = months_summary(saved["netflix_months"])
        spotify_people = saved["spotify_sharers"]
        netflix_people = saved["netflix_sharers"]
        spotify_names = " ".join(saved["spotify_names"])
        netflix_names = " ".join(saved["netflix_names"])

        await update.message.reply_text(
            f"Привет! Считаем данные за {period}.\n\n"
            f"Данные с прошлого раза:\n"
            f"*Spotify:* {spotify_sum}, {spotify_people} чел.: {spotify_names}\n"
            f"*Netflix:* {netflix_sum}, {netflix_people} чел.: {netflix_names}\n\n"
            f"Всё как прежде?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_YES_NO,
        )
        return CONFIRM_SAVED_STATE

    await update.message.reply_text(
        f"Привет! Считаем данные за {period}.\n\n"
        f"Сколько ты платила за *Spotify* в месяц? (в EUR)\n"
        f"Например: 5.32",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_SPOTIFY_MONTHLY


# ── Confirm saved state ───────────────────────────────────────────────────────

async def confirm_saved_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_yes(update.message.text):
        saved = load_state()
        context.user_data["spotify_months"] = saved["spotify_months"]
        context.user_data["netflix_months"] = saved["netflix_months"]
        context.user_data["spotify_sharers"] = saved["spotify_sharers"]
        context.user_data["netflix_sharers"] = saved["netflix_sharers"]
        context.user_data["spotify_names"] = saved["spotify_names"]
        context.user_data["netflix_names"] = saved["netflix_names"]
        return await _show_calculations(update, context)
    else:
        await update.message.reply_text(
            "Хорошо, введём заново.\n\nСколько ты платила за *Spotify* в месяц? (в EUR)",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_REMOVE,
        )
        return ASK_SPOTIFY_MONTHLY


# ── Calculations helper ───────────────────────────────────────────────────────

async def _show_calculations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fetch rate, compute breakdown, send it. Returns CONFIRM_CALCULATIONS."""
    await update.message.reply_text("Считаю... ⏳", reply_markup=_REMOVE)

    try:
        rate, source_url = await get_eur_rub_rate()
    except Exception as e:
        logger.error(f"Failed to fetch exchange rate: {e}")
        await update.message.reply_text(
            "Не удалось получить курс EUR→RUB. Попробуй /start позже."
        )
        return ConversationHandler.END

    spotify_total = sum(context.user_data["spotify_months"])
    netflix_total = sum(context.user_data["netflix_months"])
    context.user_data["spotify_total"] = spotify_total
    context.user_data["netflix_total"] = netflix_total
    context.user_data["eur_rub_rate"] = rate
    context.user_data["rate_source_url"] = source_url

    spotify_explanation = format_math_explanation(
        "Spotify", spotify_total, context.user_data["spotify_sharers"], rate, source_url,
    )
    netflix_explanation = format_math_explanation(
        "Netflix", netflix_total, context.user_data["netflix_sharers"], rate, source_url,
    )

    await update.message.reply_text(
        f"{spotify_explanation}\n\n{netflix_explanation}\n\nВсё верно?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_YES_NO,
    )
    return CONFIRM_CALCULATIONS


# ── Spotify monthly cost ──────────────────────────────────────────────────────

async def receive_spotify_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = _parse_float(update.message.text)
    except ValueError:
        await update.message.reply_text("Введи число, например 5.32")
        return ASK_SPOTIFY_MONTHLY

    context.user_data["spotify_monthly"] = value
    await update.message.reply_text(
        "Сумма была одинаковой каждый месяц?",
        reply_markup=_YES_NO,
    )
    return ASK_SPOTIFY_SAME_MONTHS


async def receive_spotify_same_months(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    monthly = context.user_data["spotify_monthly"]

    if _is_yes(update.message.text):
        context.user_data["spotify_months"] = [monthly, monthly, monthly]
        await update.message.reply_text(
            "Сколько ты платила за *Netflix* в месяц? (в EUR)",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_REMOVE,
        )
        return ASK_NETFLIX_MONTHLY
    else:
        m1, m2, m3 = _quarter_months(context.user_data)
        await update.message.reply_text(
            f"Хорошо, введём по месяцам.\n\nСколько ты заплатила в *{RUSSIAN_MONTHS[m1]}*? (EUR)",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_REMOVE,
        )
        return ASK_SPOTIFY_M1


async def receive_spotify_m1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = _parse_float(update.message.text)
    except ValueError:
        await update.message.reply_text("Введи число, например 5.32")
        return ASK_SPOTIFY_M1

    context.user_data["spotify_m1"] = value
    _, m2, _ = _quarter_months(context.user_data)
    await update.message.reply_text(
        f"Сколько ты заплатила в *{RUSSIAN_MONTHS[m2]}*? (EUR)",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_SPOTIFY_M2


async def receive_spotify_m2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = _parse_float(update.message.text)
    except ValueError:
        await update.message.reply_text("Введи число, например 5.32")
        return ASK_SPOTIFY_M2

    context.user_data["spotify_m2"] = value
    _, _, m3 = _quarter_months(context.user_data)
    await update.message.reply_text(
        f"Сколько ты заплатила в *{RUSSIAN_MONTHS[m3]}*? (EUR)",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_SPOTIFY_M3


async def receive_spotify_m3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = _parse_float(update.message.text)
    except ValueError:
        await update.message.reply_text("Введи число, например 5.32")
        return ASK_SPOTIFY_M3

    context.user_data["spotify_m3"] = value
    context.user_data["spotify_months"] = [
        context.user_data["spotify_m1"],
        context.user_data["spotify_m2"],
        value,
    ]
    await update.message.reply_text(
        "Сколько ты платила за *Netflix* в месяц? (в EUR)",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_NETFLIX_MONTHLY


# ── Netflix monthly cost ──────────────────────────────────────────────────────

async def receive_netflix_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = _parse_float(update.message.text)
    except ValueError:
        await update.message.reply_text("Введи число, например 9.50")
        return ASK_NETFLIX_MONTHLY

    context.user_data["netflix_monthly"] = value
    await update.message.reply_text(
        "Сумма была одинаковой каждый месяц?",
        reply_markup=_YES_NO,
    )
    return ASK_NETFLIX_SAME_MONTHS


async def receive_netflix_same_months(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    monthly = context.user_data["netflix_monthly"]

    if _is_yes(update.message.text):
        context.user_data["netflix_months"] = [monthly, monthly, monthly]
        await update.message.reply_text(
            "Сколько человек делят *Spotify* с тобой? (не считая тебя)",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_REMOVE,
        )
        return ASK_SPOTIFY_SHARERS
    else:
        m1, m2, m3 = _quarter_months(context.user_data)
        await update.message.reply_text(
            f"Хорошо, введём по месяцам.\n\nСколько ты заплатила в *{RUSSIAN_MONTHS[m1]}*? (EUR)",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_REMOVE,
        )
        return ASK_NETFLIX_M1


async def receive_netflix_m1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = _parse_float(update.message.text)
    except ValueError:
        await update.message.reply_text("Введи число, например 9.50")
        return ASK_NETFLIX_M1

    context.user_data["netflix_m1"] = value
    _, m2, _ = _quarter_months(context.user_data)
    await update.message.reply_text(
        f"Сколько ты заплатила в *{RUSSIAN_MONTHS[m2]}*? (EUR)",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_NETFLIX_M2


async def receive_netflix_m2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = _parse_float(update.message.text)
    except ValueError:
        await update.message.reply_text("Введи число, например 9.50")
        return ASK_NETFLIX_M2

    context.user_data["netflix_m2"] = value
    _, _, m3 = _quarter_months(context.user_data)
    await update.message.reply_text(
        f"Сколько ты заплатила в *{RUSSIAN_MONTHS[m3]}*? (EUR)",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_NETFLIX_M3


async def receive_netflix_m3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = _parse_float(update.message.text)
    except ValueError:
        await update.message.reply_text("Введи число, например 9.50")
        return ASK_NETFLIX_M3

    context.user_data["netflix_m3"] = value
    context.user_data["netflix_months"] = [
        context.user_data["netflix_m1"],
        context.user_data["netflix_m2"],
        value,
    ]
    await update.message.reply_text(
        "Сколько человек делят *Spotify* с тобой? (не считая тебя)",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_SPOTIFY_SHARERS


# ── Sharers ───────────────────────────────────────────────────────────────────

async def receive_spotify_sharers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = _parse_int(update.message.text)
        if value < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введи целое число больше 0, например 2")
        return ASK_SPOTIFY_SHARERS

    context.user_data["spotify_sharers"] = value
    await update.message.reply_text(
        "Сколько человек делят *Netflix* с тобой? (не считая тебя)",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_NETFLIX_SHARERS


async def receive_netflix_sharers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = _parse_int(update.message.text)
        if value < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введи целое число больше 0, например 3")
        return ASK_NETFLIX_SHARERS

    context.user_data["netflix_sharers"] = value
    return await _show_calculations(update, context)


# ── Confirm calculations ──────────────────────────────────────────────────────

async def confirm_calculations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_yes(update.message.text):
        await _ask_names(update, context, service="Spotify")
        return ASK_SPOTIFY_NAMES
    else:
        quarter_info = context.user_data.get("quarter_info")
        trigger_date = context.user_data.get("trigger_date")
        context.user_data.clear()
        context.user_data["quarter_info"] = quarter_info
        context.user_data["trigger_date"] = trigger_date

        await update.message.reply_text(
            "Хорошо, начнём заново.\n\nСколько ты платила за *Spotify* в месяц? (в EUR)",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_REMOVE,
        )
        return ASK_SPOTIFY_MONTHLY


# ── Name collection ───────────────────────────────────────────────────────────

async def _ask_names(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    service: str,
) -> None:
    key = f"{service.lower()}_names"
    saved_names = context.user_data.get(key)
    known = saved_names or load_participants()

    if known:
        suggestion = " ".join(known)
        source = "прошлый раз" if saved_names else "из чата"
        await update.message.reply_text(
            f"Люди ({source}): {suggestion}\n\n"
            f"Все они делят *{service}*?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_YES_NO,
        )
    else:
        await update.message.reply_text(
            f"Укажи @никнеймы людей, делящих *{service}* с тобой.\n"
            f"Можно через пробел или запятую, например: @alice @bob",
            parse_mode=ParseMode.MARKDOWN,
        )


async def receive_spotify_names(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    saved = context.user_data.get("spotify_names")
    known = saved or load_participants()

    if _is_yes(update.message.text) and known:
        names = known
    else:
        names = _parse_names(update.message.text)
        if not names:
            await update.message.reply_text("Введи хотя бы один никнейм, например @alice")
            return ASK_SPOTIFY_NAMES

    context.user_data["spotify_names"] = names
    await _ask_names(update, context, service="Netflix")
    return ASK_NETFLIX_NAMES


async def receive_netflix_names(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    saved = context.user_data.get("netflix_names")
    known = saved or load_participants()

    if _is_yes(update.message.text) and known:
        names = known
    else:
        names = _parse_names(update.message.text)
        if not names:
            await update.message.reply_text("Введи хотя бы один никнейм, например @charlie")
            return ASK_NETFLIX_NAMES

    context.user_data["netflix_names"] = names

    final_message = build_final_message(context.user_data)
    save_state(context.user_data)

    await update.message.reply_text(
        "Готово! Вот итоговое сообщение — скопируй и отправь:",
        reply_markup=_REMOVE,
    )
    await update.message.reply_text(final_message)

    return ConversationHandler.END


# ── Cancel ────────────────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_owner(update):
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text(
        "Отменено. Напиши /start чтобы начать заново.",
        reply_markup=_REMOVE,
    )
    return ConversationHandler.END


# ── ConversationHandler ───────────────────────────────────────────────────────

_text = filters.TEXT & ~filters.COMMAND

conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("start", start_conversation),
        CommandHandler("testrun", start_conversation),
    ],
    states={
        CONFIRM_SAVED_STATE:     [MessageHandler(_text, confirm_saved_state)],
        ASK_SPOTIFY_MONTHLY:     [MessageHandler(_text, receive_spotify_monthly)],
        ASK_SPOTIFY_SAME_MONTHS: [MessageHandler(_text, receive_spotify_same_months)],
        ASK_SPOTIFY_M1:          [MessageHandler(_text, receive_spotify_m1)],
        ASK_SPOTIFY_M2:          [MessageHandler(_text, receive_spotify_m2)],
        ASK_SPOTIFY_M3:          [MessageHandler(_text, receive_spotify_m3)],
        ASK_NETFLIX_MONTHLY:     [MessageHandler(_text, receive_netflix_monthly)],
        ASK_NETFLIX_SAME_MONTHS: [MessageHandler(_text, receive_netflix_same_months)],
        ASK_NETFLIX_M1:          [MessageHandler(_text, receive_netflix_m1)],
        ASK_NETFLIX_M2:          [MessageHandler(_text, receive_netflix_m2)],
        ASK_NETFLIX_M3:          [MessageHandler(_text, receive_netflix_m3)],
        ASK_SPOTIFY_SHARERS:     [MessageHandler(_text, receive_spotify_sharers)],
        ASK_NETFLIX_SHARERS:     [MessageHandler(_text, receive_netflix_sharers)],
        CONFIRM_CALCULATIONS:    [MessageHandler(_text, confirm_calculations)],
        ASK_SPOTIFY_NAMES:       [MessageHandler(_text, receive_spotify_names)],
        ASK_NETFLIX_NAMES:       [MessageHandler(_text, receive_netflix_names)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True,
)
