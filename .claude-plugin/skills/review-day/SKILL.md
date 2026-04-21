---
description: Run daily trading analysis — review wins/losses, score signal patterns, update strategy brief, check portfolio allocation
argument-hint: [date] (optional, defaults to today)
allowed-tools: Bash, Read
---

# Review Day

Run the daily trading analysis and learning cycle.

## Steps

### 1. Run the analysis
```bash
cd /Users/adewaleadeleye/projects/claude-invest
.venv/bin/python -m claude_invest.main review-day
```

### 2. Show the strategy brief
```bash
cat lessons/strategy-brief.md
```

### 3. Show allocation
```bash
.venv/bin/python -m claude_invest.main allocation
```

### 4. Present a summary to the user

Format the output as:
- Win/loss record and win rate
- Top performing signal patterns
- Mistakes to avoid
- Allocation status with drift alerts
- Strategy rules that were added or updated

Ask the user if they want to adjust any allocation targets or add manual sector overrides.
