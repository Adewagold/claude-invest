"use client";

import { useState } from "react";
import { useSignals } from "@/lib/api";
import { SignalBadge } from "@/components/signal-badge";

const WATCHED_TICKERS = ["AAPL", "NVDA", "TSLA", "PFE", "BTC/USD", "ETH/USD"];

function TickerSignals({ ticker }: { ticker: string }) {
  const { data: signals } = useSignals(ticker);
  const latest = signals?.[0];

  if (!latest) {
    return (
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <div className="font-mono font-medium mb-3">{ticker}</div>
        <div className="text-zinc-500 text-sm">No signal data</div>
      </div>
    );
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono font-medium text-lg">{ticker}</span>
        <span className="text-xs text-zinc-500">
          {new Date(latest.timestamp).toLocaleString()}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        <SignalBadge
          label="Sentiment"
          value={latest.sentiment_score?.toFixed(2) ?? null}
          type="sentiment"
        />
        <SignalBadge
          label="RSI"
          value={latest.rsi?.toFixed(1) ?? null}
          type="rsi"
        />
        <SignalBadge
          label="MACD"
          value={latest.macd?.toFixed(4) ?? null}
        />
        <SignalBadge
          label="Volume"
          value={
            latest.volume_ratio
              ? `${latest.volume_ratio.toFixed(1)}x`
              : null
          }
        />
        <SignalBadge
          label="Trend"
          value={latest.trend}
          type="trend"
        />
      </div>
    </div>
  );
}

export default function SignalsPage() {
  const [customTicker, setCustomTicker] = useState("");
  const [tickers, setTickers] = useState(WATCHED_TICKERS);

  const addTicker = () => {
    const t = customTicker.trim().toUpperCase();
    if (t && !tickers.includes(t)) {
      setTickers([...tickers, t]);
      setCustomTicker("");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Signals</h1>
        <div className="flex gap-2">
          <input
            type="text"
            value={customTicker}
            onChange={(e) => setCustomTicker(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addTicker()}
            placeholder="Add ticker..."
            className="bg-zinc-800 border border-zinc-700 rounded-md px-3 py-1.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-500"
          />
          <button
            onClick={addTicker}
            className="bg-zinc-800 border border-zinc-700 rounded-md px-3 py-1.5 text-sm hover:bg-zinc-700 transition-colors"
          >
            Add
          </button>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {tickers.map((ticker) => (
          <TickerSignals key={ticker} ticker={ticker} />
        ))}
      </div>
    </div>
  );
}
