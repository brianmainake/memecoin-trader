export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Token = {
  mint: string;
  symbol: string | null;
  name: string | null;
  status: "bonding" | "graduated";
  decimals: number;
  trade_count: number | null;
  buy_count: number | null;
  sell_count: number | null;
  volume_sol_lamports: string | null;
  last_trade_time: string | null;
  last_price_sol: string | null;
};

export type TokenDetail = {
  mint: string;
  symbol: string | null;
  name: string | null;
  decimals: number;
  status: string;
  created_at: string | null;
  graduated_at: string | null;
  pool_address: string | null;
  curve_address: string | null;
};

export type Trade = {
  time: string;
  signature: string;
  slot: number;
  wallet: string;
  side: "buy" | "sell";
  sol_lamports: string;
  token_base_units: string;
  price_sol: string;
  venue: "curve" | "pool";
};

export type LiveTradeMsg = {
  signature: string;
  slot: number;
  mint: string;
  wallet: string;
  side: "buy" | "sell";
  sol_lamports: string;
  token_base_units: string;
  time: string;
};

export async function listTokens(
  sort: "volume" | "recent" = "volume",
  limit = 50,
): Promise<Token[]> {
  const res = await fetch(`${API_BASE}/api/tokens?sort=${sort}&limit=${limit}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getToken(mint: string): Promise<TokenDetail> {
  const res = await fetch(`${API_BASE}/api/tokens/${mint}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function getRecentTrades(mint: string, limit = 50): Promise<Trade[]> {
  const res = await fetch(`${API_BASE}/api/tokens/${mint}/trades?limit=${limit}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
