from __future__ import annotations

import os
from dataclasses import dataclass


def env(key: str, default: str | None = None) -> str:
    val = os.environ.get(key)
    if val is None:
        if default is not None:
            return default
        raise RuntimeError(f"Missing required env: {key}")
    return val


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    dsn: str

    @classmethod
    def from_env(cls) -> DatabaseConfig:
        return cls(dsn=env("DATABASE_URL"))


@dataclass(frozen=True, slots=True)
class HeliusConfig:
    api_key: str
    rpc_endpoint: str

    @classmethod
    def from_env(cls) -> HeliusConfig:
        api_key = env("HELIUS_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "HELIUS_API_KEY is empty; get a free key at "
                "https://dashboard.helius.dev and put it in .env"
            )
        return cls(
            api_key=api_key,
            rpc_endpoint=env("HELIUS_RPC_ENDPOINT", "https://mainnet.helius-rpc.com"),
        )

    @property
    def ws_url(self) -> str:
        host = self.rpc_endpoint.removeprefix("https://").removeprefix("http://").rstrip("/")
        return f"wss://{host}/?api-key={self.api_key}"
