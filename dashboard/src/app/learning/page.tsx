"use client";

import {
  useLearningReport,
  useChangeLog,
  useStrategyBrief,
  revertChange,
} from "@/lib/api";
import type { ChangeLogEntry } from "@/lib/types";

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <div className="text-xs text-zinc-500 uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-bold text-zinc-100 mt-1">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

function WinRateBar({ wins, losses, winRate }: { wins: number; losses: number; winRate: number }) {
  const pct = Math.round(winRate * 100);
  const color = pct >= 60 ? "bg-emerald-500" : pct <= 40 ? "bg-red-500" : "bg-yellow-500";
  return (
    <div className="flex items-center gap-2">
      <span className="text-emerald-400 text-xs font-mono">{wins}W</span>
      <span className="text-zinc-600">/</span>
      <span className="text-red-400 text-xs font-mono">{losses}L</span>
      <div className="w-16 bg-zinc-700 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-zinc-400 w-8 text-right">{pct}%</span>
    </div>
  );
}

function DimensionTable({
  title, data, labelKey,
}: {
  title: string;
  data: Array<{ wins: number; losses: number; win_rate: number; avg_pnl: number; total: number; [k: string]: unknown }>;
  labelKey: string;
}) {
  if (!data || data.length === 0) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">{title}</h3>
      <div className="space-y-2">
        {data.map((row, i) => (
          <div key={i} className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
            <span className="text-sm text-zinc-200 font-mono">{String(row[labelKey] ?? "unknown")}</span>
            <div className="flex items-center gap-4">
              <span className="text-xs text-zinc-500">${(row.avg_pnl ?? 0).toFixed(2)} avg</span>
              <WinRateBar wins={row.wins} losses={row.losses} winRate={row.win_rate} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChangeTimeline({ changes }: { changes: ChangeLogEntry[] }) {
  if (!changes || changes.length === 0) {
    return (
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">Parameter Changes</h3>
        <div className="text-zinc-500 text-center py-4 text-sm">No parameter changes yet.</div>
      </div>
    );
  }

  const handleRevert = async (id: number) => {
    await revertChange(id);
    window.location.reload();
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <h3 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">Parameter Changes</h3>
      <div className="space-y-2">
        {changes.map((c) => {
          const statusColor = c.reverted ? "text-red-400" : c.auto_applied ? "text-emerald-400" : "text-yellow-400";
          const statusLabel = c.reverted ? "Reverted" : c.auto_applied ? "Active" : "Proposed";
          return (
            <div key={c.id} className="p-3 bg-zinc-800/50 rounded">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-mono text-sm text-zinc-200">{c.parameter_path.split(".").slice(-1)}</span>
                  <span className="text-zinc-500 mx-2">:</span>
                  <span className="text-zinc-300 text-sm">{c.old_value} → {c.new_value}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium ${statusColor}`}>{statusLabel}</span>
                  {!c.reverted && c.auto_applied && (
                    <button onClick={() => handleRevert(c.id)} className="text-xs text-zinc-500 hover:text-red-400 transition">Revert</button>
                  )}
                </div>
              </div>
              <div className="text-xs text-zinc-500 mt-1">{c.reason}</div>
              <div className="text-xs text-zinc-600 mt-1">{c.timestamp} · {c.trade_count} trades</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function LearningPage() {
  const { data: report } = useLearningReport();
  const { data: changesData } = useChangeLog();
  const { data: brief } = useStrategyBrief();
  const changes = changesData?.changes ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Learning Engine</h1>
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Win Rate" value={report ? `${Math.round(report.overall_win_rate * 100)}%` : "—"} sub={report ? `${report.total_trades} trades` : undefined} />
        <StatCard label="Total Trades" value={report ? String(report.total_trades) : "—"} />
        <StatCard label="Active Changes" value={String(changes.filter((c) => c.auto_applied && !c.reverted).length)} />
        <StatCard label="Proposed" value={String(changes.filter((c) => !c.auto_applied && !c.reverted).length)} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <DimensionTable title="Time of Day" data={report?.time_of_day ?? []} labelKey="bucket" />
        <DimensionTable title="Hold Duration" data={report?.hold_duration ?? []} labelKey="bucket" />
        <DimensionTable title="Market Regime" data={report?.market_regime ?? []} labelKey="regime" />
        <DimensionTable title="Asset Class × Strategy" data={report?.asset_class ?? []} labelKey="asset_class" />
      </div>
      <DimensionTable title="Signal Combinations" data={report?.signal_combos ?? []} labelKey="combo" />
      <ChangeTimeline changes={changes} />
      {brief && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">Strategy Brief</h3>
          <pre className="text-sm text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed">{brief.brief}</pre>
        </div>
      )}
    </div>
  );
}
