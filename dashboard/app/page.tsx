"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { listTokens, type Token } from "@/lib/api";
import { formatSol, formatTime, shortAddr } from "@/lib/format";

type Sort = "volume" | "recent";
type Filter = "all" | "bonding" | "graduated";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "bonding", label: "Bonding" },
  { key: "graduated", label: "Graduated" },
];
const SORTS: { key: Sort; label: string }[] = [
  { key: "volume", label: "Volume" },
  { key: "recent", label: "Recent" },
];

export default function HomePage() {
  const [tokens, setTokens] = useState<Token[]>([]);
  const [sort, setSort] = useState<Sort>("volume");
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const rows = await listTokens(sort, 100);
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

  const filtered = useMemo(() => {
    if (filter === "all") return tokens;
    return tokens.filter((t) => t.status === filter);
  }, [tokens, filter]);

  const stats = useMemo(() => {
    const active = tokens.filter((t) => (t.trade_count ?? 0) > 0);
    const totalVolLamports = active.reduce(
      (s, t) => s + Number(t.volume_sol_lamports ?? 0),
      0,
    );
    const totalTrades = active.reduce((s, t) => s + (t.trade_count ?? 0), 0);
    const graduated = tokens.filter((t) => t.status === "graduated").length;
    return {
      volume: totalVolLamports,
      trades: totalTrades,
      tokens: active.length,
      graduated,
    };
  }, [tokens]);

  return (
    <main>
      <nav className="sticky top-0 z-10 backdrop-blur bg-black/70 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 bg-brand-yellow rounded-full live-dot" />
            <span className="font-semibold tracking-tight text-[15px]">memecoin-trader</span>
          </div>
          <div className="ml-auto text-xs text-white/40 uppercase tracking-wider">
            pump.fun · live
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="24h Volume" value={formatSol(String(stats.volume))} />
          <StatCard label="24h Trades" value={stats.trades.toLocaleString()} />
          <StatCard label="Active Tokens" value={stats.tokens.toString()} />
          <StatCard label="Graduated" value={stats.graduated.toString()} accent="blue" />
        </section>

        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <Segmented options={FILTERS} value={filter} onChange={setFilter} />
          <div className="ml-auto">
            <Segmented options={SORTS} value={sort} onChange={setSort} />
          </div>
        </div>

        <div className="border border-white/10 rounded-2xl overflow-hidden bg-white/[0.01]">
          <table className="w-full text-sm">
            <thead className="bg-white/[0.03] text-white/50 text-xs">
              <tr>
                <th className="text-left px-5 py-3 font-medium">Token</th>
                <th className="text-left font-medium">Status</th>
                <th className="text-right font-medium">Trades</th>
                <th className="text-right font-medium">Buy · Sell</th>
                <th className="text-right font-medium">Volume</th>
                <th className="text-right font-medium">Last Price</th>
                <th className="text-right font-medium pr-5">Updated</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr
                  key={t.mint}
                  className="border-t border-white/5 hover:bg-white/[0.03] transition-colors"
                >
                  <td className="px-5 py-3.5">
                    <Link href={`/tokens/${t.mint}`} className="group inline-flex items-center gap-2">
                      <span className="font-mono text-white group-hover:text-brand-yellow transition-colors">
                        {shortAddr(t.mint, 6)}
                      </span>
                      {t.mint.endsWith("pump") && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-yellow/10 text-brand-yellow font-medium">
                          pump
                        </span>
                      )}
                    </Link>
                  </td>
                  <td>
                    <StatusPill status={t.status} />
                  </td>
                  <td className="text-right text-white/90 font-medium tabular-nums">
                    {t.trade_count ?? "—"}
                  </td>
                  <td className="text-right text-xs tabular-nums">
                    <span className="text-brand-green font-medium">{t.buy_count ?? 0}</span>
                    <span className="text-white/25 px-1.5">·</span>
                    <span className="text-brand-red font-medium">{t.sell_count ?? 0}</span>
                  </td>
                  <td className="text-right font-medium tabular-nums">
                    {formatSol(t.volume_sol_lamports)}
                  </td>
                  <td className="text-right font-mono text-xs tabular-nums text-white/70">
                    {t.last_price_sol ? Number(t.last_price_sol).toExponential(2) : "—"}
                  </td>
                  <td className="text-right text-xs text-white/50 tabular-nums pr-5">
                    {formatTime(t.last_trade_time)}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && !error && (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-white/40 text-sm">
                    {tokens.length === 0
                      ? "Waiting for data…"
                      : `No ${filter === "all" ? "" : filter} tokens right now`}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {error && (
            <div className="border-t border-brand-red/30 bg-brand-red/5 text-brand-red px-4 py-3 text-sm">
              {error}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: "blue" | "yellow" | "red";
}) {
  const color =
    accent === "blue"
      ? "text-brand-blue"
      : accent === "yellow"
        ? "text-brand-yellow"
        : accent === "red"
          ? "text-brand-red"
          : "text-white";
  return (
    <div className="border border-white/10 rounded-2xl p-4 bg-white/[0.02]">
      <div className="text-xs text-white/50">{label}</div>
      <div className={`text-2xl font-semibold mt-1 tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  if (status === "graduated") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] rounded-full bg-brand-blue/10 text-brand-blue font-medium">
        <span className="w-1 h-1 rounded-full bg-brand-blue" />
        Graduated
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] rounded-full bg-brand-yellow/10 text-brand-yellow font-medium">
      <span className="w-1 h-1 rounded-full bg-brand-yellow" />
      Bonding
    </span>
  );
}

function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { key: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex gap-1 p-1 bg-white/[0.04] border border-white/10 rounded-full">
      {options.map((o) => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          className={`px-3.5 py-1.5 text-xs font-medium rounded-full transition-colors ${
            value === o.key ? "bg-white text-black" : "text-white/70 hover:text-white"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
