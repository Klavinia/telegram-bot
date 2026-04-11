import logging
import aiohttp

logger = logging.getLogger(__name__)

_TBANK_URL = "https://www.tinkoff.ru/api/v1/currency_rates"
_TBANK_PAGE_URL = "https://www.tbank.ru/about/exchange/"
_FALLBACK_URL = "https://api.exchangerate-api.com/v4/latest/EUR"
_FALLBACK_PAGE_URL = "https://www.exchangerate-api.com"
_TIMEOUT = aiohttp.ClientTimeout(total=10)

# ISO 4217 numeric codes
_EUR_CODE = 978
_RUB_CODE = 643
_PREFERRED_CATEGORIES = ("PrepaidCardsOperations", "C2CTransfers")


async def _fetch_from_tbank(session: aiohttp.ClientSession) -> float:
    async with session.get(_TBANK_URL, timeout=_TIMEOUT) as resp:
        resp.raise_for_status()
        data = await resp.json()

    for rate in data.get("rates", []):
        if (
            rate.get("category") in _PREFERRED_CATEGORIES
            and rate.get("fromCurrency", {}).get("code") == _EUR_CODE
            and rate.get("toCurrency", {}).get("code") == _RUB_CODE
        ):
            buy = rate["buy"]
            sell = rate["sell"]
            return (buy + sell) / 2

    raise ValueError("EUR/RUB rate not found in tbank response")


async def _fetch_from_fallback(session: aiohttp.ClientSession) -> float:
    async with session.get(_FALLBACK_URL, timeout=_TIMEOUT) as resp:
        resp.raise_for_status()
        data = await resp.json()
    return float(data["rates"]["RUB"])


async def get_eur_rub_rate() -> tuple[float, str]:
    """
    Fetch EUR→RUB mid-market rate.
    Returns (rate, source_url) — tbank first, exchangerate-api as fallback.
    """
    async with aiohttp.ClientSession() as session:
        try:
            rate = await _fetch_from_tbank(session)
            logger.info(f"EUR/RUB rate from tbank: {rate:.2f}")
            return rate, _TBANK_PAGE_URL
        except Exception as e:
            logger.warning(f"tbank rate fetch failed ({e}), trying fallback")
            rate = await _fetch_from_fallback(session)
            logger.info(f"EUR/RUB rate from fallback: {rate:.2f}")
            return rate, _FALLBACK_PAGE_URL
