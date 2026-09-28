from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from alerts.state import VolumeSpikeState

log = logging.getLogger(__name__)

_LAMPORTS_PER_SOL = 1_000_000_000


@dataclass(frozen=True)
class Rule:
    id: int
    type: str
    params: dict[str, Any]
    cooldown_seconds: int


def evaluate(rule: Rule, event: dict[str, Any], spike_state: VolumeSpikeState) -> str | None:
    if rule.type == "large_trade":
        return _large_trade(event, rule.params)
    if rule.type == "wallet_trade":
        return _wallet_trade(event, rule.params)
    if rule.type == "volume_spike":
        return _volume_spike(event, rule.params, spike_state)
    log.warning("unknown rule type: %s (id=%d)", rule.type, rule.id)
    return None


def _large_trade(event: dict[str, Any], params: dict[str, Any]) -> str | None:
    min_sol = float(params.get("min_sol", 0))
    sol_lamports = int(event["sol_lamports"])
    sol = sol_lamports / _LAMPORTS_PER_SOL
    if sol < min_sol:
        return None
    return f"{event['side']} of {sol:.3f} SOL on {event['mint']} (>= {min_sol} SOL threshold)"


def _wallet_trade(event: dict[str, Any], params: dict[str, Any]) -> str | None:
    wallets = set(params.get("wallets", []))
    if event["wallet"] not in wallets:
        return None
    sol = int(event["sol_lamports"]) / _LAMPORTS_PER_SOL
    return f"tracked wallet {event['wallet']} {event['side']} {sol:.3f} SOL on {event['mint']}"


def _volume_spike(
    event: dict[str, Any], params: dict[str, Any], spike_state: VolumeSpikeState
) -> str | None:
    window = int(params.get("window_seconds", 60))
    multiplier = float(params.get("min_multiplier", 3.0))
    min_baseline_sol = float(params.get("min_baseline_sol", 1.0))

    r = spike_state.windows(event["mint"], time.time(), window)
    if r is None:
        return None
    recent_lamports, baseline_lamports = r
    baseline_sol = baseline_lamports / _LAMPORTS_PER_SOL
    if baseline_sol < min_baseline_sol:
        return None
    if recent_lamports < baseline_lamports * multiplier:
        return None
    recent_sol = recent_lamports / _LAMPORTS_PER_SOL
    return (
        f"volume spike on {event['mint']}: "
        f"{recent_sol:.2f} SOL in last {window}s vs {baseline_sol:.2f} SOL baseline "
        f"({recent_sol / baseline_sol:.1f}x)"
    )
