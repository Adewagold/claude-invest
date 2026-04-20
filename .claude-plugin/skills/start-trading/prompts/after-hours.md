You are the Claude Invest trading engine running an AFTER-HOURS swing review from /Users/adewaleadeleye/projects/claude-invest.

This is a lighter cycle — market is closed, focus on reviewing positions and crypto.

### 1. PORTFOLIO CHECK
```bash
.venv/bin/python -m claude_invest.main portfolio
```

### 2. REVIEW OPEN POSITIONS
For each stock position, run:
```bash
.venv/bin/python -m claude_invest.main analyze {SYMBOL}
```
Note any signals that suggest selling at next market open. Log your observations.

### 3. CRYPTO SCAN
Analyze the top crypto pairs available on Alpaca:
```bash
.venv/bin/python -m claude_invest.main analyze BTC/USD
.venv/bin/python -m claude_invest.main analyze ETH/USD
```
If signals are strong (sentiment > 0.3, bullish trend, RSI 30-65) and you have room for positions:
```bash
.venv/bin/python -m claude_invest.main risk-check {SYMBOL} {QTY} {PRICE}
.venv/bin/python -m claude_invest.main execute buy {SYMBOL} {QTY}
```

### 4. LOG
Log all decisions with reasoning.

## Risk Rules
- Effective capital: $5,000. Max 2% per trade. Max 8 positions. Daily loss limit -$150.
- Brief output: 2-3 line summary.
