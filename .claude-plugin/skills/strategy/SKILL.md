---
description: View and manage trading strategies — list active strategies, check performance, switch strategies
argument-hint: [list|performance]
allowed-tools: Bash, Read
---

# Strategy Management

View and manage the multi-strategy trading system.

## Commands

### List strategies and performance
```bash
cd /Users/adewaleadeleye/projects/claude-invest
.venv/bin/python -m claude_invest.main strategies
```

### View strategy config
```bash
cat src/claude_invest/config/settings.yaml | grep -A 20 "strategies:"
```

### Switch strategies
Edit `strategies.active` list in settings.yaml to enable/disable strategies.
Each strategy has `enabled: true/false` and `capital_pct` for allocation.

Present the results as a comparison table showing each strategy's trades, P&L, and win rate.
