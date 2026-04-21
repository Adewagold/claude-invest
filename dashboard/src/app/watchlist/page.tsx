"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";

const API_BASE = "http://localhost:8000";

interface WatchlistEntry {
  symbol: string;
  note: string;
  added: string;
  held?: boolean;
}

function useWatchlist() {
  return useSWR<{ watchlist: WatchlistEntry[]; count: number }>(
    "/api/watchlist",
    async (url: string) => {
      const res = await fetch(`${API_BASE}${url}`);
      return res.json();
    },
    { refreshInterval: 30000 }
  );
}

export default function WatchlistPage() {
  const { data, mutate: refreshList } = useWatchlist();
  const [newSymbol, setNewSymbol] = useState("");
  const [newNote, setNewNote] = useState("");

  const addTicker = async () => {
    if (!newSymbol.trim()) return;
    await fetch(`${API_BASE}/api/watchlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: newSymbol.trim().toUpperCase(), note: newNote.trim() }),
    });
    setNewSymbol("");
    setNewNote("");
    refreshList();
  };

  const removeTicker = async (symbol: string) => {
    await fetch(`${API_BASE}/api/watchlist/${encodeURIComponent(symbol)}`, {
      method: "DELETE",
    });
    refreshList();
  };

  const watchlist = data?.watchlist ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Watchlist</h1>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={newSymbol}
            onChange={(e) => setNewSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addTicker()}
            placeholder="Symbol (e.g. NVDA)"
            className="bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-500 w-32"
          />
          <input
            type="text"
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addTicker()}
            placeholder="Note (optional)"
            className="bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-500 flex-1"
          />
          <button
            onClick={addTicker}
            className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-md text-sm transition-colors"
          >
            Add
          </button>
        </div>
      </div>

      {watchlist.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 text-center text-zinc-500">
          No tickers on your watchlist. Add some above.
        </div>
      ) : (
        <div className="space-y-2">
          {watchlist.map((entry) => (
            <div
              key={entry.symbol}
              className="flex items-center justify-between p-3 bg-zinc-900 border border-zinc-800 rounded-lg"
            >
              <div className="flex items-center gap-3">
                <span className="font-mono font-bold text-lg">{entry.symbol}</span>
                {entry.held && (
                  <span className="px-1.5 py-0.5 rounded text-xs bg-blue-900/50 text-blue-400">
                    HELD
                  </span>
                )}
                {entry.note && (
                  <span className="text-sm text-zinc-400">{entry.note}</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-600">Added {entry.added}</span>
                <button
                  onClick={() => removeTicker(entry.symbol)}
                  className="text-zinc-500 hover:text-red-400 text-sm transition-colors"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="text-xs text-zinc-600">
        {watchlist.length} ticker{watchlist.length !== 1 ? "s" : ""} watched.
        The trading engine analyzes these each cycle and flags entry signals.
      </div>
    </div>
  );
}
