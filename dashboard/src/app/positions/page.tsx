"use client";

import { usePositions, useAllocation } from "@/lib/api";
import { StatCard } from "@/components/stat-card";

export default function PositionsPage() {
  const { data: portfolio, isLoading } = usePositions();
  const { data: allocation } = useAllocation();

  if (isLoading) return <div className="text-zinc-500">Loading positions...</div>;

  const tiers = allocation?.tiers;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Positions</h1>

      {portfolio && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Equity" value={`$${portfolio.equity.toLocaleString()}`} />
          <StatCard label="Cash" value={`$${portfolio.cash.toLocaleString()}`} />
          <StatCard label="Buying Power" value={`$${portfolio.buying_power.toLocaleString()}`} />
          <StatCard
            label="Daily P&L"
            value={`$${portfolio.daily_pnl.toFixed(2)}`}
            trend={portfolio.daily_pnl > 0 ? "up" : portfolio.daily_pnl < 0 ? "down" : "neutral"}
          />
        </div>
      )}

      {tiers && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <h2 className="text-sm font-medium text-zinc-400 mb-4 uppercase tracking-wide">
            Portfolio Allocation
          </h2>
          <div className="grid grid-cols-3 gap-4 mb-4">
            {(["safe", "neutral", "risk"] as const).map((tier) => {
              const t = tiers[tier];
              if (!t) return null;
              const actualPct = Math.round(t.actual * 100);
              const targetPct = Math.round(t.target * 100);
              const color =
                tier === "safe"
                  ? "emerald"
                  : tier === "neutral"
                    ? "blue"
                    : "amber";
              return (
                <div key={tier} className="text-center">
                  <div className="relative w-20 h-20 mx-auto mb-2">
                    <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="#27272a"
                        strokeWidth="3"
                      />
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke={
                          tier === "safe"
                            ? "#10b981"
                            : tier === "neutral"
                              ? "#3b82f6"
                              : "#f59e0b"
                        }
                        strokeWidth="3"
                        strokeDasharray={`${actualPct}, 100`}
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-lg font-bold">{actualPct}%</span>
                    </div>
                  </div>
                  <div className="text-sm font-medium capitalize">{tier}</div>
                  <div className="text-xs text-zinc-500">Target: {targetPct}%</div>
                  {t.alert && (
                    <div
                      className={`text-xs mt-1 ${
                        t.drift > 0 ? "text-amber-400" : "text-red-400"
                      }`}
                    >
                      {t.drift > 0 ? "OVER" : "UNDER"} by{" "}
                      {Math.abs(Math.round(t.drift * 100))}%
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {allocation?.sectors && (
            <div className="border-t border-zinc-800 pt-3 mt-3">
              <div className="text-xs text-zinc-500 mb-2">Sectors</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(allocation.sectors).map(([sector, data]) => (
                  <span
                    key={sector}
                    className="px-2 py-1 bg-zinc-800 rounded text-xs text-zinc-300"
                  >
                    {sector}: {Math.round((data as { pct: number }).pct * 100)}%
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {portfolio && portfolio.positions.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {portfolio.positions.map((pos) => {
            const plPercent = (
              ((pos.current_price - pos.avg_entry_price) / pos.avg_entry_price) * 100
            ).toFixed(2);
            const isUp = pos.unrealized_pl >= 0;
            const posAlloc = allocation?.positions?.find(
              (p) => p.symbol === pos.symbol
            );

            return (
              <div key={pos.symbol} className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-lg">{pos.symbol}</span>
                    {posAlloc && (
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs font-medium uppercase ${
                          posAlloc.tier === "safe"
                            ? "bg-emerald-900/50 text-emerald-400"
                            : posAlloc.tier === "risk"
                              ? "bg-amber-900/50 text-amber-400"
                              : "bg-blue-900/50 text-blue-400"
                        }`}
                      >
                        {posAlloc.tier}
                      </span>
                    )}
                  </div>
                  <span className={`font-mono font-medium ${isUp ? "text-emerald-400" : "text-red-400"}`}>
                    {isUp ? "+" : ""}${pos.unrealized_pl.toFixed(2)} ({plPercent}%)
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-zinc-500">Qty:</span>{" "}
                    <span className="font-mono">{pos.qty}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Entry:</span>{" "}
                    <span className="font-mono">${pos.avg_entry_price.toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Current:</span>{" "}
                    <span className="font-mono">${pos.current_price.toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Value:</span>{" "}
                    <span className="font-mono">${pos.market_value.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 text-center text-zinc-500">
          No open positions
        </div>
      )}
    </div>
  );
}
