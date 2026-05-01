"use client";

import { useCoreStatus, useCoreSchedule, useRebalancePreview } from "@/lib/api";

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <div className="text-xs text-zinc-500 uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-bold text-zinc-100 mt-1">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

export default function CorePage() {
  const { data: status } = useCoreStatus();
  const { data: scheduleData } = useCoreSchedule();
  const { data: rebalanceData } = useRebalancePreview();

  const holdings = status?.holdings ?? [];
  const schedule = scheduleData?.schedule ?? [];
  const preview = rebalanceData?.preview ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Core Holdings</h1>

      {/* Portfolio Split */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard
          label="Core Capital"
          value={status ? `$${status.core_capital.toLocaleString()}` : "—"}
        />
        <StatCard
          label="Invested"
          value={status ? `$${(status.core_capital - (status.cash_remaining ?? 0)).toFixed(2)}` : "—"}
          sub={status ? `${(((status.core_capital - (status.cash_remaining ?? 0)) / status.core_capital) * 100).toFixed(0)}% deployed` : undefined}
        />
        <StatCard
          label="Cash Remaining"
          value={status ? `$${status.cash_remaining.toFixed(2)}` : "—"}
        />
      </div>

      {/* Holdings Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">Holdings</h2>
        {holdings.length === 0 ? (
          <div className="text-zinc-500 text-center py-8">No core holdings yet. Run core-cycle to start buying.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-zinc-500 text-xs uppercase">
                <th className="text-left py-2">Symbol</th>
                <th className="text-left">Sector</th>
                <th className="text-right">Cost Basis</th>
                <th className="text-right">Value</th>
                <th className="text-right">P&L</th>
                <th className="text-right">Weight</th>
                <th className="text-right">Target</th>
                <th className="text-right">Drift</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => {
                const driftColor = Math.abs(h.drift) > 0.10 ? "text-red-400"
                  : Math.abs(h.drift) > 0.05 ? "text-yellow-400" : "text-zinc-400";
                const pnl = h.current_value - (h.cost_basis ?? 0);
                const pnlColor = pnl >= 0 ? "text-emerald-400" : "text-red-400";
                return (
                  <tr key={h.symbol} className="border-t border-zinc-800">
                    <td className="py-2 font-mono text-zinc-200">{h.symbol}</td>
                    <td className="text-zinc-400">{h.sector}</td>
                    <td className="text-right text-zinc-300">${(h.cost_basis ?? 0).toFixed(2)}</td>
                    <td className="text-right text-zinc-300">${h.current_value.toFixed(2)}</td>
                    <td className={`text-right ${pnlColor}`}>${pnl.toFixed(2)}</td>
                    <td className="text-right text-zinc-300">{((h.weight ?? 0) * 100).toFixed(1)}%</td>
                    <td className="text-right text-zinc-500">{((h.target_weight ?? 0) * 100).toFixed(1)}%</td>
                    <td className={`text-right ${driftColor}`}>{((h.drift ?? 0) * 100).toFixed(1)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Buy Schedule */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">Buy Schedule</h2>
        <div className="space-y-2">
          {schedule.map((s) => (
            <div key={s.symbol} className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
              <div className="flex items-center gap-3">
                <span className="font-mono text-zinc-200">{s.symbol}</span>
                <span className="text-xs text-zinc-500">{s.sector}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs text-zinc-500">
                  {s.days_since_buy !== null ? `${s.days_since_buy}d ago` : "Never bought"}
                </span>
                <span className={`text-xs font-medium ${s.due ? "text-emerald-400" : "text-zinc-500"}`}>
                  {s.due ? "DUE" : `Next: ${s.next_buy_date.slice(0, 10)}`}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Rebalance Preview */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wide">Rebalance Preview</h2>
          {status?.days_until_rebalance != null && (
            <span className="text-xs text-zinc-500">{status.days_until_rebalance} days until next rebalance</span>
          )}
        </div>
        {preview.length === 0 ? (
          <div className="text-zinc-500 text-center py-4 text-sm">Portfolio within target weights. No rebalance needed.</div>
        ) : (
          <div className="space-y-2">
            {preview.map((p, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
                <div className="flex items-center gap-3">
                  <span className={`text-xs font-medium ${(p.action ?? p.side) === "buy" ? "text-emerald-400" : "text-red-400"}`}>
                    {(p.action ?? p.side ?? "unknown").toUpperCase()}
                  </span>
                  <span className="font-mono text-zinc-200">{p.symbol}</span>
                </div>
                <div className="text-xs text-zinc-500">
                  {p.reason} · {(p.old_weight * 100).toFixed(1)}% → {(p.new_weight * 100).toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
