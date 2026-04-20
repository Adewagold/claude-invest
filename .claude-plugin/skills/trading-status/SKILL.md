---
description: Check the status of the Claude Invest trading engine — active crons, server status, portfolio state
argument-hint: (no arguments needed)
allowed-tools: Bash, CronList, Read
---

# Trading Status

Check the current state of the Claude Invest trading engine.

## Steps

### 1. Check Crons
Run CronList and report how many trading crons are active and their schedules.

### 2. Check Servers
```bash
lsof -ti:8000 > /dev/null 2>&1 && echo "FastAPI: running on port 8000" || echo "FastAPI: NOT running"
lsof -ti:3000 > /dev/null 2>&1 && echo "Dashboard: running on port 3000" || echo "Dashboard: NOT running"
```

### 3. Quick Portfolio Check
```bash
cd /Users/adewaleadeleye/projects/claude-invest
.venv/bin/python -m claude_invest.main portfolio
```

### 4. Report
Present a concise status:

| Component | Status |
|-----------|--------|
| Trading Crons | X active |
| FastAPI Server | running/stopped |
| Dashboard | running/stopped (http://localhost:3000) |
| Positions | X open |
| Daily P&L | $X.XX |
| Equity | $X,XXX |
