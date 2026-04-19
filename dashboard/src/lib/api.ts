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
