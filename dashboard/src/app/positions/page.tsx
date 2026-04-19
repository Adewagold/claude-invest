"use client";

import { usePortfolioSnapshots } from "@/lib/api";
import { StatCard } from "@/components/stat-card";

export default function PositionsPage() {
  const { data: snapshots } = usePortfolioSnapshots(1);
  const latest = snapshots?.[0];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Positions</h1>

      {latest && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Value" value={`$${latest.total_value.toLocaleString()}`} />
          <StatCard label="Cash" value={`$${latest.cash.toLocaleString()}`} />
          <StatCard label="Positions Value" value={`$${latest.positions_value.toLocaleString()}`} />
          <StatCard
            label="Daily P&L"
            value={`$${(latest.daily_pnl ?? 0).toFixed(2)}`}
            trend={(latest.daily_pnl ?? 0) > 0 ? "up" : (latest.daily_pnl ?? 0) < 0 ? "down" : "neutral"}
          />
        </div>
      )}

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 text-center">
        <p className="text-zinc-400 mb-2">
          Live positions are fetched from Alpaca when the trading engine runs.
        </p>
        <p className="text-zinc-500 text-sm">
          Check the Overview page for the latest portfolio state, or run the CLI:
        </p>
        <code className="text-xs text-zinc-400 bg-zinc-800 px-3 py-1.5 rounded mt-2 inline-block">
          .venv/bin/python -m claude_invest.main portfolio
        </code>
      </div>
    </div>
  );
}
