#!/usr/bin/env python3
"""Scrape Covers NFL props and rank them by projection edge."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

DEFAULT_URL = "https://www.covers.com/sport/football/nfl/player-props"
PROBABILITY_PROP_TERMS = ("touchdown", "interception")
MIN_PROBABILITY_PROJECTION = 0.40


@dataclass(frozen=True)
class Prop:
    player: str
    position: str
    market: str
    selection: str
    line: float | None
    projection: float | None
    difference: float
    ev_percent: float | None
    best_odds: str
    game: str


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def number(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.search(r"[+-]?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group()) if match else None


def parse_prop(text: str, odds: str = "", game: str = "") -> Prop | None:
    text = compact(text)
    player_match = re.search(
        r"(?:[A-Z]{2,3}\s+)?"
        r"(?P<player>(?:[A-Z](?:\.[A-Z])?\.?|[A-Z][A-Za-z.'-]+)"
        r"(?:\s+[A-Z][A-Za-z.'-]*)+)\s+"
        r"\((?P<position>QB|RB|WR|TE|K|FB)\)",
        text,
    )
    if not player_match:
        return None

    difference_match = re.search(
        r"(?P<difference>[+-]?\d+(?:\.\d+)?)\s+DIFFERENCE", text, re.I
    )
    if not difference_match:
        difference_match = re.search(
            r"DIFFERENCE\s+(?P<difference>[+-]?\d+(?:\.\d+)?)%?\s+EV",
            text,
            re.I,
        )
    projection_match = re.search(
        r"(?P<projection>[+-]?\d+(?:\.\d+)?)\s+(?:OVER|UNDER)?\s*(?:[A-Za-z]+\s+)*PROJECTION",
        text,
        re.I,
    )
    ev_match = re.search(r"(?P<ev>[+-]?\d+(?:\.\d+)?)%\s+EV", text, re.I)
    if not difference_match and ev_match:
        difference_value = number(ev_match.group("ev"))
    elif difference_match:
        difference_value = number(difference_match.group("difference"))
    else:
        difference_value = None
    if difference_value is None:
        return None

    player_end = player_match.end()
    market_text = compact(text[player_end : projection_match.start()] if projection_match else "")
    selection_match = re.search(
        r"(?P<selection>[ou]?\s*[+-]?\d+(?:\.\d+)?)\s+(?P<market>.+)$",
        market_text,
        re.I,
    )
    if not selection_match:
        selection_match = re.search(
            r"(?P<market>.+?)\s+(?P<selection>[+-]?\d+(?:\.\d+)?)\s+[A-Za-z]+$",
            market_text,
            re.I,
        )
    if selection_match:
        selection = compact(f"{selection_match.group('selection')} {selection_match.group('market')}")
        market = compact(selection_match.group("market"))
        line = number(selection_match.group("selection"))
    elif projection_match and market_text:
        selection = market_text
        market = market_text
        line = None
    else:
        return None

    return Prop(
        player=player_match.group("player"),
        position=player_match.group("position"),
        market=market,
        selection=selection,
        line=line,
        projection=number(projection_match.group("projection")) if projection_match else None,
        difference=difference_value,
        ev_percent=number(ev_match.group("ev")) if ev_match else None,
        best_odds=compact(odds),
        game=compact(game),
    )


def reveal_more_props(page: Page, prop_types: list[str]) -> None:
    terms = " ".join(prop_types).casefold()
    market_name = None
    if "touchdown" in terms:
        market_name = "nfl_game_player_score_touchdown"
    elif "interception" in terms:
        market_name = "nfl_game_player_passing_interception"

    if not market_name:
        return

    page.wait_for_timeout(1_000)
    more_button = page.locator("button.more-btn").first
    if more_button.count():
        more_button.wait_for(state="visible", timeout=30_000)
        more_button.click()
        page.wait_for_timeout(500)

    market_button = page.locator(f'button[data-market-name="{market_name}"]').first
    market_button.wait_for(state="visible", timeout=10_000)
    if "selected-market" not in (market_button.get_attribute("class") or ""):
        market_button.click()
    page.wait_for_function(
        """marketName => {
            const button = document.querySelector(
                `button[data-market-name="${marketName}"].selected-market`
            );
            return Boolean(button);
        }""",
        arg=market_name,
        timeout=10_000,
    )
    label = "Anytime Touchdown" if "touchdown" in terms else "Interceptions Thrown"
    page.wait_for_function(
        """label => Array.from(document.querySelectorAll(
            '.game-projections-container'
        )).some(row => row.innerText.toLowerCase().includes(label.toLowerCase()))""",
        arg=label,
        timeout=30_000,
    )


def extract_props(page: Page, prop_types: list[str]) -> list[Prop]:
    reveal_more_props(page, prop_types)
    page.wait_for_selector(".game-projections-container", state="attached", timeout=30_000)
    row_locator = page.locator(".game-projections-container")
    terms = " ".join(prop_types).casefold()
    if "touchdown" in terms:
        row_locator = row_locator.filter(has_text=re.compile(r"anytime\s+touchdown", re.I))
    elif "interception" in terms:
        row_locator = row_locator.filter(has_text=re.compile(r"interceptions\s+thrown", re.I))
    props: dict[tuple[object, ...], Prop] = {}

    for row in row_locator.all():
        text = compact(row.inner_text())
        if "DIFFERENCE" not in text.upper() or "PROJECTION" not in text.upper():
            continue
        odds_links = row.locator("a").all_inner_texts()
        game_links = row.locator('a[href*="/matchup/"]').all_inner_texts()
        prop = parse_prop(
            text,
            odds=odds_links[-1] if odds_links else "",
            game=game_links[0] if game_links else "",
        )
        if prop is None:
            continue
        key = (prop.player, prop.position, prop.market, prop.selection, prop.line, prop.projection, prop.difference)
        props.setdefault(key, prop)

    return sorted(props.values(), key=lambda prop: prop.difference, reverse=True)


def print_table(props: Iterable[Prop]) -> None:
    rows = list(props)
    headers = ["EDGE", "PLAYER", "PROP", "PROJECTION", "EV", "ODDS", "GAME"]
    values = [
        [
            f"{prop.difference:+.1f}",
            f"{prop.player} ({prop.position})",
            prop.selection,
            f"{prop.projection:.2f}" if prop.projection is not None else "",
            f"{prop.ev_percent:.2f}%" if prop.ev_percent is not None else "",
            prop.best_odds,
            prop.game,
        ]
        for prop in rows
    ]
    if not values:
        return
    widths = [max(len(headers[index]), *(len(row[index]) for row in values)) for index in range(len(headers))]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in values:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def filter_props(props: Iterable[Prop], prop_types: list[str]) -> list[Prop]:
    terms = [
        term.strip().casefold()
        for value in prop_types
        for term in value.split(",")
        if term.strip()
    ]
    terms.extend(term[:-1] for term in terms if term in ("touchdowns", "interceptions"))
    filtered = [
        prop for prop in props
        if not terms or any(term in f"{prop.market} {prop.selection}".casefold() for term in terms)
    ]
    return [prop for prop in filtered if is_reportable_edge(prop)]


def is_reportable_edge(prop: Prop) -> bool:
    prop_text = f"{prop.market} {prop.selection}".casefold()
    is_probability_prop = any(term in prop_text for term in PROBABILITY_PROP_TERMS)
    return not is_probability_prop or (
        prop.projection is not None and prop.projection > MIN_PROBABILITY_PROJECTION
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--prop-type", action="append", default=[], metavar="TEXT",
                        help="Keep props whose market or selection contains TEXT; repeat or use commas for alternatives")
    parser.add_argument("--format", choices=("table", "json", "csv"), default="table")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--headed", action="store_true", help="Show the browser while scraping")
    args = parser.parse_args()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(args.url, wait_until="domcontentloaded", timeout=60_000)
            props = filter_props(extract_props(page, args.prop_type), args.prop_type)[: max(args.limit, 0)]
            browser.close()
    except PlaywrightTimeoutError as error:
        print(f"Timed out waiting for Covers props: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Scrape failed: {error}", file=sys.stderr)
        return 1

    if args.format == "json":
        rendered = json.dumps([asdict(prop) for prop in props], indent=2)
    elif args.format == "csv":
        output = _StringWriter()
        writer = csv.DictWriter(output, fieldnames=list(Prop.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(prop) for prop in props)
        rendered = output.value
    else:
        if not props:
            message = (
                f"No props matched --prop-type {', '.join(args.prop_type)!r}."
                if args.prop_type
                else "No props found. Covers may have changed its page structure."
            )
            print(message, file=sys.stderr)
            return 1
        print_table(props)
        return 0

    if args.output:
        args.output.write_text(rendered + ("\n" if not rendered.endswith("\n") else ""), encoding="utf-8")
    else:
        print(rendered)
    return 0


class _StringWriter:
    def __init__(self) -> None:
        self.value = ""

    def write(self, value: str) -> int:
        self.value += value
        return len(value)


if __name__ == "__main__":
    raise SystemExit(main())
