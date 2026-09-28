from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from decoder.pumpfun import parse_pumpfun_swap, parse_swap
from shared.events import Side, Venue

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "tests" / "pumpfun"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_parse_buy() -> None:
    event = parse_pumpfun_swap(_load("buy_1.json"))
    assert event is not None
    assert event.side == Side.BUY
    assert event.venue == Venue.CURVE
    assert event.wallet == "138YFNB7L6K1nAQCgWVCsapFtW838HoH2ufpack43t1h"
    assert event.mint == "78Cfe4mD2iDZvgwHaR3yi5X3UdMc3HyQfeGTcc9Hpump"
    assert event.slot == 451162469
    assert event.signature == (
        "3MfLHDQvtouKfYfiyUJGhoSnJu2TgirCn8KDKb3XhUJvmoZAGM8XgWScsovXaugwEWq2VujijC4FD1V4vFtUyEyt"
    )
    assert event.sol_lamports == Decimal("2526840")
    assert event.token_base_units == Decimal("15543906671")
    assert event.token_decimals == 6
    expected_price = (
        (Decimal("2526840") / Decimal(10**9)) / (Decimal("15543906671") / Decimal(10**6))
    ).quantize(Decimal(10) ** -20)
    assert event.price_sol == expected_price


def test_parse_sell() -> None:
    event = parse_pumpfun_swap(_load("sell_1.json"))
    assert event is not None
    assert event.side == Side.SELL
    assert event.venue == Venue.CURVE
    assert event.wallet == "6nFs5b4tnEy6EyPBEZyoNzkzpvJ5phrBanZcN44DH1qk"
    assert event.mint == "FkoGiwCCynKkvG2JYNbGGB7i2TifEjVVycZ6i5wdmiRU"
    assert event.slot == 451162468
    assert event.sol_lamports == Decimal("653617770")
    assert event.token_base_units == Decimal("19022024084180")
    assert event.token_decimals == 6


def test_rejects_jupiter_swap() -> None:
    assert parse_pumpfun_swap(_load("jupiter_swap.json")) is None


def test_rejects_pumpfun_unknown_type() -> None:
    assert parse_pumpfun_swap(_load("pumpfun_unknown.json")) is None


def test_rejects_empty_payload() -> None:
    assert parse_pumpfun_swap({}) is None


def test_parse_swap_jupiter_post_grad() -> None:
    """A graduated token traded via Jupiter should parse when the strict
    source filter is dropped. Venue flips to POOL. WSOL is correctly
    skipped when picking the trader's target token transfer."""
    event = parse_swap(_load("jupiter_swap.json"))
    assert event is not None
    assert event.side == Side.BUY
    assert event.venue == Venue.POOL
    assert event.mint == "AUdSCZzU2Z84LPtjABi6pMWp1Qh5FFFm4fiHXydja4N3"
    assert event.wallet == "8FVa6HichsF8wdRsNNfYuookw81MEPyB7CsPvNrBmyKc"
    assert event.sol_lamports == Decimal("2166778759")
    assert event.token_base_units == Decimal("35333491543883")
    assert event.token_decimals == 6


def test_parse_swap_still_rejects_non_swap() -> None:
    assert parse_swap(_load("pumpfun_unknown.json")) is None
    assert parse_swap({}) is None
