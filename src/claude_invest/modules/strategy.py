import json
import os
from datetime import datetime, timezone


def load_lessons(lessons_dir: str) -> dict:
    path = os.path.join(lessons_dir, "lessons.json")
    if not os.path.exists(path):
        return {"patterns": [], "last_updated": None}
    with open(path) as f:
        return json.load(f)


def update_lessons(lessons_dir: str, patterns: list[dict], date: str):
    existing = load_lessons(lessons_dir)

    existing_combos = {p["signal_combo"]: p for p in existing["patterns"]}
    for p in patterns:
        combo = p["signal_combo"]
        if combo in existing_combos:
            old = existing_combos[combo]
            old["wins"] = p["wins"]
            old["losses"] = p["losses"]
            old["total"] = p["total"]
            old["win_rate"] = p["win_rate"]
            old["avg_pnl"] = p["avg_pnl"]
            old["confidence"] = p["confidence"]
        else:
            existing_combos[combo] = p

    data = {
        "patterns": list(existing_combos.values()),
        "last_updated": date,
    }

    path = os.path.join(lessons_dir, "lessons.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    daily_path = os.path.join(lessons_dir, "daily", f"{date}.md")
    os.makedirs(os.path.dirname(daily_path), exist_ok=True)
    with open(daily_path, "w") as f:
        f.write(f"# Trading Lessons — {date}\n\n")
        for p in sorted(patterns, key=lambda x: x["win_rate"], reverse=True):
            status = "WIN" if p["win_rate"] > 0.5 else "LOSS" if p["win_rate"] < 0.5 else "MIXED"
            f.write(f"- [{status}] {p['signal_combo']}: {p['wins']}W/{p['losses']}L (avg P&L: {p['avg_pnl']:.2f})\n")


def build_strategy_brief(lessons_dir: str, allocation: dict) -> str:
    lessons = load_lessons(lessons_dir)
    patterns = lessons.get("patterns", [])

    lines = ["# Strategy Brief", ""]
    lines.append(f"*Updated: {lessons.get('last_updated', 'never')}*")
    lines.append("")

    rules_always = [p for p in patterns if p.get("confidence") == "high" and p.get("win_rate", 0) >= 0.75 and p.get("total", 0) >= 3]
    rules_never = [p for p in patterns if p.get("confidence") == "high" and p.get("win_rate", 1) <= 0.25 and p.get("total", 0) >= 3]
    observations = [p for p in patterns if p.get("confidence") != "high" or p.get("total", 0) < 3]

    if rules_always:
        lines.append("## RULES — ALWAYS")
        for r in rules_always:
            lines.append(f"- PREFER: {r['signal_combo']} ({r['wins']}W/{r['losses']}L, avg +{r['avg_pnl']:.2f})")
        lines.append("")

    if rules_never:
        lines.append("## RULES — NEVER")
        for r in rules_never:
            lines.append(f"- AVOID: {r['signal_combo']} ({r['wins']}W/{r['losses']}L, avg {r['avg_pnl']:.2f})")
        lines.append("")

    if observations:
        lines.append("## OBSERVATIONS (need more data)")
        for o in sorted(observations, key=lambda x: x.get("total", 0), reverse=True)[:10]:
            wr = o.get("win_rate", 0)
            lines.append(f"- {o['signal_combo']}: {o.get('wins',0)}W/{o.get('losses',0)}L ({wr:.0%} win rate)")
        lines.append("")

    tiers = allocation.get("tiers", {})
    alerts = [(name, t) for name, t in tiers.items() if t.get("alert")]
    if alerts:
        lines.append("## ALLOCATION ALERTS")
        for name, t in alerts:
            direction = "OVER" if t["drift"] > 0 else "UNDER"
            lines.append(f"- {name.upper()}: {t['actual']:.0%} actual vs {t['target']:.0%} target ({direction} by {abs(t['drift']):.0%})")
        lines.append("")

    total_wins = sum(p.get("wins", 0) for p in patterns)
    total_losses = sum(p.get("losses", 0) for p in patterns)
    total = total_wins + total_losses
    if total > 0:
        lines.append(f"## OVERALL: {total_wins}W/{total_losses}L ({total_wins/total:.0%} win rate)")

    brief = "\n".join(lines)

    brief_path = os.path.join(lessons_dir, "strategy-brief.md")
    with open(brief_path, "w") as f:
        f.write(brief)

    return brief
