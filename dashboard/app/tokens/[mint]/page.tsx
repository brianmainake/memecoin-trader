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

  return (
    <main className="p-6 max-w-6xl mx-auto w-full">
      <Link href="/" className="text-sm text-blue-400 hover:underline">
        ← back
      </Link>
      <h1 className="text-lg mt-2 font-mono break-all">{mint}</h1>
      {error && <div className="text-red-400 text-sm mt-2">{error}</div>}
      {token && (
        <div className="text-sm text-gray-400 mt-2 mb-6">
          {token.symbol ?? "—"} · <span className="capitalize">{token.status}</span> ·{" "}
          {token.decimals} decimals
          {token.pool_address && <> · pool {shortAddr(token.pool_address, 4)}</>}
        </div>
      )}
      <div className="mb-8">
        <CandleChart mint={mint} />
      </div>
      <div className="flex items-center gap-2 mb-2">
        <h2 className="text-lg">Recent trades</h2>
        <span className="text-xs text-gray-500 rounded-full bg-gray-800 px-2 py-0.5">
          live
        </span>
      </div>
      <table className="w-full text-sm">
        <thead className="text-left text-gray-400 border-b border-gray-800">
          <tr>
            <th className="py-2 font-normal">Time</th>
            <th className="font-normal">Side</th>
            <th className="font-normal">Wallet</th>
            <th className="font-normal">SOL</th>
            <th className="font-normal">Tokens</th>
            <th className="font-normal">Sig</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.signature} className="border-b border-gray-900">
              <td className="py-1 text-xs text-gray-400">{formatTime(t.time)}</td>
              <td className={t.side === "buy" ? "text-green-400" : "text-red-400"}>
                {t.side}
              </td>
              <td className="font-mono text-xs">{shortAddr(t.wallet, 4)}</td>
              <td>{formatSol(t.sol_lamports)}</td>
              <td>{formatTokenAmount(t.token_base_units, token?.decimals ?? 6)}</td>
              <td className="font-mono text-xs text-gray-500">
                {shortAddr(t.signature, 4)}
              </td>
            </tr>
          ))}
          {trades.length === 0 && (
            <tr>
              <td colSpan={6} className="py-6 text-center text-gray-500">
                No trades yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </main>
  );
}
