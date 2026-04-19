"use client";

import { usePositions } from "@/lib/api";
import { StatCard } from "@/components/stat-card";

export default function PositionsPage() {
  const { data: portfolio, isLoading } = usePositions();

  if (isLoading) return <div className="text-zinc-500">Loading positions...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Positions</h1>

      {portfolio && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Equity"
            value={`$${portfolio.equity.toLocaleString()}`}
          />
          <StatCard
            label="Cash"
            value={`$${portfolio.cash.toLocaleString()}`}
          />
          <StatCard
            label="Buying Power"
            value={`$${portfolio.buying_power.toLocaleString()}`}
          />
          <StatCard
            label="Daily P&L"
            value={`$${portfolio.daily_pnl.toFixed(2)}`}
            trend={portfolio.daily_pnl > 0 ? "up" : portfolio.daily_pnl < 0 ? "down" : "neutral"}
          />
        </div>
      )}

      {portfolio && portfolio.positions.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {portfolio.positions.map((pos) => {
            const plPercent = (
              ((pos.current_price - pos.avg_entry_price) / pos.avg_entry_price) *
              100
            ).toFixed(2);
            const isUp = pos.unrealized_pl >= 0;

            return (
              <div
                key={pos.symbol}
                className="bg-zinc-900 border border-zinc-800 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-mono font-bold text-lg">
                    {pos.symbol}
                  </span>
                  <span
                    className={`font-mono font-medium ${
                      isUp ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {isUp ? "+" : ""}${pos.unrealized_pl.toFixed(2)} (
                    {plPercent}%)
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-zinc-500">Qty:</span>{" "}
                    <span className="font-mono">{pos.qty}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Entry:</span>{" "}
                    <span className="font-mono">
                      ${pos.avg_entry_price.toFixed(2)}
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Current:</span>{" "}
                    <span className="font-mono">
                      ${pos.current_price.toFixed(2)}
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Value:</span>{" "}
                    <span className="font-mono">
                      ${pos.market_value.toFixed(2)}
                    </span>
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
