"use client";

import { usePortfolioSnapshots, useStats, useDecisions } from "@/lib/api";
import { StatCard } from "@/components/stat-card";
import { PortfolioChart } from "@/components/portfolio-chart";

export default function OverviewPage() {
  const { data: snapshots, error: snapErr } = usePortfolioSnapshots();
  const { data: stats, error: statsErr } = useStats();
  const { data: decisions, error: decErr } = useDecisions(10);

  if (snapErr || statsErr || decErr) {
    return (
      <div className="p-6 bg-red-900/20 border border-red-800 rounded-lg text-red-400">
        <p className="font-medium">API connection error</p>
        <p className="text-sm mt-1 text-red-500">
          Make sure the FastAPI server is running on port 8000:
          <code className="block mt-2 bg-zinc-900 px-3 py-1 rounded text-xs text-zinc-300">
            .venv/bin/python -m claude_invest.modules.api_server
          </code>
        </p>
      </div>
    );
  }

  const latestSnapshot = snapshots?.[0];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Overview</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Portfolio Value"
          value={
            latestSnapshot
              ? `$${latestSnapshot.total_value.toLocaleString()}`
              : "—"
          }
        />
        <StatCard
          label="Daily P&L"
          value={
            latestSnapshot
              ? `$${(latestSnapshot.daily_pnl ?? 0).toFixed(2)}`
              : "—"
          }
          trend={
            (latestSnapshot?.daily_pnl ?? 0) > 0
              ? "up"
              : (latestSnapshot?.daily_pnl ?? 0) < 0
                ? "down"
                : "neutral"
          }
        />
        <StatCard
          label="Cash"
          value={
            latestSnapshot
              ? `$${latestSnapshot.cash.toLocaleString()}`
              : "—"
          }
        />
        <StatCard
          label="Positions Value"
          value={
            latestSnapshot
              ? `$${latestSnapshot.positions_value.toLocaleString()}`
              : "—"
          }
        />
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-4">
          Portfolio Value Over Time
        </h2>
        {snapshots && snapshots.length > 0 ? (
          <PortfolioChart snapshots={snapshots} />
        ) : (
          <div className="text-zinc-500 text-center py-12">
            No portfolio data yet
          </div>
        )}
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-4">
          Recent Decisions
        </h2>
        {decisions && decisions.length > 0 ? (
          <div className="space-y-3">
            {decisions.map((d) => (
              <div
                key={d.id}
                className="flex items-start gap-3 p-3 bg-zinc-800/50 rounded-md"
              >
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium uppercase ${
                    d.action === "buy"
                      ? "bg-emerald-900/50 text-emerald-400"
                      : d.action === "sell"
                        ? "bg-red-900/50 text-red-400"
                        : d.action === "hold"
                          ? "bg-blue-900/50 text-blue-400"
                          : "bg-zinc-700 text-zinc-400"
                  }`}
                >
                  {d.action}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-medium">{d.ticker}</span>
                    <span className="text-xs text-zinc-500">
                      {new Date(d.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm text-zinc-400 mt-1 line-clamp-2">
                    {d.reasoning}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-zinc-500 text-center py-8">
            No decisions yet
          </div>
        )}
      </div>
    </div>
  );
}
