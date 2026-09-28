"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useState } from "react";

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
        // ignore
      }
    };
    return () => ws.close();
  }, [mint]);

  const stats = useMemo(() => {
    const totalSol = trades.reduce((s, t) => s + Number(t.sol_lamports || 0), 0);
    const buys = trades.filter((t) => t.side === "buy").length;
    const sells = trades.filter((t) => t.side === "sell").length;
    const lastPrice = trades.find((t) => t.price_sol && t.price_sol !== "-")?.price_sol;
    return { totalSol, buys, sells, count: trades.length, lastPrice };
  }, [trades]);

  const isGraduated = token?.status === "graduated";

  return (
    <main>
      <nav className="sticky top-0 z-10 backdrop-blur bg-black/70 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <Link
            href="/"
            className="text-sm text-white/60 hover:text-white transition-colors inline-flex items-center gap-1.5"
          >
            <span aria-hidden>←</span> Back
          </Link>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        <section>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="font-mono text-base md:text-lg break-all">{mint}</h1>
            {token && (
              <span
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] rounded-full font-medium ${
                  isGraduated
                    ? "bg-brand-blue/10 text-brand-blue"
                    : "bg-brand-yellow/10 text-brand-yellow"
                }`}
              >
                <span
                  className={`w-1 h-1 rounded-full ${
                    isGraduated ? "bg-brand-blue" : "bg-brand-yellow"
                  }`}
                />
                {token.status}
              </span>
            )}
          </div>
          {token && (
            <div className="text-sm text-white/50 mt-2 flex flex-wrap gap-x-4 gap-y-1">
              <span>
                {token.symbol ?? "—"} · {token.decimals} decimals
              </span>
              {token.pool_address && <span>pool {shortAddr(token.pool_address, 4)}</span>}
              {token.graduated_at && <span>graduated {formatTime(token.graduated_at)}</span>}
            </div>
          )}
        </section>

        {error && (
          <div className="border border-brand-red/30 bg-brand-red/5 text-brand-red px-4 py-3 text-sm rounded-2xl">
            {error}
          </div>
        )}

        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat
            label="Last Price (SOL)"
            value={stats.lastPrice ? Number(stats.lastPrice).toExponential(2) : "—"}
            mono
          />
          <Stat label="Recent Volume" value={formatSol(String(stats.totalSol))} />
          <Stat
            label="Buys · Sells"
            value={
              <>
                <span className="text-brand-green">{stats.buys}</span>
                <span className="text-white/25 px-1.5">·</span>
                <span className="text-brand-red">{stats.sells}</span>
              </>
            }
          />
          <Stat label="Trades Shown" value={stats.count.toString()} />
        </section>

        <section>
          <CandleChart mint={mint} />
        </section>

        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium">Recent Trades</h2>
            <div className="flex items-center gap-1.5 text-xs text-brand-yellow">
              <span className="live-dot inline-block w-1.5 h-1.5 bg-brand-yellow rounded-full" />
              Live
            </div>
          </div>
          <div className="border border-white/10 rounded-2xl overflow-hidden bg-white/[0.01]">
            <table className="w-full text-sm">
              <thead className="bg-white/[0.03] text-white/50 text-xs">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">Time</th>
                  <th className="text-left font-medium">Side</th>
                  <th className="text-left font-medium">Wallet</th>
                  <th className="text-right font-medium">SOL</th>
                  <th className="text-right font-medium">Tokens</th>
                  <th className="text-right font-medium pr-5">Sig</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.signature} className="border-t border-white/5">
                    <td className="px-5 py-2.5 text-xs text-white/70 tabular-nums">
                      {formatTime(t.time)}
                    </td>
                    <td>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 text-[11px] rounded-full font-medium capitalize ${
                          t.side === "buy"
                            ? "bg-brand-green/10 text-brand-green"
                            : "bg-brand-red/10 text-brand-red"
                        }`}
                      >
                        {t.side}
                      </span>
                    </td>
                    <td className="font-mono text-xs text-white/80">
                      {shortAddr(t.wallet, 4)}
                    </td>
                    <td className="text-right font-medium tabular-nums">
                      {formatSol(t.sol_lamports)}
                    </td>
                    <td className="text-right tabular-nums text-white/80">
                      {formatTokenAmount(t.token_base_units, token?.decimals ?? 6)}
                    </td>
                    <td className="text-right font-mono text-xs text-white/40 pr-5">
                      {shortAddr(t.signature, 4)}
                    </td>
                  </tr>
                ))}
                {trades.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-white/40 text-sm">
                      No trades yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}

function Stat({
  label,
  value,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="border border-white/10 rounded-2xl p-4 bg-white/[0.02]">
      <div className="text-xs text-white/50">{label}</div>
      <div
        className={`text-xl font-semibold mt-1 tabular-nums ${mono ? "font-mono" : ""}`}
      >
        {value}
      </div>
    </div>
  );
}
