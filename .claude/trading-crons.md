# Trading Cron Definitions

When asked to "start trading crons", create these three CronCreate jobs:

## 1. Market Hours (weekdays 9AM-3PM ET)
- Cron: `*/5 9-15 * * 1-5`
- Durable: true
- Full trading cycle: portfolio check, position management, discovery, evaluation, execution

## 2. After Hours (weekdays 4PM-7PM ET)
- Cron: `17 16-19 * * 1-5`
- Durable: true
- Review positions + crypto scan (BTC, ETH)

## 3. Crypto Overnight (8PM-8AM daily)
- Cron: `43 20-23,0-8 * * *`
- Durable: true
- Crypto-only monitoring

The prompts for each cron are the full trading engine prompts from the design spec.
Use the prompts from the original CronCreate calls in this session.
