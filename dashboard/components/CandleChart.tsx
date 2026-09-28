"use client";

import {
  CandlestickSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

import { API_BASE } from "@/lib/api";

type CandleRow = {
  time: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume_sol_lamports: string;
  buy_count: number;
  sell_count: number;
  trade_count: number;
};

export type Interval = "1m" | "5m" | "1h" | "24h";

const INTERVALS: Interval[] = ["1m", "5m", "1h", "24h"];

async function fetchCandles(mint: string, interval: Interval): Promise<CandleRow[]> {
  const res = await fetch(
    `${API_BASE}/api/tokens/${mint}/candles?interval=${interval}&limit=200`,
    { cache: "no-store" },
  );
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export default function CandleChart({ mint }: { mint: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [intervalKey, setIntervalKey] = useState<Interval>("1m");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { color: "transparent" },
        textColor: "#ffffff",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.06)" },
        horzLines: { color: "rgba(255,255,255,0.06)" },
      },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: "#ffffff" },
      rightPriceScale: { borderColor: "#ffffff" },
      crosshair: { mode: 1 },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#0044ff",
      downColor: "#ff0033",
      borderVisible: false,
      wickUpColor: "#0044ff",
      wickDownColor: "#ff0033",
      priceFormat: { type: "price", precision: 12, minMove: 1e-12 },
    });
    chartRef.current = chart;
    seriesRef.current = series;
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const rows = await fetchCandles(mint, intervalKey);
        if (cancelled || !seriesRef.current) return;
        const data = rows
          .slice()
          .reverse()
          .map((r) => ({
            time: Math.floor(Date.parse(r.time) / 1000) as Time,
            open: Number(r.open),
            high: Number(r.high),
            low: Number(r.low),
            close: Number(r.close),
          }));
        seriesRef.current.setData(data);
        chartRef.current?.timeScale().fitContent();
        setError(null);
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }
    tick();
    const id = window.setInterval(tick, 10_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [mint, intervalKey]);

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <h2 className="text-xs uppercase tracking-widest text-white/70">Candles</h2>
        <div className="ml-auto flex">
          {INTERVALS.map((i) => (
            <button
              key={i}
              onClick={() => setIntervalKey(i)}
              className={`px-3 py-1 text-[10px] font-bold uppercase tracking-widest border-2 -ml-[2px] first:ml-0 transition-colors ${
                intervalKey === i
                  ? "bg-white text-black border-white"
                  : "bg-black text-white border-white/40 hover:border-white"
              }`}
            >
              {i}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <div className="border-2 border-brand-red bg-brand-red/10 text-brand-red px-3 py-1.5 mb-2 text-xs uppercase tracking-widest">
          {error}
        </div>
      )}
      <div ref={containerRef} className="h-[400px] border-2 border-white" />
    </div>
  );
}
