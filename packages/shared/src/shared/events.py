from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class Venue(StrEnum):
    CURVE = "curve"
    POOL = "pool"


class TokenStatus(StrEnum):
    BONDING = "bonding"
    GRADUATED = "graduated"


@dataclass(frozen=True, slots=True)
class TradeEvent:
    time: datetime
    signature: str
    event_index: int
    slot: int
    mint: str
    wallet: str
    side: Side
    sol_lamports: Decimal
    token_base_units: Decimal
    token_decimals: int
    price_sol: Decimal
    sol_usd: Decimal | None
    venue: Venue


@dataclass(frozen=True, slots=True)
class TokenCreatedEvent:
    time: datetime
    signature: str
    slot: int
    mint: str
    decimals: int
    symbol: str | None
    name: str | None
    creator: str
    curve_address: str


@dataclass(frozen=True, slots=True)
class GraduatedEvent:
    time: datetime
    signature: str
    slot: int
    mint: str
    pool_address: str
