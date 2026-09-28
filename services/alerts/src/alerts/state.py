from __future__ import annotations

from collections import deque


class VolumeSpikeState:
    """Per-mint rolling window of (unix_time, sol_lamports) trades.

    Keeps enough history to compare 'current window' vs 'baseline'
    (the previous few windows) for volume_spike rules. Not shared
    across ranges — one instance sized for the largest window used.
    """

    def __init__(self, retention_seconds: int = 300):
        self._retention = retention_seconds
        self._by_mint: dict[str, deque[tuple[float, int]]] = {}

    def add(self, mint: str, now: float, sol_lamports: int) -> None:
        d = self._by_mint.setdefault(mint, deque())
        d.append((now, sol_lamports))
        cutoff = now - self._retention
        while d and d[0][0] < cutoff:
            d.popleft()

    def windows(
        self, mint: str, now: float, window_seconds: int, baseline_windows: int = 4
    ) -> tuple[int, int] | None:
        """Return (recent_sum, avg_baseline_per_window) or None if no data yet.

        recent_sum: sum of sol_lamports in (now - window_seconds, now]
        avg_baseline_per_window: average per window over the previous
        baseline_windows windows.
        """
        d = self._by_mint.get(mint)
        if not d:
            return None
        w = window_seconds
        recent = sum(sol for t, sol in d if t > now - w)
        baseline_total = sum(sol for t, sol in d if now - w * (1 + baseline_windows) < t <= now - w)
        avg_baseline = baseline_total // baseline_windows if baseline_windows > 0 else 0
        return recent, avg_baseline
