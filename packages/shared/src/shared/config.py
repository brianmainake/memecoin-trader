from __future__ import annotations

import os
from dataclasses import dataclass


def env(key: str, default: str | None = None) -> str:
    val = os.environ.get(key, default)
    if val is None:
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
        return cls(
            api_key=env("HELIUS_API_KEY"),
            rpc_endpoint=env("HELIUS_RPC_ENDPOINT", "https://mainnet.helius-rpc.com"),
        )
