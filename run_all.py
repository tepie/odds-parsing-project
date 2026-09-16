#!/usr/bin/env python3
"""Collect all supported Covers markets and rank the strongest edges together."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from analysis.comparator import analyze_comparisons, group_odds_by_player_market
from analysis.normalizer import collect_all_data
from analysis.outliers import remove_outliers
from models.odds import Odds, Projection
from props.covers_props import extract_props, filter_props
from playwright.sync_api import sync_playwright


GAME_SPORTS = ("nba", "mlb", "nfl", "ncaaf")
PROP_SPORTS = ("nfl", "mlb")


@dataclass(frozen=True)
class Edge:
    score: float
    sport: str
    kind: str
    description: str
    detail: str


def collect_game_edges(sport: str, outlier_method: str) -> list[Edge]:
    data = collect_all_data(sport)
    odds = [Odds(**item) for item in data["odds"]]
    projections = [Projection(**item) for item in data["projections"]]

    if outlier_method != "none":
        groups: dict[tuple[str, str], list[Odds]] = {}
        for item in odds:
            groups.setdefault((item.player, item.market), []).append(item)
        odds = [
            item
            for group in groups.values()
            for item in remove_outliers(group, outlier_method)
        ]

    comparisons = analyze_comparisons(
        group_odds_by_player_market(odds, projections)
    )
    edges = []
    for comparison in comparisons.values():
        if not comparison.best_odds or len(comparison.odds_list) < 2:
            continue
        market_edge = comparison.market_difference or 0
        if market_edge <= 0:
            continue
        best = comparison.best_odds
        event = best.event or best.player
        selection = best.selection or best.player
        edges.append(
            Edge(
                score=market_edge,
                sport=sport.upper(),
                kind="GAME",
                description=f"{event} | {comparison.market} | {selection}",
                detail=f"{best.bookmaker} {decimal_to_american(best.odds)}",
            )
        )
    return edges


def collect_prop_edges(sport: str, limit: int) -> list[Edge]:
    url = {
        "nfl": "https://www.covers.com/sport/football/nfl/player-props",
        "mlb": "https://www.covers.com/sport/baseball/mlb/player-props",
    }[sport]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            props = filter_props(extract_props(page, sport, []), [])[:limit]
        finally:
            browser.close()

    return [
        Edge(
            score=prop.difference,
            sport=sport.upper(),
            kind="PROP",
            description=f"{prop.player} ({prop.position}) | {prop.selection}",
            detail=f"{prop.game} | {prop.best_odds}",
        )
        for prop in props
    ]


def decimal_to_american(decimal_odds: float) -> str:
    if decimal_odds >= 2:
        return f"+{int((decimal_odds - 1) * 100)}"
    return str(int(-100 / (decimal_odds - 1)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum props per sport and number of global results to print",
    )
    parser.add_argument(
        "--outlier-method",
        choices=("zscore", "iqr", "none"),
        default="none",
    )
    args = parser.parse_args()

    edges: list[Edge] = []
    for sport in GAME_SPORTS:
        print(f"Collecting {sport.upper()} game odds...", flush=True)
        try:
            edges.extend(collect_game_edges(sport, args.outlier_method))
        except (ValueError, requests.RequestException, OSError) as error:
            print(f"Skipped {sport.upper()} game odds: {error}")

    for sport in PROP_SPORTS:
        print(f"Collecting {sport.upper()} player props...", flush=True)
        try:
            edges.extend(collect_prop_edges(sport, args.limit))
        except (PlaywrightTimeoutError, OSError, ValueError) as error:
            print(f"Skipped {sport.upper()} props: {error}")

    edges.sort(key=lambda edge: edge.score, reverse=True)
    print("\nGLOBAL EDGE RANKING")
    print("=" * 110)
    print(f"{'RANK':<5} {'EDGE':>8} {'SPORT':<6} {'TYPE':<5} {'OPPORTUNITY':<68} DETAILS")
    print("-" * 110)
    for rank, edge in enumerate(edges[: args.limit], 1):
        print(
            f"{rank:<5} {edge.score:>+7.2f} {edge.sport:<6} {edge.kind:<5} "
            f"{edge.description[:68]:<68} {edge.detail}"
        )
    if not edges:
        print("No edges were collected.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
