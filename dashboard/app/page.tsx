"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { listTokens, type Token } from "@/lib/api";
import { formatSol, formatTime, shortAddr } from "@/lib/format";

export default function HomePage() {
  const [tokens, setTokens] = useState<Token[]>([]);
  const [sort, setSort] = useState<"volume" | "recent">("volume");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const rows = await listTokens(sort, 50);
        if (!cancelled) {
          setTokens(rows);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }
    tick();
    const id = setInterval(tick, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [sort]);

  return (
    <main className="p-6 max-w-6xl mx-auto w-full">
      <div className="flex items-center gap-4 mb-6">
        <h1 className="text-2xl font-bold">memecoin-trader</h1>
        <div className="ml-auto flex gap-2 text-sm">
          <button
            className={`px-3 py-1 rounded transition-colors ${
              sort === "volume"
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-300 hover:bg-gray-700"
            }`}
            onClick={() => setSort("volume")}
          >
            Volume
          </button>
          <button
            className={`px-3 py-1 rounded transition-colors ${
              sort === "recent"
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-300 hover:bg-gray-700"
            }`}
            onClick={() => setSort("recent")}
          >
            Recent
          </button>
        </div>
      </div>
      {error && <div className="text-red-400 mb-4 text-sm">{error}</div>}
      <table className="w-full text-sm">
        <thead className="text-left text-gray-400 border-b border-gray-800">
          <tr>
            <th className="py-2 font-normal">Mint</th>
            <th className="font-normal">Status</th>
            <th className="font-normal">Trades (24h)</th>
            <th className="font-normal">B/S</th>
            <th className="font-normal">Volume</th>
            <th className="font-normal">Last price</th>
            <th className="font-normal">Time</th>
          </tr>
        </thead>
        <tbody>
          {tokens.map((t) => (
            <tr key={t.mint} className="border-b border-gray-900 hover:bg-gray-900/50">
              <td className="py-2">
                <Link
                  href={`/tokens/${t.mint}`}
                  className="text-blue-400 hover:underline font-mono"
                >
                  {shortAddr(t.mint, 6)}
                </Link>
                {t.mint.endsWith("pump") && (
                  <span className="ml-2 text-xs text-yellow-500">pump</span>
                )}
              </td>
              <td className="capitalize">{t.status}</td>
              <td>{t.trade_count ?? "-"}</td>
              <td className="text-xs">
                <span className="text-green-400">{t.buy_count ?? 0}</span>
                {" / "}
                <span className="text-red-400">{t.sell_count ?? 0}</span>
              </td>
              <td>{formatSol(t.volume_sol_lamports)}</td>
              <td className="font-mono">
                {t.last_price_sol ? Number(t.last_price_sol).toExponential(2) : "-"}
              </td>
              <td className="text-xs text-gray-400">{formatTime(t.last_trade_time)}</td>
            </tr>
          ))}
          {tokens.length === 0 && !error && (
            <tr>
              <td colSpan={7} className="py-6 text-center text-gray-500">
                No trades in the last 24h yet. Start the ingestor to fill this in.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </main>
  );
}
