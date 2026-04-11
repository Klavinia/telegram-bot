from calculator import (
    cost_per_person_per_quarter,
    month_range_label,
)


def build_final_message(user_data: dict) -> str:
    year, first_month, last_month = user_data["quarter_info"]
    period = month_range_label(first_month, last_month, year)
    rate = user_data["eur_rub_rate"]

    netflix_rub = round(
        cost_per_person_per_quarter(user_data["netflix_total"], user_data["netflix_sharers"]) * rate
    )
    spotify_rub = round(
        cost_per_person_per_quarter(user_data["spotify_total"], user_data["spotify_sharers"]) * rate
    )

    netflix_names = " ".join(user_data["netflix_names"])
    spotify_names = " ".join(user_data["spotify_names"])

    return (
        f"Всем привет!\n\n"
        f"Netflix {netflix_names}\n\n"
        f"{period} (3 месяца): {netflix_rub} ₽\n\n"
        f"Spotify {spotify_names}\n\n"
        f"{period} (3 месяца): {spotify_rub} ₽\n\n"
        f"Либо на Тиньк (лучше всего), либо на сбер по номеру: +79217964475 Клавдия Фадеева"
    )
