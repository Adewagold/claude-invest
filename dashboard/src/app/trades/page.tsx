"use client";

import { useDecisions } from "@/lib/api";
import { DataTable } from "@/components/data-table";
import type { Decision } from "@/lib/types";

const columns = [
  {
    key: "timestamp",
    header: "Time",
    render: (row: Decision) => (
      <span className="text-xs text-zinc-400">
        {new Date(row.timestamp).toLocaleString()}
      </span>
    ),
  },
  {
    key: "ticker",
    header: "Ticker",
    render: (row: Decision) => (
      <span className="font-mono font-medium">{row.ticker}</span>
    ),
  },
  {
    key: "action",
    header: "Action",
    render: (row: Decision) => (
      <span
        className={`px-2 py-0.5 rounded text-xs font-medium uppercase ${
          row.action === "buy"
            ? "bg-emerald-900/50 text-emerald-400"
            : row.action === "sell"
              ? "bg-red-900/50 text-red-400"
              : row.action === "hold"
                ? "bg-blue-900/50 text-blue-400"
                : "bg-zinc-700 text-zinc-400"
        }`}
      >
        {row.action}
      </span>
    ),
  },
  {
    key: "reasoning",
    header: "AI Reasoning",
    render: (row: Decision) => (
      <p className="text-sm text-zinc-300 max-w-xl">{row.reasoning}</p>
    ),
  },
];

export default function TradesPage() {
  const { data: decisions, isLoading } = useDecisions();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Trade Decisions</h1>
      {isLoading ? (
        <div className="text-zinc-500">Loading...</div>
      ) : (
        <DataTable
          columns={columns}
          data={(decisions ?? []) as unknown as Record<string, unknown>[]}
          emptyMessage="No trade decisions yet"
        />
      )}
    </div>
  );
}
