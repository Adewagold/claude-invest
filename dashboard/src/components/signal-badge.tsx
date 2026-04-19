interface SignalBadgeProps {
  label: string;
  value: number | string | null;
  type?: "sentiment" | "rsi" | "trend" | "default";
}

function getColor(type: string, value: number | string | null): string {
  if (value === null) return "bg-zinc-700 text-zinc-400";

  if (type === "sentiment") {
    const v = Number(value);
    if (v > 0.3) return "bg-emerald-900/50 text-emerald-400 border-emerald-800";
    if (v < -0.2) return "bg-red-900/50 text-red-400 border-red-800";
    return "bg-zinc-800 text-zinc-300 border-zinc-700";
  }

  if (type === "rsi") {
    const v = Number(value);
    if (v > 70) return "bg-red-900/50 text-red-400 border-red-800";
    if (v < 30) return "bg-emerald-900/50 text-emerald-400 border-emerald-800";
    return "bg-zinc-800 text-zinc-300 border-zinc-700";
  }

  if (type === "trend") {
    if (value === "bullish") return "bg-emerald-900/50 text-emerald-400 border-emerald-800";
    if (value === "bearish") return "bg-red-900/50 text-red-400 border-red-800";
    return "bg-zinc-800 text-zinc-300 border-zinc-700";
  }

  return "bg-zinc-800 text-zinc-300 border-zinc-700";
}

export function SignalBadge({ label, value, type = "default" }: SignalBadgeProps) {
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md border text-sm ${getColor(type, value)}`}>
      <span className="text-zinc-500 text-xs">{label}</span>
      <span className="font-mono font-medium">
        {value !== null ? String(value) : "N/A"}
      </span>
    </div>
  );
}
