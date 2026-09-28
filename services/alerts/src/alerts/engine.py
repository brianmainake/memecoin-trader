from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

import asyncpg

from alerts.delivery import Delivery
from alerts.rules import Rule, evaluate
from alerts.state import VolumeSpikeState

log = logging.getLogger(__name__)


class AlertEngine:
    def __init__(
        self,
        pool: asyncpg.Pool,
        listener_conn: asyncpg.Connection,
        delivery: Delivery,
        rules_refresh_interval: float = 30.0,
        state_retention_seconds: int = 600,
    ):
        self._pool = pool
        self._listener = listener_conn
        self._delivery = delivery
        self._rules_refresh = rules_refresh_interval
        self._rules: list[Rule] = []
        self._cooldowns: dict[tuple[int, str], datetime] = {}
        self._spike_state = VolumeSpikeState(retention_seconds=state_retention_seconds)
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)

    async def run(self) -> None:
        await self._load_rules()
        await self._load_cooldowns()
        log.info(
            "loaded %d rules, %d cooldown entries",
            len(self._rules), len(self._cooldowns),
        )
        if not self._rules:
            log.warning(
                "no active rules — insert into alert_rules to fire alerts, e.g. "
                "\"INSERT INTO alert_rules (type, params) VALUES "
                "('large_trade', '{\"min_sol\": 1}');\""
            )

        def _cb(_conn: Any, _pid: int, _ch: str, payload: str) -> None:
            try:
                event = json.loads(payload)
                self._queue.put_nowait(event)
            except (json.JSONDecodeError, asyncio.QueueFull) as exc:
                log.warning("dropped event (%s): %s", type(exc).__name__, exc)

        await self._listener.add_listener("trade_events", _cb)
        refresh_task = asyncio.create_task(self._refresh_loop())
        try:
            while True:
                event = await self._queue.get()
                try:
                    await self._process(event)
                except Exception as exc:
                    log.warning("process failed (%s: %s)", type(exc).__name__, exc)
        finally:
            refresh_task.cancel()
            await self._listener.remove_listener("trade_events", _cb)

    async def _refresh_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._rules_refresh)
                await self._load_rules()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                log.warning("rules refresh failed: %s", exc)

    async def _load_rules(self) -> None:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, type, params, cooldown_seconds "
                "FROM alert_rules WHERE enabled = true ORDER BY id"
            )
        self._rules = [
            Rule(
                id=r["id"],
                type=r["type"],
                params=r["params"],
                cooldown_seconds=r["cooldown_seconds"],
            )
            for r in rows
        ]

    async def _load_cooldowns(self) -> None:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT rule_id, mint, last_fired_at FROM alert_cooldowns"
            )
        self._cooldowns = {
            (r["rule_id"], r["mint"]): r["last_fired_at"] for r in rows
        }

    async def _process(self, event: dict[str, Any]) -> None:
        mint = event.get("mint")
        sol_lamports_raw = event.get("sol_lamports")
        if not mint or sol_lamports_raw is None:
            return
        try:
            sol_lamports = int(sol_lamports_raw)
        except (TypeError, ValueError):
            return
        now = time.time()
        self._spike_state.add(mint, now, sol_lamports)

        for rule in self._rules:
            message = evaluate(rule, event, self._spike_state)
            if message is None:
                continue
            if not self._pass_cooldown(rule, mint):
                continue
            await self._fire(rule, mint, message, event)

    def _pass_cooldown(self, rule: Rule, mint: str) -> bool:
        last = self._cooldowns.get((rule.id, mint))
        if last is None:
            return True
        elapsed = (datetime.now(UTC) - last).total_seconds()
        return elapsed >= rule.cooldown_seconds

    async def _fire(
        self, rule: Rule, mint: str, message: str, event: dict[str, Any]
    ) -> None:
        now = datetime.now(UTC)
        self._cooldowns[(rule.id, mint)] = now
        await self._delivery.send(
            message,
            {
                "rule_id": rule.id,
                "type": rule.type,
                "mint": mint,
                "signature": event.get("signature"),
                "side": event.get("side"),
                "sol_lamports": event.get("sol_lamports"),
                "wallet": event.get("wallet"),
            },
        )
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO alert_cooldowns (rule_id, mint, last_fired_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (rule_id, mint) DO UPDATE SET last_fired_at = $3
                    """,
                    rule.id, mint, now,
                )
                await conn.execute(
                    """
                    INSERT INTO alert_log (rule_id, mint, payload)
                    VALUES ($1, $2, $3)
                    """,
                    rule.id,
                    mint,
                    {"message": message, "event": event, "params": rule.params},
                )
