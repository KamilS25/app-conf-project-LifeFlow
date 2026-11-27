from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal, DecimalException
from http.client import HTTPException
from threading import Lock
from time import monotonic
from typing import Literal
from urllib.request import HTTPRedirectHandler, build_opener
from xml.etree import ElementTree

from pydantic import BaseModel

from app.models import Currency

DAILY_RATES_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
MIRROR_RATES_URL = "https://www.cbr-xml-daily.ru/daily_utf8.xml"
FOREIGN_CURRENCIES = (Currency.USD, Currency.EUR, Currency.CNY)
MAX_FEED_BYTES = 128 * 1024


class RatesUnavailable(Exception):
    pass


class RateSnapshot(BaseModel):
    rate_date: date
    rub_per_unit: dict[Currency, Decimal]
    stale: bool = False
    provider: Literal["cbr", "mirror"] = "cbr"


def parse_daily_rates(payload: bytes) -> RateSnapshot:
    if (
        len(payload) > MAX_FEED_BYTES
        or b"<!DOCTYPE" in payload.upper()
        or b"\x00" in payload
    ):
        raise ValueError("Unexpected currency feed")
    root = ElementTree.fromstring(payload)
    rate_date = datetime.strptime(root.attrib["Date"], "%d.%m.%Y").date()
    rates = {}
    for currency in FOREIGN_CURRENCIES:
        node = root.find(f"./Valute[CharCode='{currency.value}']")
        if node is None:
            raise ValueError("Currency missing from feed")
        value = Decimal(node.findtext("Value", "").replace(",", "."))
        units = int(node.findtext("Nominal", "0"))
        if units <= 0 or not value.is_finite() or value <= 0:
            raise ValueError("Invalid currency rate")
        rates[currency] = value / units
    return RateSnapshot(rate_date=rate_date, rub_per_unit=rates)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl) -> None:
        return None


def fetch_daily_rates() -> RateSnapshot:
    opener = build_opener(NoRedirect())
    last_error = None
    for provider, url in (("cbr", DAILY_RATES_URL), ("mirror", MIRROR_RATES_URL)):
        try:
            with opener.open(url, timeout=3) as response:
                snapshot = parse_daily_rates(response.read(MAX_FEED_BYTES + 1))
                return snapshot.model_copy(update={"provider": provider})
        except (
            OSError,
            ValueError,
            LookupError,
            HTTPException,
            DecimalException,
            ElementTree.ParseError,
        ) as error:
            last_error = error
    raise RatesUnavailable from last_error


class RateFeed:
    def __init__(self, load: Callable[[], RateSnapshot] = fetch_daily_rates) -> None:
        self.load = load
        self.lock = Lock()
        self.snapshot: RateSnapshot | None = None
        self.retry_at = 0.0

    def read(self) -> RateSnapshot:
        with self.lock:
            if monotonic() >= self.retry_at:
                try:
                    self.snapshot = self.load()
                    self.retry_at = monotonic() + 3600
                except RatesUnavailable:
                    self.retry_at = monotonic() + 60
                    if self.snapshot is not None:
                        self.snapshot = self.snapshot.model_copy(update={"stale": True})

            if self.snapshot is None:
                raise RatesUnavailable
            return self.snapshot
