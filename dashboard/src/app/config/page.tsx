"use client";

import { useState, useEffect } from "react";
import { useConfig, updateConfig } from "@/lib/api";
import type { Config } from "@/lib/types";

function ConfigField({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string | number | boolean;
  onChange: (val: string) => void;
  type?: string;
}) {
  if (typeof value === "boolean") {
    return (
      <div className="flex items-center justify-between py-2">
        <label className="text-sm text-zinc-300">{label}</label>
        <button
          onClick={() => onChange(String(!value))}
          className={`w-10 h-5 rounded-full transition-colors ${
            value ? "bg-emerald-600" : "bg-zinc-700"
          }`}
        >
          <div
            className={`w-4 h-4 rounded-full bg-white transform transition-transform ${
              value ? "translate-x-5" : "translate-x-0.5"
            }`}
          />
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between py-2">
      <label className="text-sm text-zinc-300">{label}</label>
      <input
        type={type}
        value={String(value)}
        onChange={(e) => onChange(e.target.value)}
        className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1 text-sm text-white w-32 text-right focus:outline-none focus:border-zinc-500"
      />
    </div>
  );
}

export default function ConfigPage() {
  const { data: config, mutate } = useConfig();
  const [editing, setEditing] = useState<Config | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (config && !editing) setEditing(structuredClone(config));
  }, [config]);

  if (!editing) return <div className="text-zinc-500">Loading config...</div>;

  const handleSave = async () => {
    setSaving(true);
    await updateConfig(editing);
    await mutate();
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const update = (path: string, value: string) => {
    const next = structuredClone(editing);
    const keys = path.split(".");
    let obj: Record<string, unknown> = next as unknown as Record<string, unknown>;
    for (let i = 0; i < keys.length - 1; i++) {
      obj = obj[keys[i]] as Record<string, unknown>;
    }
    const lastKey = keys[keys.length - 1];
    const current = obj[lastKey];
    if (typeof current === "boolean") {
      obj[lastKey] = value === "true";
    } else if (typeof current === "number") {
      obj[lastKey] = Number(value);
    } else {
      obj[lastKey] = value;
    }
    setEditing(next);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Configuration</h1>
        <div className="flex items-center gap-3">
          {saved && (
            <span className="text-emerald-400 text-sm">Saved!</span>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-md text-sm transition-colors disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">
          General
        </h2>
        <ConfigField label="Mode" value={editing.mode} onChange={(v) => update("mode", v)} />
        <ConfigField label="Capital ($)" value={editing.capital} onChange={(v) => update("capital", v)} type="number" />
        <ConfigField label="Max Positions" value={editing.max_positions} onChange={(v) => update("max_positions", v)} type="number" />
        <ConfigField label="Max Per Ticker (%)" value={editing.max_per_ticker} onChange={(v) => update("max_per_ticker", v)} type="number" />
        <ConfigField label="Position Size (%)" value={editing.position_size_pct} onChange={(v) => update("position_size_pct", v)} type="number" />
        <ConfigField label="Daily Loss Limit ($)" value={editing.daily_loss_limit} onChange={(v) => update("daily_loss_limit", v)} type="number" />
        <ConfigField label="PDT Tracking" value={editing.pdt_tracking} onChange={(v) => update("pdt_tracking", v)} />
        <ConfigField label="Trading Style" value={editing.trading_style} onChange={(v) => update("trading_style", v)} />
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">
          Exit Strategy
        </h2>
        <ConfigField label="Stop Loss (%)" value={editing.exit_strategy.stop_loss_pct} onChange={(v) => update("exit_strategy.stop_loss_pct", v)} type="number" />
        <ConfigField label="Trailing Stop (%)" value={editing.exit_strategy.trailing_stop_pct} onChange={(v) => update("exit_strategy.trailing_stop_pct", v)} type="number" />
        <ConfigField label="Signal-Based Exit" value={editing.exit_strategy.signal_exit} onChange={(v) => update("exit_strategy.signal_exit", v)} />
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">
          Discovery Thresholds
        </h2>
        <ConfigField label="Min Relative Volume" value={editing.discovery.min_relative_volume} onChange={(v) => update("discovery.min_relative_volume", v)} type="number" />
        <ConfigField label="Min News Count" value={editing.discovery.min_news_count} onChange={(v) => update("discovery.min_news_count", v)} type="number" />
        <ConfigField label="Sentiment Threshold" value={editing.discovery.sentiment_threshold} onChange={(v) => update("discovery.sentiment_threshold", v)} type="number" />
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">
          Polling Intervals (minutes)
        </h2>
        <ConfigField label="Market Open" value={editing.polling.market_open_interval} onChange={(v) => update("polling.market_open_interval", v)} type="number" />
        <ConfigField label="Market Close" value={editing.polling.market_close_interval} onChange={(v) => update("polling.market_close_interval", v)} type="number" />
        <ConfigField label="Midday" value={editing.polling.midday_interval} onChange={(v) => update("polling.midday_interval", v)} type="number" />
        <ConfigField label="Crypto" value={editing.polling.crypto_interval} onChange={(v) => update("polling.crypto_interval", v)} type="number" />
      </div>
    </div>
  );
}
