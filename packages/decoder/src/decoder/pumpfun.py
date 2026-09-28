from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from shared.events import Side, TradeEvent, Venue

_LAMPORTS_PER_SOL = Decimal(10**9)
_PRICE_QUANT = Decimal(10) ** -20  # matches trades.price_sol NUMERIC(40, 20)
_WSOL_MINT = "So11111111111111111111111111111111111111112"


def parse_pumpfun_swap(payload: dict[str, Any]) -> TradeEvent | None:
    """Strict wrapper for the pre-graduation pump.fun pipeline.
    Accepts only source == 'PUMP_FUN'; use parse_swap for post-graduation.
    """
    return parse_swap(payload, allowed_sources={"PUMP_FUN"})


def parse_swap(
    payload: dict[str, Any],
    allowed_sources: set[str] | None = None,
) -> TradeEvent | None:
    """Parse a Helius-parsed SWAP into a normalized TradeEvent.

    Works for pump.fun bonding swaps and post-graduation swaps routed
    through aggregators (Jupiter, PumpSwap direct, Raydium, ...).
    Skips WSOL when identifying the trader's target token so aggregator
    swaps that wrap SOL as an intermediate do not confuse the direction.

    allowed_sources: if given, only accept those Helius 'source' values;
    otherwise accept any.
    """
    if payload.get("type") != "SWAP":
        return None
    if payload.get("transactionError") is not None:
        return None
    source = payload.get("source")
    if allowed_sources is not None and source not in allowed_sources:
        return None

    signature = payload.get("signature")
    slot = payload.get("slot")
    timestamp = payload.get("timestamp")
    fee_payer = payload.get("feePayer")
    if signature is None or slot is None or timestamp is None or not fee_payer:
        return None

    tt = _pick_transfer_involving(
        payload.get("tokenTransfers") or [],
        fee_payer,
        exclude_mints={_WSOL_MINT},
    )
    if tt is None:
        return None
    mint = tt.get("mint")
    if not mint:
        return None
    side = Side.BUY if tt.get("toUserAccount") == fee_payer else Side.SELL

    account_data = payload.get("accountData") or []
    sol_net = _fee_payer_sol_change(account_data, fee_payer)
    if sol_net is None:
        return None
    sol_lamports = abs(Decimal(sol_net))
    if sol_lamports == 0:
        return None

    token_change = _fee_payer_token_change(account_data, fee_payer, mint)
    if token_change is None:
        return None
    token_base_units, decimals = token_change
    token_base_units = abs(token_base_units)
    if token_base_units == 0:
        return None

    sol_amount = sol_lamports / _LAMPORTS_PER_SOL
    token_amount = token_base_units / Decimal(10**decimals)
    price_sol = (sol_amount / token_amount).quantize(_PRICE_QUANT)

    venue = Venue.CURVE if source == "PUMP_FUN" else Venue.POOL

    return TradeEvent(
        time=datetime.fromtimestamp(int(timestamp), tz=UTC),
        signature=signature,
        event_index=0,
        slot=int(slot),
        mint=mint,
        wallet=fee_payer,
        side=side,
        sol_lamports=sol_lamports,
        token_base_units=token_base_units,
        token_decimals=decimals,
        price_sol=price_sol,
        sol_usd=None,
        venue=venue,
    )


def _pick_transfer_involving(
    transfers: list[dict[str, Any]],
    wallet: str,
    exclude_mints: set[str] | None = None,
) -> dict[str, Any] | None:
    for t in transfers:
        if exclude_mints and t.get("mint") in exclude_mints:
            continue
        if t.get("fromUserAccount") == wallet or t.get("toUserAccount") == wallet:
            return t
    return None


def _fee_payer_sol_change(account_data: list[dict[str, Any]], wallet: str) -> int | None:
    for ad in account_data:
        if ad.get("account") == wallet:
            change = ad.get("nativeBalanceChange")
            if isinstance(change, int):
                return change
    return None


def _fee_payer_token_change(
    account_data: list[dict[str, Any]],
    wallet: str,
    mint: str,
) -> tuple[Decimal, int] | None:
    for ad in account_data:
        for tbc in ad.get("tokenBalanceChanges") or []:
            if tbc.get("userAccount") == wallet and tbc.get("mint") == mint:
                raw = tbc.get("rawTokenAmount") or {}
                amount_str = raw.get("tokenAmount")
                decimals = raw.get("decimals")
                if amount_str is None or decimals is None:
                    return None
                try:
                    return Decimal(str(amount_str)), int(decimals)
                except (ArithmeticError, ValueError):
                    return None
    return None
