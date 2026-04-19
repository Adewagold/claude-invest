interface StatCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  trend?: "up" | "down" | "neutral";
}

export function StatCard({ label, value, subValue, trend }: StatCardProps) {
  const trendColor =
    trend === "up"
      ? "text-emerald-400"
      : trend === "down"
        ? "text-red-400"
        : "text-zinc-400";

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <div className="text-xs text-zinc-500 uppercase tracking-wide mb-1">
        {label}
      </div>
      <div className={`text-2xl font-bold ${trendColor}`}>{value}</div>
      {subValue && (
        <div className="text-xs text-zinc-500 mt-1">{subValue}</div>
      )}
    </div>
  );
}
