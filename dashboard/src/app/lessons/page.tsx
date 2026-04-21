"use client";

import { useLessons, useStrategyBrief } from "@/lib/api";

export default function LessonsPage() {
  const { data: lessons } = useLessons();
  const { data: brief } = useStrategyBrief();

  const patterns = lessons?.patterns ?? [];
  const sorted = [...patterns].sort((a, b) => b.total - a.total);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Learning Engine</h1>

      {brief && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <h2 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">
            Active Strategy Brief
          </h2>
          <pre className="text-sm text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed">
            {brief.brief}
          </pre>
        </div>
      )}

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wide">
            Signal Patterns
          </h2>
          <span className="text-xs text-zinc-500">
            {patterns.length} patterns tracked
          </span>
        </div>

        {sorted.length === 0 ? (
          <div className="text-zinc-500 text-center py-8">
            No patterns yet. Run /review-day after closing some trades.
          </div>
        ) : (
          <div className="space-y-2">
            {sorted.map((p, i) => {
              const winPct = Math.round(p.win_rate * 100);
              const barColor =
                winPct >= 75
                  ? "bg-emerald-500"
                  : winPct <= 25
                    ? "bg-red-500"
                    : "bg-zinc-500";
              return (
                <div
                  key={i}
                  className="flex items-center gap-4 p-3 bg-zinc-800/50 rounded-md"
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-mono text-sm text-zinc-200 truncate">
                      {p.signal_combo}
                    </div>
                    <div className="text-xs text-zinc-500 mt-1">
                      {p.confidence === "high" ? "RULE" : "Observation"} · Avg
                      P&L: ${p.avg_pnl.toFixed(2)}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right">
                      <span className="text-emerald-400 text-sm font-mono">
                        {p.wins}W
                      </span>
                      <span className="text-zinc-600 mx-1">/</span>
                      <span className="text-red-400 text-sm font-mono">
                        {p.losses}L
                      </span>
                    </div>
                    <div className="w-16 bg-zinc-700 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${barColor}`}
                        style={{ width: `${winPct}%` }}
                      />
                    </div>
                    <span className="text-sm font-mono w-10 text-right text-zinc-300">
                      {winPct}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {lessons?.last_updated && (
        <div className="text-xs text-zinc-600 text-right">
          Last updated: {lessons.last_updated}
        </div>
      )}
    </div>
  );
}
