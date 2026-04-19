"use client";

import { useDiscovery } from "@/lib/api";
import { DataTable } from "@/components/data-table";
import type { DiscoveryEntry } from "@/lib/types";

const columns = [
  {
    key: "timestamp",
    header: "Time",
    render: (row: DiscoveryEntry) => (
      <span className="text-xs text-zinc-400">
        {new Date(row.timestamp).toLocaleString()}
      </span>
    ),
  },
  {
    key: "ticker",
    header: "Ticker",
    render: (row: DiscoveryEntry) => (
      <span className="font-mono font-medium">{row.ticker}</span>
    ),
  },
  {
    key: "volume_score",
    header: "Volume",
    align: "right" as const,
    render: (row: DiscoveryEntry) => (
      <span
        className={`font-mono ${
          (row.volume_score ?? 0) >= 2
            ? "text-emerald-400"
            : "text-zinc-400"
        }`}
      >
        {row.volume_score?.toFixed(1) ?? "—"}x
      </span>
    ),
  },
  {
    key: "sentiment",
    header: "Sentiment",
    align: "right" as const,
    render: (row: DiscoveryEntry) => (
      <span
        className={`font-mono ${
          (row.sentiment ?? 0) > 0.3
            ? "text-emerald-400"
            : (row.sentiment ?? 0) < -0.2
              ? "text-red-400"
              : "text-zinc-400"
        }`}
      >
        {row.sentiment?.toFixed(2) ?? "—"}
      </span>
    ),
  },
  {
    key: "action_taken",
    header: "Action",
    render: (row: DiscoveryEntry) => (
      <span
        className={`px-2 py-0.5 rounded text-xs font-medium ${
          row.action_taken === "flagged"
            ? "bg-emerald-900/50 text-emerald-400"
            : "bg-zinc-700 text-zinc-400"
        }`}
      >
        {row.action_taken}
      </span>
    ),
  },
];

export default function DiscoveryPage() {
  const { data: discovery, isLoading } = useDiscovery();

  const flaggedCount = discovery?.filter((d) => d.action_taken === "flagged").length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Discovery</h1>
        <span className="text-sm text-zinc-500">
          {flaggedCount} flagged of {discovery?.length ?? 0} scanned
        </span>
      </div>
      {isLoading ? (
        <div className="text-zinc-500">Loading...</div>
      ) : (
        <DataTable
          columns={columns}
          data={discovery ?? []}
          emptyMessage="No discovery data yet — scanner hasn't run"
        />
      )}
    </div>
  );
}
