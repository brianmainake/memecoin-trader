export function formatSol(lamports: string | null | undefined): string {
  if (!lamports) return "-";
  const n = Number(lamports) / 1e9;
  if (n < 0.001) return `${(n * 1000).toFixed(3)} mSOL`;
  if (n < 1) return `${n.toFixed(4)} SOL`;
  return `${n.toFixed(2)} SOL`;
}

export function formatTokenAmount(baseUnits: string, decimals: number): string {
  const n = Number(baseUnits) / Math.pow(10, decimals);
  if (n < 1000) return n.toFixed(2);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`;
  if (n < 1_000_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  return `${(n / 1_000_000_000).toFixed(1)}B`;
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleTimeString();
}

export function shortAddr(addr: string, chars = 4): string {
  if (addr.length <= chars * 2 + 1) return addr;
  return `${addr.slice(0, chars)}…${addr.slice(-chars)}`;
}
