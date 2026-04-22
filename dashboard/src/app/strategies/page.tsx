"use client";

import useSWR from "swr";

const API_BASE = "http://localhost:8000";

interface StrategyPerf {
  strategy_id: string;
  name: string;
  description: string;
  capital_pct: number;
  enabled: boolean;
  total_trades: number;
  buys: number;
  sells: number;
  realized_pnl: number;
  decisions_logged: number;
}

function useStrategies() {
  return useSWR<{ strategies: StrategyPerf[] }>(
    "/api/strategies",
    async (url: string) => {
      const res = await fetch(`${API_BASE}${url}`);
      return res.json();
    },
    { refreshInterval: 30000 }
  );
}

export default function StrategiesPage() {
  const { data } = useStrategies();
  const strategies = data?.strategies ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Strategy Performance</h1>

      {strategies.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 text-center text-zinc-500">
          No strategies configured. Add strategies to settings.yaml.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {strategies.map((s) => {
            const pnlColor =
              s.realized_pnl > 0
                ? "text-emerald-400"
                : s.realized_pnl < 0
                  ? "text-red-400"
                  : "text-zinc-400";
            return (
              <div
                key={s.strategy_id}
                className="bg-zinc-900 border border-zinc-800 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-bold text-lg">{s.name}</h3>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      s.enabled
                        ? "bg-emerald-900/50 text-emerald-400"
                        : "bg-zinc-700 text-zinc-400"
                    }`}
                  >
                    {s.enabled ? "ACTIVE" : "OFF"}
                  </span>
                </div>
                <p className="text-xs text-zinc-500 mb-4">{s.description}</p>

                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-zinc-500">Capital</span>
                    <span className="font-mono">
                      {Math.round(s.capital_pct * 100)}%
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-zinc-500">Trades</span>
                    <span className="font-mono">{s.total_trades}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-zinc-500">Buys / Sells</span>
                    <span className="font-mono">
                      {s.buys} / {s.sells}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-zinc-500">Realized P&L</span>
                    <span className={`font-mono font-medium ${pnlColor}`}>
                      ${s.realized_pnl.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-zinc-500">Decisions</span>
                    <span className="font-mono">{s.decisions_logged}</span>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-zinc-800">
                  <div className="w-full bg-zinc-700 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${
                        s.realized_pnl > 0
                          ? "bg-emerald-500"
                          : s.realized_pnl < 0
                            ? "bg-red-500"
                            : "bg-zinc-500"
                      }`}
                      style={{
                        width: `${Math.min(
                          100,
                          Math.max(5, Math.abs(s.realized_pnl) * 2)
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">
          Strategy Parameters
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div>
            <h4 className="font-medium text-zinc-300 mb-1">RSI(2) Mean Reversion</h4>
            <div className="text-zinc-500 space-y-0.5">
              <div>RSI Period: 2</div>
              <div>Buy: RSI &lt; 25</div>
              <div>Sell: RSI &gt; 65 or 5 bars</div>
              <div>Stop: 1% | Target: 2%</div>
              <div>Filter: Above 200 MA</div>
            </div>
          </div>
          <div>
            <h4 className="font-medium text-zinc-300 mb-1">MACD 5/35/5 Trend</h4>
            <div className="text-zinc-500 space-y-0.5">
              <div>MACD: 5/35/5</div>
              <div>Buy: Golden cross + RSI &lt; 40</div>
              <div>Sell: Death cross + RSI &gt; 60</div>
              <div>Stop: 2% | Target: 4%</div>
              <div>Filter: Above 200 MA</div>
            </div>
          </div>
          <div>
            <h4 className="font-medium text-zinc-300 mb-1">Momentum Breakout</h4>
            <div className="text-zinc-500 space-y-0.5">
              <div>RSI: 14 period</div>
              <div>Buy: RSI 30-65 + MACD cross</div>
              <div>Sell: RSI &gt; 80 or -5%</div>
              <div>Stop: 5% | Target: 10%</div>
              <div>Scanner discovery</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
