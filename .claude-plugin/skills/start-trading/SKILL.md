---
description: Start the Claude Invest trading engine — creates market hours, after-hours, and crypto overnight cron jobs, starts the FastAPI server and Next.js dashboard
argument-hint: (no arguments needed)
allowed-tools: Bash, CronCreate, CronList, Read
---

# Start Trading

Start the Claude Invest trading engine by creating all trading cron jobs and ensuring servers are running.

## Steps

### 1. Start FastAPI Backend (if not running)

Check if port 8000 is in use. If not, start the API server:

```bash
cd /Users/adewaleadeleye/projects/claude-invest
lsof -ti:8000 > /dev/null 2>&1 || (source .venv/bin/activate && .venv/bin/python -m claude_invest.modules.api_server &>/dev/null &)
```

### 2. Start Next.js Dashboard (if not running)

Check if port 3000 is in use. If not, start the dashboard:

```bash
cd /Users/adewaleadeleye/projects/claude-invest/dashboard
lsof -ti:3000 > /dev/null 2>&1 || (npm run dev &>/dev/null &)
```

### 3. Create Trading Crons

Check existing crons with CronList first. Only create crons that don't already exist.

Create these three CronCreate jobs:

**Market Hours (weekdays 9AM-3PM ET):**
- Cron: `*/5 9-15 * * 1-5`
- Durable: true
- Recurring: true
- Prompt: The full market hours trading cycle prompt. Read it from `/Users/adewaleadeleye/projects/claude-invest/.claude-plugin/skills/start-trading/prompts/market-hours.md`

**After Hours (weekdays 4PM-7PM ET):**
- Cron: `17 16-19 * * 1-5`
- Durable: true
- Recurring: true
- Prompt: The after-hours review prompt. Read it from `/Users/adewaleadeleye/projects/claude-invest/.claude-plugin/skills/start-trading/prompts/after-hours.md`

**Crypto Overnight (8PM-8AM daily):**
- Cron: `43 20-23,0-8 * * *`
- Durable: true
- Recurring: true
- Prompt: The crypto overnight prompt. Read it from `/Users/adewaleadeleye/projects/claude-invest/.claude-plugin/skills/start-trading/prompts/crypto-overnight.md`

### 4. Confirm

After all crons are created, run CronList and report:
- How many crons are active
- FastAPI server status (port 8000)
- Dashboard status (port 3000)
- Dashboard URL: http://localhost:3000

Say: "Trading engine is live. Crons will fire on schedule. Dashboard at http://localhost:3000"
