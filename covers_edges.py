#!/usr/bin/env python3
"""
Covers.com Computer Picks Edge Finder (v6 – Clear Actionable Output)
"""

import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

NCAAF_URL = "https://www.covers.com/picks/ncaaf"
NFL_URL   = "https://www.covers.com/picks/nfl"
MIN_EDGE  = 1.0


@dataclass
class GameEdge:
    league: str
    matchup: str
    away: str
    home: str
    pred_away: float
    pred_home: float
    pred_margin: float
    pred_total: float
    mkt_spread: Optional[float] = None   # from home perspective
    mkt_total: Optional[float] = None
    spread_edge: Optional[float] = None
    total_edge: Optional[float] = None
    recommendation: str = ""


def extract_number(text: str) -> Optional[float]:
    if not text:
        return None
    text = text.replace("−", "-").replace("–", "-")
    m = re.search(r"([+-]?\d+\.?\d*)", text)
    return float(m.group(1)) if m else None


def parse_page(url: str, league: str) -> List[GameEdge]:
    print(f"Fetching {league} ...")
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  Failed: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    games = []
    seen = set()

    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        header_cells = [c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"])]
        header_text = " ".join(header_cells)

        if "predicted" not in header_text and "spread" not in header_text:
            continue

        try:
            away_cells = [c.get_text(" ", strip=True) for c in rows[1].find_all(["td", "th"])]
            home_cells = [c.get_text(" ", strip=True) for c in rows[2].find_all(["td", "th"])]

            if len(away_cells) < 3 or len(home_cells) < 3:
                continue

            away_team = away_cells[0]
            home_team = home_cells[0]

            away_abbr = re.search(r"[A-Z0-9]{2,5}", away_team)
            home_abbr = re.search(r"[A-Z0-9]{2,5}", home_team)
            away = away_abbr.group(0) if away_abbr else away_team[:5]
            home = home_abbr.group(0) if home_abbr else home_team[:5]

            if away == home:
                continue

            pred_away = extract_number(away_cells[1])
            pred_home = extract_number(home_cells[1])
            if pred_away is None or pred_home is None:
                continue

            pred_margin = pred_home - pred_away
            pred_total = pred_away + pred_home

            # Market spread (prefer home row)
            mkt_spread = None
            for cell in (home_cells[2], away_cells[2]):
                val = extract_number(cell)
                if val is not None and 0.5 <= abs(val) <= 55:
                    mkt_spread = val
                    break

            # Market total
            mkt_total = None
            for cell in (home_cells[3] if len(home_cells) > 3 else "",
                         away_cells[3] if len(away_cells) > 3 else ""):
                if re.search(r"[ou]\s*\d", cell, re.I) or "total" in cell.lower():
                    val = extract_number(cell)
                    if val and 30 < val < 90:
                        mkt_total = val
                        break
                else:
                    val = extract_number(cell)
                    if val and 35 < val < 85 and abs(val - pred_away) > 4 and abs(val - pred_home) > 4:
                        mkt_total = val
                        break

            matchup = f"{away} @ {home}"
            if matchup in seen:
                continue
            seen.add(matchup)

            game = GameEdge(
                league=league,
                matchup=matchup,
                away=away,
                home=home,
                pred_away=pred_away,
                pred_home=pred_home,
                pred_margin=pred_margin,
                pred_total=pred_total,
                mkt_spread=mkt_spread,
                mkt_total=mkt_total,
            )

            # Calculate edges
            if mkt_spread is not None:
                game.spread_edge = pred_margin - (-mkt_spread)

            if mkt_total is not None:
                game.total_edge = pred_total - mkt_total
                if abs(game.total_edge) > 18:
                    game.mkt_total = None
                    game.total_edge = None

            # ---------- Clear Recommendation ----------
            recs = []

            if game.spread_edge is not None and abs(game.spread_edge) >= MIN_EDGE:
                if game.spread_edge > 0:
                    # Model likes home more → bet home against the spread
                    home_line = mkt_spread
                    recs.append(f"Bet {home} {home_line:+.1f}")
                else:
                    # Model likes away more → bet away against the spread
                    away_line = -mkt_spread if mkt_spread is not None else 0
                    recs.append(f"Bet {away} {away_line:+.1f}")

            if game.total_edge is not None and abs(game.total_edge) >= MIN_EDGE:
                if game.total_edge > 0:
                    recs.append(f"OVER {mkt_total:.1f}")
                else:
                    recs.append(f"UNDER {mkt_total:.1f}")

            # ML upset flag
            if mkt_spread is not None:
                market_home_fav = mkt_spread < 0
                model_home_fav = pred_margin > 1.0
                if market_home_fav != model_home_fav:
                    underdog = home if not market_home_fav else away
                    recs.append(f"ML upset lean: {underdog}")

            game.recommendation = " | ".join(recs) if recs else "No clear edge"
            games.append(game)

        except Exception:
            continue

    print(f"  Parsed {len(games)} clean games")
    return games


def print_table(games: List[GameEdge], title: str):
    if not games:
        print(f"\n{title}: nothing found")
        return

    ranked = sorted(
        games,
        key=lambda g: abs(g.spread_edge) if g.spread_edge is not None else 0,
        reverse=True,
    )

    print(f"\n{'='*100}")
    print(f" {title}")
    print(f"{'='*100}")
    print(f"{'Matchup':<16} {'Pred':<11} {'Margin':>7} {'Mkt Spr':>8} {'Edge':>6}  Recommendation")
    print("-" * 100)

    for g in ranked:
        pred   = f"{g.pred_away:.1f}-{g.pred_home:.1f}"
        margin = f"{g.pred_margin:+.1f}"
        mkt    = f"{g.mkt_spread:+.1f}" if g.mkt_spread is not None else "—"
        edge   = f"{g.spread_edge:+.1f}" if g.spread_edge is not None else "—"
        print(f"{g.matchup:<16} {pred:<11} {margin:>7} {mkt:>8} {edge:>6}  {g.recommendation}")

    # Notable totals
    tot = sorted(
        [g for g in games if g.total_edge is not None],
        key=lambda g: abs(g.total_edge),
        reverse=True,
    )[:8]
    if tot:
        print("\nNotable Total Edges:")
        for g in tot:
            direction = "OVER" if g.total_edge > 0 else "UNDER"
            print(f"  {g.matchup:<16} Pred {g.pred_total:.1f} vs Mkt {g.mkt_total:.1f} → {direction} {abs(g.total_edge):.1f}")


def main():
    print(f"Covers Edge Check – {datetime.now():%Y-%m-%d %H:%M}")
    print("=" * 55)

    ncaaf = parse_page(NCAAF_URL, "NCAAF")
    nfl   = parse_page(NFL_URL, "NFL")

    print_table(ncaaf, "NCAAF – Ranked by Spread Edge")
    print_table(nfl,   "NFL – Ranked by Spread Edge")

    combined = sorted(
        [g for g in (ncaaf + nfl) if g.spread_edge and abs(g.spread_edge) >= 1.5],
        key=lambda g: abs(g.spread_edge),
        reverse=True,
    )[:15]

    if combined:
        print(f"\n{'='*100}")
        print(" COMBINED TOP EDGES (≥ 1.5 pts)")
        print(f"{'='*100}")
        for i, g in enumerate(combined, 1):
            print(f"{i:2}. [{g.league}] {g.matchup:<16} {g.spread_edge:+.1f}  →  {g.recommendation}")

    print("\nAlways verify live lines – they move.")


if __name__ == "__main__":
    main()