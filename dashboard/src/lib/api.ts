import useSWR from "swr";
import type {
  Trade,
  Decision,
  Signal,
  DiscoveryEntry,
  PortfolioSnapshot,
  Portfolio,
  Stats,
  Config,
  LearningReport,
  ChangeLogEntry,
  PerformanceSeries,
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

export function usePositions() {
  return useSWR<Portfolio>("/api/positions", fetcher, {
    refreshInterval: 15000,
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

export function useLessons() {
  return useSWR<{ patterns: Array<{ signal_combo: string; wins: number; losses: number; total: number; win_rate: number; avg_pnl: number; confidence: string }>; last_updated: string | null }>("/api/lessons", fetcher, { refreshInterval: 60000 });
}

export function useAllocation() {
  return useSWR<{
    total_value: number;
    tiers: Record<string, { target: number; actual: number; drift: number; value: number; alert: boolean }>;
    sectors: Record<string, { value: number; positions: string[]; pct: number }>;
    positions?: Array<{ symbol: string; tier: string; [key: string]: unknown }>;
  }>("/api/allocation", fetcher, { refreshInterval: 30000 });
}

export function useStrategyBrief() {
  return useSWR<{ brief: string }>("/api/strategy-brief", fetcher, { refreshInterval: 60000 });
}

export function useLearningReport() {
  return useSWR<LearningReport>("/api/learning/report", fetcher, {
    refreshInterval: 60000,
  });
}

export function useChangeLog() {
  return useSWR<{ changes: ChangeLogEntry[] }>("/api/learning/changes", fetcher, {
    refreshInterval: 30000,
  });
}

export function usePerformanceSeries() {
  return useSWR<{ series: PerformanceSeries[] }>("/api/learning/performance", fetcher, {
    refreshInterval: 60000,
  });
}

export async function revertChange(changeId: number): Promise<void> {
  await fetch(`${API_BASE}/api/learning/revert/${changeId}`, { method: "POST" });
}
