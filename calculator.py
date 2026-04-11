from datetime import date

RUSSIAN_MONTHS = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

# Maps the trigger month → (q_year_offset, first_month, last_month)
# year_offset: 0 = current year, -1 = previous year
_QUARTER_MAP = {
    1:  (-1, 10, 12),  # Jan 1 → Q4 of previous year (Oct–Dec)
    4:  (0,   1,  3),  # Apr 1 → Q1 (Jan–Mar)
    7:  (0,   4,  6),  # Jul 1 → Q2 (Apr–Jun)
    10: (0,   7,  9),  # Oct 1 → Q3 (Jul–Sep)
}


def get_previous_quarter(trigger_date: date) -> tuple:
    """
    Returns (year, first_month, last_month) for the quarter prior to trigger_date.
    trigger_date should be the 1st of Jan/Apr/Jul/Oct.
    """
    year_offset, first_month, last_month = _QUARTER_MAP[trigger_date.month]
    year = trigger_date.year + year_offset
    return year, first_month, last_month


def cost_per_person_per_quarter(total_paid: float, num_sharers: int) -> float:
    """total_paid split evenly among (num_sharers + 1) people for the full quarter."""
    return total_paid / (num_sharers + 1)


def cost_per_person_per_month(total_paid: float, num_sharers: int) -> float:
    """Monthly share per person."""
    return total_paid / 3 / (num_sharers + 1)


def format_math_explanation(
    service: str,
    total_paid: float,
    num_sharers: int,
    rate: float,
    source_url: str,
) -> str:
    total_people = num_sharers + 1
    per_quarter = cost_per_person_per_quarter(total_paid, num_sharers)
    per_month = cost_per_person_per_month(total_paid, num_sharers)
    per_quarter_rub = per_quarter * rate

    lines = [
        f"*{service}:*",
        f"  Оплачено за квартал: {total_paid:.2f} EUR",
        f"  Всего человек: {total_people} (ты + {num_sharers})",
        f"  На человека за квартал: {total_paid:.2f} ÷ {total_people} = {per_quarter:.2f} EUR",
        f"  На человека в месяц: {per_quarter:.2f} ÷ 3 = {per_month:.2f} EUR",
        f"  Курс EUR→RUB: {rate:.2f} ([источник]({source_url}))",
        f"  Итого: {per_quarter:.2f} × {rate:.2f} = *{round(per_quarter_rub)} ₽*/человек/квартал",
    ]
    return "\n".join(lines)


def month_range_label(first_month: int, last_month: int, year: int) -> str:
    return f"{RUSSIAN_MONTHS[first_month]} - {RUSSIAN_MONTHS[last_month]} {year}"
