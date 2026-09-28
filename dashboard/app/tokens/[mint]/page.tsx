"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import CandleChart from "@/components/CandleChart";
import {
  API_BASE,
  getRecentTrades,
  getToken,
  type LiveTradeMsg,
  type TokenDetail,
  type Trade,
} from "@/lib/api";
import { formatSol, formatTime, formatTokenAmount, shortAddr } from "@/lib/format";

export default function TokenDetailPage({
  params,
}: {
  params: Promise<{ mint: string }>;
}) {
  const { mint } = use(params);
  const [token, setToken] = useState<TokenDetail | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getToken(mint).then(setToken).catch((e) => setError(String(e)));
    getRecentTrades(mint, 50).then(setTrades).catch((e) => setError(String(e)));
  }, [mint]);

  useEffect(() => {
    const wsUrl = API_BASE.replace(/^http/, "ws") + "/api/ws/trades";
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as LiveTradeMsg;
        if (msg.mint !== mint) return;
        setTrades((prev) => [
          {
            time: msg.time,
            signature: msg.signature,
            slot: msg.slot,
            wallet: msg.wallet,
            side: msg.side,
            sol_lamports: msg.sol_lamports,
            token_base_units: msg.token_base_units,
            price_sol: "-",
            venue: "curve",
          },
          ...prev.slice(0, 49),
        ]);
      } catch {
        // ignore bad frames
      }
    };
    return () => ws.close();
  }, [mint]);

  const isGraduated = token?.status === "graduated";

  return (
    <main className="min-h-screen">
      <header className="border-b-2 border-white px-6 py-6">
        <div className="max-w-7xl mx-auto">
          <Link
            href="/"
            className="text-xs uppercase tracking-widest text-white/60 hover:text-brand-yellow transition-colors inline-block mb-3"
          >
            ← back
          </Link>
          <div className="flex items-baseline gap-4 flex-wrap">
            <h1 className="font-mono text-lg md:text-xl break-all">{mint}</h1>
            {token && (
              <span
                className={`inline-block px-2 py-0.5 text-[10px] uppercase tracking-widest font-bold shrink-0 ${
                  isGraduated ? "bg-brand-blue text-white" : "bg-brand-yellow text-black"
                }`}
              >
                {token.status}
              </span>
            )}
          </div>
          {token && (
            <div className="text-xs uppercase tracking-widest text-white/50 mt-2">
              {token.symbol ?? "—"} · {token.decimals} decimals
              {token.pool_address && <> · pool {shortAddr(token.pool_address, 4)}</>}
              {token.graduated_at && <> · graduated {formatTime(token.graduated_at)}</>}
            </div>
          )}
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-10">
        {error && (
          <div className="border-2 border-brand-red bg-brand-red/10 text-brand-red px-4 py-2 text-sm uppercase tracking-widest">
            {error}
          </div>
        )}

        <section>
          <CandleChart mint={mint} />
        </section>

        <section>
          <div className="flex items-center gap-3 mb-3">
            <h2 className="text-xs uppercase tracking-widest text-white/70">Recent trades</h2>
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-brand-yellow">
              <span className="live-dot inline-block w-1.5 h-1.5 bg-brand-yellow rounded-full" />
              live
            </div>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-white/50 uppercase text-[10px] tracking-widest">
                <th className="text-left py-3 font-normal border-b-2 border-white">Time</th>
                <th className="text-left font-normal border-b-2 border-white">Side</th>
                <th className="text-left font-normal border-b-2 border-white">Wallet</th>
                <th className="text-right font-normal border-b-2 border-white">SOL</th>
                <th className="text-right font-normal border-b-2 border-white">Tokens</th>
                <th className="text-right font-normal border-b-2 border-white pr-1">Sig</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.signature} className="border-b border-white/10">
                  <td className="py-2 text-xs text-white/60 tabular-nums">
                    {formatTime(t.time)}
                  </td>
                  <td>
                    <span
                      className={`inline-block px-2 py-0.5 text-[10px] uppercase tracking-widest font-bold ${
                        t.side === "buy"
                          ? "bg-brand-blue text-white"
                          : "bg-brand-red text-white"
                      }`}
                    >
                      {t.side}
                    </span>
                  </td>
                  <td className="font-mono text-xs text-white/80">{shortAddr(t.wallet, 4)}</td>
                  <td className="text-right tabular-nums">{formatSol(t.sol_lamports)}</td>
                  <td className="text-right tabular-nums">
                    {formatTokenAmount(t.token_base_units, token?.decimals ?? 6)}
                  </td>
                  <td className="text-right font-mono text-xs text-white/40 pr-1">
                    {shortAddr(t.signature, 4)}
                  </td>
                </tr>
              ))}
              {trades.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-white/40 uppercase tracking-widest text-xs">
                    no trades yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      </div>
    </main>
  );
}
