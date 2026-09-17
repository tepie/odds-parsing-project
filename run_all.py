#!/usr/bin/env python3
"""Collect all supported Covers markets and rank the strongest edges together."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from analysis.comparator import (
    analyze_comparisons,
    group_odds_by_player_market,
    projection_recommendation,
    _team_label_matches,
)
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


def collect_game_edges(sport: str, outlier_method: str, include_api: bool = False) -> list[Edge]:
    data = collect_all_data(sport, include_api=include_api)
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
    moneylines: dict[str, list[Odds]] = {}
    for comparison in comparisons.values():
        if not comparison.best_odds:
            continue
        best = comparison.best_odds
        if best.market == "moneyline" and best.event:
            moneylines.setdefault(best.event, []).append(best)
        model_edge = best.score_edge if best.score_edge and best.score_edge > 0 else 0
        if model_edge <= 0:
            continue
        event = best.event or best.player
        selection = best.selection or best.player
        recommendation = projection_recommendation(best)
        projection = next(
            (
                item for item in projections
                if item.event and best.event and item.event.lower() == best.event.lower()
            ),
            None,
        )
        edges.append(
            Edge(
                score=model_edge,
                sport=sport.upper(),
                kind="GAME",
                description=f"{event} | {comparison.market} | {selection}",
                detail=(
                    (f"predicted {projection.away_score:.2f}-{projection.home_score:.2f} | "
                     if projection and projection.away_score is not None and projection.home_score is not None
                     else "")
                    + (recommendation or f"edge {model_edge:+.2f} pts")
                ),
            )
        )
    for event, sides in moneylines.items():
        projection = next((item for item in projections if item.event and item.event.lower() == event.lower()), None)
        if not projection or projection.projected_spread is None or len(sides) < 2:
            continue
        market_team = min(sides, key=lambda item: item.odds).selection
        away, home = [part.strip() for part in event.split("@", 1)]
        model_team = home if projection.projected_spread > 0 else away
        market_favorite = next(
            (item for item in sides if item.selection and _team_label_matches(item.selection, market_team or "")),
            None,
        )
        market_favorite_team = market_favorite.selection if market_favorite else market_team
        if market_favorite_team and not _team_label_matches(market_favorite_team, model_team):
            model_side = next(
                (item for item in sides if item.selection and _team_label_matches(item.selection, model_team)),
                None,
            )
            if model_side:
                edges.append(
                    Edge(
                        score=abs(projection.projected_spread),
                        sport=sport.upper(),
                        kind="GAME",
                        description=f"{event} | moneyline upset | {model_team}",
                        detail=f"predicted margin {projection.projected_spread:+.1f} pts",
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
    parser.add_argument(
        "--include-odds-api",
        action="store_true",
        help="Also query The Odds API; Covers is used by default",
    )
    args = parser.parse_args()

    edges: list[Edge] = []
    for sport in GAME_SPORTS:
        print(f"Collecting {sport.upper()} game odds...", flush=True)
        try:
            edges.extend(collect_game_edges(sport, args.outlier_method, args.include_odds_api))
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
