# Covers Sports Odds Project

A Python scraper and reporting pipeline focused on Covers.com for NBA, MLB, NFL, and NCAAF betting odds and NFL player props. It normalizes prices into a common model, compares bookmakers, filters records, and provides console-oriented reports.

This repository is the active successor to the original NBA `oddsparser` experiment. Covers is the primary source; The Odds API is an optional supplement. Treat generated reports as inspection aids, not production betting or pricing systems.

## What It Does

`main.py` runs the game-odds pipeline:

1. Scrapes Covers game prices and predicted-score projections for NBA, MLB, NFL, or NCAAF.
2. Optionally supplements Covers with The Odds API game markets (`h2h`, `spreads`, and `totals`).
3. Normalizes scraped odds to decimal format and lowercases player/event keys.
4. Reconstructs `Odds` and `Projection` dataclass objects.
5. Filters odds by bookmaker, minimum decimal odds, optional EV, and market.
6. Removes per-player/per-market outliers with z-score or IQR filtering.
7. Groups odds and projections by event, market, and selection when source metadata is available.
8. Calculates a bookmaker-relative percentage, identifies the best decimal odds, and calculates an unweighted average (“Blended Score”).
9. Ranks available market groups by best-price difference versus the market median.
10. Prints a console summary and saves the unfiltered scrape data as JSON. An HTML report is optional.

The `props/covers_props.py` command separately collects NFL or MLB props from Covers' client-rendered props pages and can print a table or write JSON/CSV. The project does not place bets, persist historical runs, expose an API, or provide a web server.

## AI Handoff: Goals And Progress

### Project Goals

- Collect current sports odds from multiple sources.
- Normalize bookmaker, event, market, selection, and price data into shared records.
- Compare available prices and identify the strongest value opportunities.
- Preserve the original NBA use case as an explicit sport filter.
- Make Covers the primary and maintained odds source across NBA, MLB, NFL, and NCAAF.
- Produce useful console output for each selected sport.
- Collect NFL and MLB props with projection edge, EV, visible odds, and game context.
- Keep the pipeline easy for another AI session to inspect, test, and extend.

### Completed Progress

- Added `--sport nba|mlb|nfl|ncaaf` routing.
- Added Covers picks-page collection for NBA, MLB, NFL, and NCAAF.
- Added The Odds API support for NBA, MLB, NFL, and NCAAF as an optional supplement.
- Added odds metadata for event, selection, line, fair odds, and source-published EV.
- Added event/market/selection grouping support for records that provide those fields.
- Replaced the active OddsShark, Action Network, and CrazyNinja collection paths with Covers.
- Moved the `covers-props` scraper into `props/` as the NFL/MLB player-props workflow.
- Updated this README with setup, runtime behavior, limitations, and continuation guidance.

### Current Working Behavior

- NBA, MLB, NFL, and NCAAF use the corresponding Covers picks page.
- The Odds API is attempted only as an optional supplement and is skipped when no API key is present.
- Covers predicted-score data is retained as projections when the page exposes it.
- NFL and MLB props are collected with Playwright and ranked by Covers' displayed Difference field.

### Next AI Session Checklist

1. Run fresh NBA, MLB, NFL, and NCAAF collections and confirm the Covers parser returns records from each live page.
2. Add fixture-based tests for Covers detail-line parsing and American-to-decimal conversion.
3. Extract stable matchup identifiers from Covers so prices and projections join reliably.
4. Add `numpy` to `requirements.txt` and improve source-level error handling.

When continuing work, preserve the distinction between source-published value and the comparator's percentage relative to a bookmaker/reference price. They are different signals and should not share the same field without an explicit decision.

## Repository Layout

```text
main.py                    CLI entry point and orchestration
requirements.txt           Python dependencies
models/odds.py             Odds, Projection, and OddsComparison dataclasses
analysis/normalizer.py     Scraping orchestration, normalization, JSON output
analysis/comparator.py     Grouping, relative comparison, best odds, average score
analysis/outliers.py       Z-score and IQR filtering
reports/generator.py       Inline Jinja2 HTML report template
scrapers/
  covers.py                Legacy Covers player-projection scraper
  covers_ncaaf.py          Covers NBA/MLB/NFL/NCAAF game-picks scraper
  the_odds_api.py          Optional The Odds API integration
props/
  covers_props.py          Covers NFL/MLB player-props scraper and CLI
  run_covers_props.sh      Props launcher using the repository environment
odds_data.json             Checked-in example/raw output
odds_report.html           Checked-in example report
```

## Requirements

- Python 3
- Packages listed in `requirements.txt`
- Internet access to Covers and optionally The Odds API
- Internet access to the scraped sites
- `ODDS_API_KEY` only when The Odds API source should be included
- Playwright Chromium for the NFL props workflow

`webdriver-manager` attempts to obtain a compatible ChromeDriver automatically. The first Selenium run may therefore require network access and a locally installed Chrome browser.

## Setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The current code also imports `numpy` in `analysis/outliers.py`, but `numpy` is not listed in `requirements.txt`. Install it separately until the dependency file is updated:

```bash
python -m pip install numpy
```

On macOS, activate the environment again in each new terminal session:

```bash
source .venv/bin/activate
```

## Run The App

Basic console run:

```bash
python main.py
```

Collect NBA odds from Covers, with optional The Odds API supplementation:

```bash
export ODDS_API_KEY="your-key"
python main.py --sport nba --outlier-method none --output odds_report_nba.html
```

For console-only game output, omit `--output`:

```bash
python main.py --sport nfl --outlier-method none
```

Run the consolidated player-props workflow:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
./props/run_covers_props.sh --limit 25
./props/run_covers_props.sh --sport mlb --limit 25
```

Filter props and choose structured output:

```bash
./props/run_covers_props.sh --sport nfl --prop-type touchdowns --limit 50
./props/run_covers_props.sh --sport mlb --prop-type "home runs" --limit 50
./props/run_covers_props.sh --format json --output props.json
./props/run_covers_props.sh --format csv --output props.csv
```

The game-odds run always writes raw collected data to `odds_data.json`, even when no HTML output is requested.

Example focused run:

```bash
python main.py \
  --market first_inning_total_runs \
  --outlier-method iqr \
  --min-odds 1.909 \
  --output reports/mlb-review.html
```

Optional The Odds API source:

```bash
export ODDS_API_KEY="your-key"
python main.py
```

If `ODDS_API_KEY` is absent, the API source is skipped. Other request or Selenium failures are not generally caught by the orchestration layer and may stop the run.

## CLI Options

| Option | Default | Meaning |
| --- | --- | --- |
| `--sport` | `mlb` | `nba`, `mlb`, `nfl`, or `ncaaf`; Covers is queried for the selected sport. |
| `--market` | `all` | Keep one normalized market, such as `home_runs`, `home_run`, or `first_inning_total_runs`. The exact value must match scraper output. |
| `--output` | unset | Optional HTML report path. Omit it for console-only output. |
| `--outlier-method` | `zscore` | `zscore`, `iqr`, or `none`; filtering is performed separately for each player/market group. |
| `--bookmakers` | Several common books | One or more bookmaker names. Matching is case-insensitive but otherwise exact. |
| `--min-odds` | `1.909` | Minimum decimal odds retained. This is approximately -110 or better. |
| `--min-ev` | unset | Filters on `Odds.ev`, but the current pipeline calculates comparison percentages only after this filter. See limitations below. |

To include all bookmakers discovered by the scrapers, pass an explicit list containing their names, for example:

```bash
python main.py --bookmakers Pinnacle Circa Sports Novig Fanatics DraftKings PointsBet
```

## Data Contracts

### `Odds`

Defined in `models/odds.py`:

```text
bookmaker: str
odds: float       decimal odds after normalization
market: str
player: str       also used for matchup/event descriptions
 timestamp: str
source: str | None
ev: float | None
```

### `Projection`

```text
site: str
player: str
market: str
projection: float
timestamp: str
```

The JSON output has this shape:

```json
{
  "odds": [],
  "projections": [],
  "timestamp": "ISO-8601 timestamp"
}
```

## Analysis Semantics

- American odds are converted to decimal odds by scraper helpers or `normalize_odds`.
- `normalize_odds` treats values below zero as American odds, values above 20 or at least 100 as American-style positive odds, and values in the normal decimal range as already decimal.
- Players/event labels are lowercased and stripped before grouping.
- “Best odds” means the largest decimal payout, not necessarily the best price after accounting for limits, liquidity, or fees.
- `Pinnacle` and `Circa` are treated as sharp references when their bookmaker names contain those strings. If neither is present, the group’s best odds becomes the reference.
- The displayed `ev` field is actually percentage difference from the selected sharp/reference odds: `((book_odds - reference_odds) / reference_odds) * 100`.
- `blended_score` is the simple arithmetic mean of decimal odds in the group; no bookmaker reliability weights are currently applied.

## Current Limitations And Next Work

These are the most important facts for the next contributor:

- The Covers HTML structure may change and the current parser depends on recognizable picks tables and matchup links.
- Covers projections and odds do not always expose a stable shared matchup identifier, so projection joins may be incomplete.
- `--min-ev` is currently unreliable: it filters before `analyze_comparisons()` assigns the relative percentage to `Odds.ev`. With the usual scraped records, setting it can remove records whose `ev` is still `None`.
- The default minimum odds filter runs before comparison and may exclude otherwise useful prices.
- The default bookmaker list includes `NoviG`; matching is case-insensitive, so it matches `Novig`, but bookmaker aliases are not otherwise normalized.
- The Odds API integration defaults to game-level `h2h`, `spreads`, and `totals` markets.
- The legacy scraper modules remain in the tree for reference but are not active collection sources.
- The props workflow requires a browser because Covers renders player props client-side.
- The checked-in `odds_data.json` and `odds_report.html` are snapshots, not guaranteed current data.
- Generated report headings use the selected sport (`NBA`, `MLB`, `NFL`, or `NCAAF`).
- There are no test files or configuration files in the repository. When changing parsing or matching, add fixture-based tests before relying on live websites.

## Recommended Continuation Order

1. Add `numpy` to `requirements.txt`.
2. Add request timeouts, browser cleanup guarantees, and source-level error handling.
3. Replace table assumptions with fixture-backed Covers parsers for NBA, MLB, NFL, and NCAAF.
4. Extract stable matchup identifiers and normalize bookmaker aliases and market names.
5. Move EV/reference calculation before `--min-ev`, or rename the option to reflect that it is a relative percentage.
6. Add fixture-based tests for the game and player-props parsers.

## Output And Safety Notes

Odds are time-sensitive and websites may enforce access restrictions or change their markup. Confirm that scraping each source is permitted and do not treat the report’s relative percentages as independently verified expected value. The application only reports scraped values and simple calculations; it does not validate lines, model probability, betting limits, or data freshness.
