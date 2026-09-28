"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { listTokens, type Token } from "@/lib/api";
import { formatSol, formatTime, shortAddr } from "@/lib/format";

const SORT_KEYS = ["volume", "recent"] as const;
type Sort = (typeof SORT_KEYS)[number];

export default function HomePage() {
  const [tokens, setTokens] = useState<Token[]>([]);
  const [sort, setSort] = useState<Sort>("volume");
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
    <main className="min-h-screen">
      <header className="border-b-2 border-white px-6 py-6">
        <div className="max-w-7xl mx-auto flex items-center gap-6 flex-wrap">
          <h1 className="text-3xl font-black tracking-tight uppercase">memecoin-trader</h1>
          <span className="text-xs uppercase tracking-widest text-white/50">
            top 50 pump.fun mints · 24h
          </span>
          <div className="ml-auto flex">
            {SORT_KEYS.map((k) => (
              <button
                key={k}
                onClick={() => setSort(k)}
                className={`px-4 py-2 text-xs font-bold uppercase tracking-widest border-2 -ml-[2px] first:ml-0 transition-colors ${
                  sort === k
                    ? "bg-white text-black border-white"
                    : "bg-black text-white border-white/40 hover:border-white"
                }`}
              >
                {k}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {error && (
          <div className="border-2 border-brand-red bg-brand-red/10 text-brand-red px-4 py-2 mb-6 text-sm uppercase tracking-widest">
            {error}
          </div>
        )}
        <table className="w-full text-sm">
          <thead>
            <tr className="text-white/50 uppercase text-[10px] tracking-widest">
              <th className="text-left py-3 font-normal border-b-2 border-white">Mint</th>
              <th className="text-left font-normal border-b-2 border-white">Status</th>
              <th className="text-right font-normal border-b-2 border-white">Trades</th>
              <th className="text-right font-normal border-b-2 border-white">Buy / Sell</th>
              <th className="text-right font-normal border-b-2 border-white">Volume</th>
              <th className="text-right font-normal border-b-2 border-white">Last</th>
              <th className="text-right font-normal border-b-2 border-white pr-1">Updated</th>
            </tr>
          </thead>
          <tbody>
            {tokens.map((t) => (
              <tr
                key={t.mint}
                className="border-b border-white/10 hover:bg-white/[0.04] transition-colors"
              >
                <td className="py-3">
                  <Link
                    href={`/tokens/${t.mint}`}
                    className="font-mono text-white hover:text-brand-yellow transition-colors"
                  >
                    {shortAddr(t.mint, 6)}
                  </Link>
                  {t.mint.endsWith("pump") && (
                    <span className="ml-2 text-[10px] uppercase tracking-widest text-brand-yellow">
                      pump
                    </span>
                  )}
                </td>
                <td>
                  <StatusBadge status={t.status} />
                </td>
                <td className="text-right tabular-nums">{t.trade_count ?? "—"}</td>
                <td className="text-right tabular-nums text-xs">
                  <span className="text-brand-blue font-bold">{t.buy_count ?? 0}</span>
                  <span className="text-white/30 px-1">/</span>
                  <span className="text-brand-red font-bold">{t.sell_count ?? 0}</span>
                </td>
                <td className="text-right tabular-nums">{formatSol(t.volume_sol_lamports)}</td>
                <td className="text-right font-mono tabular-nums text-xs">
                  {t.last_price_sol ? Number(t.last_price_sol).toExponential(2) : "—"}
                </td>
                <td className="text-right text-xs text-white/50 tabular-nums pr-1">
                  {formatTime(t.last_trade_time)}
                </td>
              </tr>
            ))}
            {tokens.length === 0 && !error && (
              <tr>
                <td colSpan={7} className="py-10 text-center text-white/40 uppercase tracking-widest text-xs">
                  waiting for data…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}

function StatusBadge({ status }: { status: string }) {
  const isGraduated = status === "graduated";
  const className = isGraduated
    ? "bg-brand-blue text-white"
    : "bg-brand-yellow text-black";
  return (
    <span className={`inline-block px-2 py-0.5 text-[10px] uppercase tracking-widest font-bold ${className}`}>
      {status}
    </span>
  );
}
