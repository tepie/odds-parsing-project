#!/usr/bin/env python3
"""Build a cross-sport daily best-odds summary for the GitHub Action run."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GAME_SPORTS = ("nba", "mlb", "nfl", "ncaaf", "ncaab", "nhl")
PROP_SCANS = (
    ("nfl", "touchdowns", [sys.executable, "props/covers_props.py", "--sport", "nfl", "--prop-type", "touchdowns", "--limit", "10", "--format", "json", "--output", "nfl_touchdowns.json"]),
    ("nfl", "passing yards", [sys.executable, "props/covers_props.py", "--sport", "nfl", "--prop-type", "passing yards", "--limit", "10", "--format", "json", "--output", "nfl_passing_yards.json"]),
    ("mlb", "home runs", [sys.executable, "props/covers_props.py", "--sport", "mlb", "--prop-type", "home runs", "--limit", "10", "--format", "json", "--output", "mlb_home_runs.json"]),
)


def decimal_to_american(decimal_odds: float) -> str:
    if decimal_odds >= 2.0:
        return f"+{int((decimal_odds - 1) * 100)}"
    return str(int(-100 / (decimal_odds - 1)))


def parse_american(value: str | float | None) -> float:
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    if text.replace("+", "").replace("-", "").replace(".", "").isdigit():
        num = float(text)
        if num >= 2:
            return num
        if num > 0:
            return (num / 100) + 1
        if num < 0:
            return (100 / abs(num)) + 1
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_record(record: dict) -> dict | None:
    if not record.get("odds"):
        return None
    event = record.get("event") or record.get("player") or "Unknown"
    selection = record.get("selection") or record.get("player") or "Unknown"
    market = record.get("market") or "unknown"
    bookmaker = record.get("bookmaker") or "Unknown"
    source = record.get("source") or "Unknown"
    decimal_value = float(record.get("odds") or 0)
    if decimal_value <= 1:
        return None
    return {
        "sport": "general",
        "event": event,
        "market": market,
        "selection": selection,
        "bookmaker": bookmaker,
        "odds": decimal_value,
        "odds_american": decimal_to_american(decimal_value),
        "source": source,
    }


def scrape_game_summary(limit: int) -> list[dict]:
    rows: list[dict] = []
    for sport in GAME_SPORTS:
        result = subprocess.run(
            [sys.executable, "main.py", "--sport", sport, "--outlier-method", "none", "--limit", str(limit)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode not in (0, 1):
            print(result.stderr, file=sys.stderr)
        odds_path = REPO_ROOT / "odds_data.json"
        if not odds_path.exists():
            continue
        with odds_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for record in payload.get("odds", []):
            parsed = parse_record(record)
            if not parsed:
                continue
            parsed["sport"] = sport.upper()
            rows.append(parsed)
    return rows


def scrape_prop_summary() -> list[dict]:
    rows: list[dict] = []
    for sport, market_label, command in PROP_SCANS:
        result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        if result.returncode not in (0, 1):
            print(result.stderr, file=sys.stderr)
        file_name = command[-1]
        file_path = REPO_ROOT / file_name
        if not file_path.exists():
            continue
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for record in payload:
            decimal_value = parse_american(record.get("best_odds"))
            if decimal_value <= 1:
                continue
            rows.append(
                {
                    "sport": sport.upper(),
                    "event": record.get("game") or record.get("player") or "Unknown",
                    "market": record.get("market") or market_label,
                    "selection": record.get("selection") or record.get("player") or "Unknown",
                    "bookmaker": "Covers",
                    "odds": decimal_value,
                    "odds_american": decimal_to_american(decimal_value),
                    "source": "Covers props",
                }
            )
    return rows


def render_markdown(rows: list[dict], limit: int) -> str:
    top_rows = sorted(rows, key=lambda item: item["odds"], reverse=True)[:limit]
    lines = [
        "# Daily best odds summary",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| Sport | Market | Matchup | Selection | Book | Odds |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not top_rows:
        lines.append("No odds were captured.")
        return "\n".join(lines) + "\n"
    for row in top_rows:
        lines.append(
            f"| {row['sport']} | {row['market']} | {row['event']} | {row['selection']} | {row['bookmaker']} | {row['odds_american']} ({row['odds']:.2f}) |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    rows = scrape_game_summary(args.limit)
    rows.extend(scrape_prop_summary())

    markdown = render_markdown(rows, args.limit)
    summary_path = REPO_ROOT / "daily_best_odds.md"
    summary_path.write_text(markdown, encoding="utf-8")
    print(markdown)

    github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_summary:
        with open(github_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
