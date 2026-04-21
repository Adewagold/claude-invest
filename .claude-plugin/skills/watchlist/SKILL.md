---
description: Manage the trading watchlist — add, remove, or view tickers you want to monitor for entry signals
argument-hint: <add|remove|show> [symbol] [note]
allowed-tools: Bash, Read
---

# Watchlist

Manage the trading watchlist.

## Commands

### Show watchlist
```bash
cd /Users/adewaleadeleye/projects/claude-invest
.venv/bin/python -m claude_invest.main watchlist
```

### Add a ticker
```bash
.venv/bin/python -m claude_invest.main watchlist-add SYMBOL "optional note"
```

### Remove a ticker
```bash
.venv/bin/python -m claude_invest.main watchlist-remove SYMBOL
```

### Analyze watchlist tickers
For each watchlist ticker not currently held, run:
```bash
.venv/bin/python -m claude_invest.main analyze SYMBOL
```
Report which ones have entry signals (RSI 30-65, MACD above signal, bullish trend).
