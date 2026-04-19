# Claude Invest Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Next.js monitoring dashboard that displays real-time trading data from the Claude Invest Python backend.

**Architecture:** Next.js App Router app consuming REST APIs from FastAPI backend at `http://localhost:8000`. SWR for data fetching with auto-refresh. TradingView Lightweight Charts for portfolio/price visualization. All pages are read-only except the config editor.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS 4, SWR, lightweight-charts (TradingView), shadcn/ui components

---

## File Structure

```
dashboard/
├── package.json
├── tsconfig.json
├── next.config.ts
├── tailwind.config.ts
├── postcss.config.mjs
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root layout with nav sidebar
│   │   ├── page.tsx                # Overview dashboard
│   │   ├── globals.css             # Tailwind imports + custom styles
│   │   ├── trades/
│   │   │   └── page.tsx            # Trade history
│   │   ├── signals/
│   │   │   └── page.tsx            # Signal dashboard
│   │   ├── discovery/
│   │   │   └── page.tsx            # Discovery feed
│   │   ├── positions/
│   │   │   └── page.tsx            # Open positions detail
│   │   └── config/
│   │       └── page.tsx            # Config editor
│   ├── components/
│   │   ├── nav.tsx                 # Sidebar navigation
│   │   ├── portfolio-chart.tsx     # TradingView chart wrapper
│   │   ├── stat-card.tsx           # Reusable stat display card
│   │   ├── signal-badge.tsx        # Color-coded signal indicator
│   │   └── data-table.tsx          # Reusable sortable table
│   └── lib/
│       ├── api.ts                  # SWR hooks + fetch helpers
│       └── types.ts                # TypeScript types matching API
```

---

### Task 1: Scaffold Next.js Project

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/tsconfig.json`
- Create: `dashboard/next.config.ts`
- Create: `dashboard/src/app/layout.tsx`
- Create: `dashboard/src/app/page.tsx`
- Create: `dashboard/src/app/globals.css`

- [ ] **Step 1: Create Next.js app**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
npx create-next-app@latest dashboard --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm --yes
```

- [ ] **Step 2: Install dependencies**

```bash
cd /Users/adewaleadeleye/projects/claude-invest/dashboard
npm install swr lightweight-charts
```

- [ ] **Step 3: Verify dev server starts**

```bash
cd /Users/adewaleadeleye/projects/claude-invest/dashboard
npm run dev
```

Expected: Server starts at `http://localhost:3000`, default Next.js page loads.

- [ ] **Step 4: Commit**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
git add dashboard/
git commit -m "feat: scaffold Next.js dashboard with dependencies"
```

---

### Task 2: TypeScript Types & API Layer

**Files:**
- Create: `dashboard/src/lib/types.ts`
- Create: `dashboard/src/lib/api.ts`

- [ ] **Step 1: Create TypeScript types**

`dashboard/src/lib/types.ts`:
```typescript
export interface Position {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pl: number;
  market_value: number;
}

export interface Portfolio {
  equity: number;
  cash: number;
  buying_power: number;
  daily_pnl: number;
  positions: Position[];
  position_count: number;
}

export interface Trade {
  id: number;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  timestamp: string;
  order_id: string;
  trade_type: string;
  status: string;
}

export interface Decision {
  id: number;
  timestamp: string;
  ticker: string;
  action: string;
  reasoning: string;
  signals_snapshot: string;
}

export interface Signal {
  id: number;
  ticker: string;
  timestamp: string;
  sentiment_score: number | null;
  rsi: number | null;
  macd: number | null;
  volume_ratio: number | null;
  trend: string | null;
}

export interface DiscoveryEntry {
  id: number;
  timestamp: string;
  ticker: string;
  volume_score: number | null;
  news_score: number | null;
  sentiment: number | null;
  action_taken: string;
}

export interface PortfolioSnapshot {
  id: number;
  timestamp: string;
  total_value: number;
  cash: number;
  positions_value: number;
  daily_pnl: number | null;
}

export interface Stats {
  latest_value: number;
  latest_daily_pnl: number;
  total_snapshots: number;
}

export interface Config {
  mode: string;
  capital: number;
  max_positions: number;
  max_per_ticker: number;
  position_size_pct: number;
  daily_loss_limit: number;
  pdt_tracking: boolean;
  exit_strategy: {
    stop_loss_pct: number;
    trailing_stop_pct: number;
    signal_exit: boolean;
  };
  polling: {
    market_open_interval: number;
    market_close_interval: number;
    midday_interval: number;
    crypto_interval: number;
  };
  discovery: {
    min_relative_volume: number;
    min_news_count: number;
    sentiment_threshold: number;
  };
  trading_style: string;
}
```

- [ ] **Step 2: Create API layer with SWR hooks**

`dashboard/src/lib/api.ts`:
```typescript
import useSWR from "swr";
import type {
  Trade,
  Decision,
  Signal,
  DiscoveryEntry,
  PortfolioSnapshot,
  Stats,
  Config,
} from "./types";

const API_BASE = "http://localhost:8000";

async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export function useTrades(limit = 100) {
  return useSWR<Trade[]>(`/api/trades?limit=${limit}`, fetcher, {
    refreshInterval: 30000,
  });
}

export function useDecisions(limit = 50) {
  return useSWR<Decision[]>(`/api/decisions?limit=${limit}`, fetcher, {
    refreshInterval: 30000,
  });
}

export function useSignals(ticker: string) {
  return useSWR<Signal[]>(`/api/signals/${ticker}`, fetcher, {
    refreshInterval: 15000,
  });
}

export function useDiscovery(limit = 50) {
  return useSWR<DiscoveryEntry[]>(`/api/discovery?limit=${limit}`, fetcher, {
    refreshInterval: 30000,
  });
}

export function usePortfolioSnapshots(limit = 100) {
  return useSWR<PortfolioSnapshot[]>(`/api/portfolio?limit=${limit}`, fetcher, {
    refreshInterval: 30000,
  });
}

export function useStats() {
  return useSWR<Stats>("/api/stats", fetcher, {
    refreshInterval: 15000,
  });
}

export function useConfig() {
  return useSWR<Config>("/api/config", fetcher);
}

export async function updateConfig(config: Config): Promise<void> {
  await fetch(`${API_BASE}/api/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
git add dashboard/src/lib/
git commit -m "feat: add TypeScript types and SWR API hooks"
```

---

### Task 3: Navigation & Layout

**Files:**
- Create: `dashboard/src/components/nav.tsx`
- Modify: `dashboard/src/app/layout.tsx`
- Modify: `dashboard/src/app/globals.css`

- [ ] **Step 1: Create navigation component**

`dashboard/src/components/nav.tsx`:
```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Overview", icon: "📊" },
  { href: "/positions", label: "Positions", icon: "💼" },
  { href: "/trades", label: "Trades", icon: "📋" },
  { href: "/signals", label: "Signals", icon: "📡" },
  { href: "/discovery", label: "Discovery", icon: "🔍" },
  { href: "/config", label: "Config", icon: "⚙️" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="w-56 min-h-screen bg-zinc-900 border-r border-zinc-800 p-4 flex flex-col gap-1">
      <div className="text-lg font-bold text-white mb-6 px-3">
        Claude Invest
      </div>
      {links.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
              active
                ? "bg-zinc-800 text-white"
                : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
            }`}
          >
            <span>{link.icon}</span>
            <span>{link.label}</span>
          </Link>
        );
      })}
      <div className="mt-auto px-3 py-2 text-xs text-zinc-600">
        Paper Trading
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: Update root layout**

`dashboard/src/app/layout.tsx`:
```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Claude Invest",
  description: "AI-powered trading dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-zinc-950 text-zinc-100`}>
        <div className="flex">
          <Nav />
          <main className="flex-1 p-6 overflow-auto min-h-screen">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Update globals.css**

Replace the contents of `dashboard/src/app/globals.css` with:
```css
@import "tailwindcss";

:root {
  --foreground: #fafafa;
  --background: #09090b;
}

body {
  color: var(--foreground);
  background: var(--background);
}
```

- [ ] **Step 4: Verify layout renders**

Start the dev server and check `http://localhost:3000`. You should see a dark sidebar with navigation links and an empty main area.

```bash
cd /Users/adewaleadeleye/projects/claude-invest/dashboard
npm run dev
```

- [ ] **Step 5: Commit**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
git add dashboard/src/components/nav.tsx dashboard/src/app/layout.tsx dashboard/src/app/globals.css
git commit -m "feat: add dark sidebar navigation and root layout"
```

---

### Task 4: Reusable Components

**Files:**
- Create: `dashboard/src/components/stat-card.tsx`
- Create: `dashboard/src/components/signal-badge.tsx`
- Create: `dashboard/src/components/data-table.tsx`

- [ ] **Step 1: Create stat card component**

`dashboard/src/components/stat-card.tsx`:
```tsx
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
```

- [ ] **Step 2: Create signal badge component**

`dashboard/src/components/signal-badge.tsx`:
```tsx
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
```

- [ ] **Step 3: Create data table component**

`dashboard/src/components/data-table.tsx`:
```tsx
interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => React.ReactNode;
  align?: "left" | "right" | "center";
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  emptyMessage?: string;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  emptyMessage = "No data",
}: DataTableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="text-center text-zinc-500 py-12 bg-zinc-900 rounded-lg border border-zinc-800">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-zinc-900 border-b border-zinc-800">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-4 py-3 font-medium text-zinc-400 text-xs uppercase tracking-wide ${
                  col.align === "right" ? "text-right" : "text-left"
                }`}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={i}
              className="border-b border-zinc-800/50 hover:bg-zinc-900/50 transition-colors"
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`px-4 py-3 ${
                    col.align === "right" ? "text-right" : "text-left"
                  }`}
                >
                  {col.render
                    ? col.render(row)
                    : String(row[col.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
git add dashboard/src/components/
git commit -m "feat: add stat-card, signal-badge, and data-table components"
```

---

### Task 5: Overview Page

**Files:**
- Modify: `dashboard/src/app/page.tsx`
- Create: `dashboard/src/components/portfolio-chart.tsx`

- [ ] **Step 1: Create portfolio chart component**

`dashboard/src/components/portfolio-chart.tsx`:
```tsx
"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, type IChartApi } from "lightweight-charts";
import type { PortfolioSnapshot } from "@/lib/types";

interface PortfolioChartProps {
  snapshots: PortfolioSnapshot[];
}

export function PortfolioChart({ snapshots }: PortfolioChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current || snapshots.length === 0) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#a1a1aa",
      },
      grid: {
        vertLines: { color: "#27272a" },
        horzLines: { color: "#27272a" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 300,
      timeScale: {
        timeVisible: true,
        borderColor: "#27272a",
      },
      rightPriceScale: {
        borderColor: "#27272a",
      },
    });

    const series = chart.addAreaSeries({
      lineColor: "#10b981",
      topColor: "rgba(16, 185, 129, 0.3)",
      bottomColor: "rgba(16, 185, 129, 0.0)",
      lineWidth: 2,
    });

    const data = snapshots
      .slice()
      .reverse()
      .map((s) => ({
        time: s.timestamp.replace(" ", "T") as unknown as number,
        value: s.total_value,
      }));

    series.setData(data);
    chart.timeScale().fitContent();
    chartRef.current = chart;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [snapshots]);

  return <div ref={chartContainerRef} className="w-full" />;
}
```

- [ ] **Step 2: Build the overview page**

`dashboard/src/app/page.tsx`:
```tsx
"use client";

import { usePortfolioSnapshots, useStats, useDecisions } from "@/lib/api";
import { StatCard } from "@/components/stat-card";
import { PortfolioChart } from "@/components/portfolio-chart";

export default function OverviewPage() {
  const { data: snapshots } = usePortfolioSnapshots();
  const { data: stats } = useStats();
  const { data: decisions } = useDecisions(10);

  const latestSnapshot = snapshots?.[0];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Overview</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Portfolio Value"
          value={
            latestSnapshot
              ? `$${latestSnapshot.total_value.toLocaleString()}`
              : "—"
          }
        />
        <StatCard
          label="Daily P&L"
          value={
            latestSnapshot
              ? `$${(latestSnapshot.daily_pnl ?? 0).toFixed(2)}`
              : "—"
          }
          trend={
            (latestSnapshot?.daily_pnl ?? 0) > 0
              ? "up"
              : (latestSnapshot?.daily_pnl ?? 0) < 0
                ? "down"
                : "neutral"
          }
        />
        <StatCard
          label="Cash"
          value={
            latestSnapshot
              ? `$${latestSnapshot.cash.toLocaleString()}`
              : "—"
          }
        />
        <StatCard
          label="Positions Value"
          value={
            latestSnapshot
              ? `$${latestSnapshot.positions_value.toLocaleString()}`
              : "—"
          }
        />
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-4">
          Portfolio Value Over Time
        </h2>
        {snapshots && snapshots.length > 0 ? (
          <PortfolioChart snapshots={snapshots} />
        ) : (
          <div className="text-zinc-500 text-center py-12">
            No portfolio data yet
          </div>
        )}
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-medium text-zinc-400 mb-4">
          Recent Decisions
        </h2>
        {decisions && decisions.length > 0 ? (
          <div className="space-y-3">
            {decisions.map((d) => (
              <div
                key={d.id}
                className="flex items-start gap-3 p-3 bg-zinc-800/50 rounded-md"
              >
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium uppercase ${
                    d.action === "buy"
                      ? "bg-emerald-900/50 text-emerald-400"
                      : d.action === "sell"
                        ? "bg-red-900/50 text-red-400"
                        : d.action === "hold"
                          ? "bg-blue-900/50 text-blue-400"
                          : "bg-zinc-700 text-zinc-400"
                  }`}
                >
                  {d.action}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-medium">{d.ticker}</span>
                    <span className="text-xs text-zinc-500">
                      {new Date(d.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm text-zinc-400 mt-1 line-clamp-2">
                    {d.reasoning}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-zinc-500 text-center py-8">
            No decisions yet
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Start FastAPI backend and verify**

```bash
# Terminal 1: Start Python API
cd /Users/adewaleadeleye/projects/claude-invest
source .venv/bin/activate && .venv/bin/python -m claude_invest.modules.api_server

# Terminal 2: Start Next.js dashboard
cd /Users/adewaleadeleye/projects/claude-invest/dashboard
npm run dev
```

Visit `http://localhost:3000`. You should see the overview with portfolio stats, a chart, and recent decisions.

- [ ] **Step 4: Commit**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
git add dashboard/src/app/page.tsx dashboard/src/components/portfolio-chart.tsx
git commit -m "feat: add overview page with portfolio chart and recent decisions"
```

---

### Task 6: Trades Page

**Files:**
- Create: `dashboard/src/app/trades/page.tsx`

- [ ] **Step 1: Build trades page**

`dashboard/src/app/trades/page.tsx`:
```tsx
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
          data={decisions ?? []}
          emptyMessage="No trade decisions yet"
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Visit `http://localhost:3000/trades`. You should see the trade decisions table with AI reasoning.

- [ ] **Step 3: Commit**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
git add dashboard/src/app/trades/
git commit -m "feat: add trades page with decision history and AI reasoning"
```

---

### Task 7: Signals Page

**Files:**
- Create: `dashboard/src/app/signals/page.tsx`

- [ ] **Step 1: Build signals page**

`dashboard/src/app/signals/page.tsx`:
```tsx
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
```

- [ ] **Step 2: Verify in browser**

Visit `http://localhost:3000/signals`. You should see signal cards for each ticker with color-coded badges.

- [ ] **Step 3: Commit**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
git add dashboard/src/app/signals/
git commit -m "feat: add signals page with color-coded signal badges per ticker"
```

---

### Task 8: Discovery Page

**Files:**
- Create: `dashboard/src/app/discovery/page.tsx`

- [ ] **Step 1: Build discovery page**

`dashboard/src/app/discovery/page.tsx`:
```tsx
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
```

- [ ] **Step 2: Verify in browser**

Visit `http://localhost:3000/discovery`. You should see the discovery table with color-coded volume and sentiment.

- [ ] **Step 3: Commit**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
git add dashboard/src/app/discovery/
git commit -m "feat: add discovery page with scanner results feed"
```

---

### Task 9: Positions Page

**Files:**
- Create: `dashboard/src/app/positions/page.tsx`

- [ ] **Step 1: Build positions page**

`dashboard/src/app/positions/page.tsx`:
```tsx
"use client";

import { usePortfolioSnapshots, useSignals } from "@/lib/api";
import { StatCard } from "@/components/stat-card";
import { SignalBadge } from "@/components/signal-badge";

// We read positions from the latest portfolio snapshot's context.
// Since the snapshot doesn't store individual positions, we fetch live
// from the /api/portfolio endpoint which returns the account state.
import useSWR from "swr";
import type { Portfolio } from "@/lib/types";

const API_BASE = "http://localhost:8000";

function PositionCard({ position }: { position: Portfolio["positions"][0] }) {
  const { data: signals } = useSignals(position.symbol);
  const latest = signals?.[0];
  const plPercent = ((position.current_price - position.avg_entry_price) / position.avg_entry_price * 100).toFixed(2);
  const isUp = position.unrealized_pl >= 0;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono font-bold text-lg">{position.symbol}</span>
        <span className={`font-mono font-medium ${isUp ? "text-emerald-400" : "text-red-400"}`}>
          {isUp ? "+" : ""}${position.unrealized_pl.toFixed(2)} ({plPercent}%)
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm mb-3">
        <div>
          <span className="text-zinc-500">Qty:</span>{" "}
          <span className="font-mono">{position.qty}</span>
        </div>
        <div>
          <span className="text-zinc-500">Entry:</span>{" "}
          <span className="font-mono">${position.avg_entry_price.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-zinc-500">Current:</span>{" "}
          <span className="font-mono">${position.current_price.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-zinc-500">Value:</span>{" "}
          <span className="font-mono">${position.market_value.toFixed(2)}</span>
        </div>
      </div>
      {latest && (
        <div className="flex flex-wrap gap-2 pt-3 border-t border-zinc-800">
          <SignalBadge label="RSI" value={latest.rsi?.toFixed(1) ?? null} type="rsi" />
          <SignalBadge label="Trend" value={latest.trend} type="trend" />
          <SignalBadge label="Sent" value={latest.sentiment_score?.toFixed(2) ?? null} type="sentiment" />
        </div>
      )}
    </div>
  );
}

export default function PositionsPage() {
  const { data: portfolio } = useSWR<Portfolio>(
    "/api/portfolio-live",
    async () => {
      // This fetches live from Alpaca via our CLI
      // Fall back to snapshot data if live isn't available
      try {
        const res = await fetch(`${API_BASE}/api/portfolio`);
        const snapshots = await res.json();
        // Return a mock portfolio structure from latest snapshot
        return null;
      } catch {
        return null;
      }
    }
  );

  const { data: snapshots } = usePortfolioSnapshots(1);
  const latest = snapshots?.[0];

  // For positions, we'll display from the decisions/signals data
  // since the snapshot API doesn't include individual positions
  // In production, you'd add a /api/positions endpoint
  // For now, show a summary view

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Positions</h1>

      {latest && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Value" value={`$${latest.total_value.toLocaleString()}`} />
          <StatCard label="Cash" value={`$${latest.cash.toLocaleString()}`} />
          <StatCard label="Positions Value" value={`$${latest.positions_value.toLocaleString()}`} />
          <StatCard
            label="Daily P&L"
            value={`$${(latest.daily_pnl ?? 0).toFixed(2)}`}
            trend={(latest.daily_pnl ?? 0) > 0 ? "up" : (latest.daily_pnl ?? 0) < 0 ? "down" : "neutral"}
          />
        </div>
      )}

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 text-center">
        <p className="text-zinc-400 mb-2">
          Live positions are fetched from Alpaca when the trading engine runs.
        </p>
        <p className="text-zinc-500 text-sm">
          Check the Overview page for the latest portfolio state, or run the CLI:
        </p>
        <code className="text-xs text-zinc-400 bg-zinc-800 px-3 py-1.5 rounded mt-2 inline-block">
          .venv/bin/python -m claude_invest.main portfolio
        </code>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Visit `http://localhost:3000/positions`. You should see portfolio stats and a note about live positions.

- [ ] **Step 3: Commit**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
git add dashboard/src/app/positions/
git commit -m "feat: add positions page with portfolio summary"
```

---

### Task 10: Config Page

**Files:**
- Create: `dashboard/src/app/config/page.tsx`

- [ ] **Step 1: Build config editor page**

`dashboard/src/app/config/page.tsx`:
```tsx
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
```

- [ ] **Step 2: Verify in browser**

Visit `http://localhost:3000/config`. You should see all config sections with editable fields. Try changing a value and clicking Save.

- [ ] **Step 3: Commit**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
git add dashboard/src/app/config/
git commit -m "feat: add config editor page with live save"
```

---

### Task 11: Final Polish & Verification

**Files:**
- No new files — verify all pages work end-to-end

- [ ] **Step 1: Start both servers**

```bash
# Terminal 1: Python API backend
cd /Users/adewaleadeleye/projects/claude-invest
source .venv/bin/activate && .venv/bin/python -m claude_invest.modules.api_server

# Terminal 2: Next.js dashboard
cd /Users/adewaleadeleye/projects/claude-invest/dashboard
npm run dev
```

- [ ] **Step 2: Verify each page**

Visit each page and confirm it renders data:
- `http://localhost:3000/` — Portfolio stats, chart, recent decisions
- `http://localhost:3000/trades` — Decision history table
- `http://localhost:3000/signals` — Signal cards per ticker
- `http://localhost:3000/discovery` — Scanner results table
- `http://localhost:3000/positions` — Portfolio summary
- `http://localhost:3000/config` — Editable config with save

- [ ] **Step 3: Test config save round-trip**

On the config page:
1. Change `capital` from 5000 to 5500
2. Click Save
3. Refresh the page
4. Verify `capital` shows 5500
5. Change it back to 5000 and save

- [ ] **Step 4: Build check**

```bash
cd /Users/adewaleadeleye/projects/claude-invest/dashboard
npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 5: Final commit**

```bash
cd /Users/adewaleadeleye/projects/claude-invest
git add dashboard/
git commit -m "chore: verify dashboard end-to-end and build passes"
```
