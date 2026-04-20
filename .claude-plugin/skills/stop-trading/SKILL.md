---
description: Stop the Claude Invest trading engine — cancel all trading cron jobs
argument-hint: (no arguments needed)
allowed-tools: CronList, CronDelete
---

# Stop Trading

Stop the Claude Invest trading engine by canceling all active trading cron jobs.

## Steps

1. Run CronList to see all active crons
2. Delete each trading cron using CronDelete
3. Confirm: "Trading engine stopped. All crons canceled. Servers still running for dashboard access."

Note: This does NOT stop the FastAPI server or dashboard — those remain available for viewing historical data.
