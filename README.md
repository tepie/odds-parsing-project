# Covers Sports Odds Project

A public Python scraper and reporting pipeline focused on Covers.com for NBA, MLB, NFL, and NCAAF game projections and NFL/MLB player props. Game reports compare Covers predicted scores directly with spreads and totals to find the largest point differences.

This repository is the single active project consolidating the original NBA `oddsparser` experiment and the `covers-props` player-props scraper. The former `oddsparser` repository is archived, and the former `covers-props` repository has been consolidated here. Covers is the default game source; The Odds API is opt-in only. Treat generated reports as inspection aids, not production betting or pricing systems.

## What It Does

`main.py` runs the game-odds pipeline:

1. Scrapes Covers game lines and predicted scores for NBA, MLB, NFL, or NCAAF.
2. Normalizes the game records and joins each market to its Covers predicted score.
3. Calculates spread differences from the projected margin and total differences from the projected total.
4. Sorts game recommendations by the largest positive projection edge.
5. Prints only the matchup, predicted score, selection, and projection edge for console game output.
6. Saves analyzed records to JSON. An HTML report is optional.

The Odds API is not queried unless `--include-odds-api` is explicitly supplied. Its prices are supplemental data only and do not define the projection-edge ranking.

The `props/covers_props.py` command separately collects NFL or MLB props from Covers' client-rendered props pages and can print a table or write JSON/CSV. The project does not place bets, persist historical runs, expose an API, or provide a web server.

`run_all.py` is the consolidated entry point. It checks all four game sports and both supported props sports, then prints one global ranking of the strongest collected edges.

## AI Handoff: Goals And Progress

### Project Goals

- Collect current Covers game lines and predicted scores.
- Normalize event, market, selection, and price data into shared records.
- Identify the largest differences between Covers projections and posted spreads/totals.
- Preserve the original NBA use case as an explicit sport filter.
- Make Covers the primary and maintained odds source across NBA, MLB, NFL, and NCAAF.
- Produce useful console output by default for each selected sport.
- Collect NFL and MLB props with projection edge, EV, visible odds, and game context.
- Keep the pipeline easy for another AI session to inspect, test, and extend.

### Completed Progress

- Added `--sport nba|mlb|nfl|ncaaf` routing.
- Added Covers picks-page collection for NBA, MLB, NFL, and NCAAF.
- Added The Odds API support for NBA, MLB, NFL, and NCAAF as an optional supplement.
- Added odds metadata for event, selection, line, fair odds, and source-published EV.
- Added event/market/selection grouping support for records that provide those fields.
- Replaced the active OddsShark, Action Network, and CrazyNinja collection paths with Covers.
- Consolidated the `covers-props` scraper into `props/` as the NFL/MLB player-props workflow.
- Archived the former `oddsparser` GitHub repository; its local clone is no longer retained.
- Removed the former `covers-props` local clone after consolidating its implementation here.
- Updated this README with setup, runtime behavior, limitations, and continuation guidance.

### Current Working Behavior

- NBA, MLB, NFL, and NCAAF use the corresponding Covers picks page.
- The Odds API is opt-in only and is not queried during normal Covers scans.
- Covers predicted-score data is retained as projections when the page exposes it.
- NFL and MLB props are collected with Playwright and ranked by Covers' displayed Difference field.

### Next AI Session Checklist

1. Run fresh NBA, MLB, NFL, and NCAAF collections and confirm predicted scores join to every game card.
2. Add fixture-based tests for current Covers game-card markup and projection-edge calculations.
3. Extract stable matchup identifiers from Covers so lines and projections join reliably.
4. Improve source-level error handling and preserve the Covers-only default.

When continuing work, preserve the distinction between the Covers projection edge and any optional bookmaker-price comparison. Projection edge is the primary game signal; price comparison is not part of the normal game ranking.

## Repository Layout

```text
main.py                    CLI entry point and orchestration
requirements.txt           Python dependencies
models/odds.py             Odds, Projection, and OddsComparison dataclasses
analysis/normalizer.py     Scraping orchestration, normalization, JSON output
analysis/comparator.py     Projection-edge calculations and shared grouping
analysis/outliers.py       Z-score and IQR filtering
reports/generator.py       Inline Jinja2 HTML report template
scrapers/
  covers.py                Legacy Covers player-projection scraper
  covers_games.py          Covers NBA/MLB/NFL/NCAAF game-picks scraper
  the_odds_api.py          Optional The Odds API integration
props/
  covers_props.py          Covers NFL/MLB player-props scraper and CLI
  run_covers_props.sh      Props launcher using the repository environment
odds_data.json             Local generated scan data (ignored)
odds_report.html           Local generated report (ignored)
```

`odds_data.json` and generated `odds_report*.html` files are local scan artifacts. They are intentionally ignored by Git and are not part of the committed project.

## Requirements

- Python 3
- Packages listed in `requirements.txt`
- Internet access to Covers and optionally The Odds API
- Internet access to the scraped sites
- `ODDS_API_KEY` only when The Odds API source should be included
- Playwright Chromium for the NFL and MLB props workflows

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

Basic console run (the default reporting mode):

```bash
python main.py
```

Collect NBA projection edges from Covers:

```bash
python main.py --sport nba --outlier-method none --limit 10
```

For console-only game output, omit `--output`:

```bash
python main.py --sport nfl --outlier-method none
```

Run only the NCAAF game-edge scan:

```bash
./.venv/bin/python main.py --sport ncaaf --outlier-method none
```

This collects NCAAF game odds from Covers and prints the projection-edge results to the console. Covers is the default and only source unless `--include-odds-api` is explicitly supplied.

Game results are ranked only by the Covers predicted-score difference versus the spread or total line. For example, a predicted 39.10-19.02 score implies a 20.08-point margin; compared with Miami -20.5, the spread model edge is -0.42 points, while Wake +20.5 is +0.42 points. The console output shows only the matchup, predicted score, market selection, and projection edge. Bookmaker price differences are not part of this ranking. The scan also flags potential moneyline upsets when the Covers projected winner differs from the market favorite. The score projection is a model signal, not a guarantee or a true moneyline probability.

Limit the output to the ten highest-ranked NCAAF edges:

```bash
./.venv/bin/python main.py --sport ncaaf --outlier-method none --limit 10
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

Run the complete cross-sport scan and print one global edge ranking:

```bash
./run_all.sh
```

The scan checks NBA, MLB, NFL, and NCAAF game odds, then NFL and MLB player props. Covers is used by default. Add `--include-odds-api` if The Odds API prices should be included:

```bash
export ODDS_API_KEY="your-api-key"
./run_all.sh --limit 25 --include-odds-api
```

`--limit` controls both the number of props considered per props sport and the number of global results printed. Use `--outlier-method zscore` or `--outlier-method iqr` to enable game-odds outlier filtering.

The game-odds run writes the analyzed collected data to local `odds_data.json`, even when no HTML output is requested. HTML generation is optional and is enabled only when `--output` is supplied. These generated files are ignored by Git.

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
python main.py --sport ncaaf --include-odds-api --limit 10
```

The default game scan does not query The Odds API, so it does not consume API credits. Other request or Selenium failures are not generally caught by the orchestration layer and may stop the run.

## CLI Options

| Option | Default | Meaning |
| --- | --- | --- |
| `--sport` | `mlb` | `nba`, `mlb`, `nfl`, or `ncaaf`; Covers is queried for the selected sport. |
| `--market` | `all` | Keep one normalized market, such as `home_runs`, `home_run`, or `first_inning_total_runs`. The exact value must match scraper output. |
| `--output` | unset | Optional HTML report path. Omit it for console-only output. |
| `--outlier-method` | `zscore` | `zscore`, `iqr`, or `none`; filtering is performed separately for each player/market group. |
| `--bookmakers` | unset | Optional bookmaker filter for raw records; it does not affect projection-edge ranking. |
| `--min-odds` | `1.0` | Minimum decimal odds retained. The default keeps every listed game price. |
| `--min-ev` | unset | Legacy filter for raw odds records; it is not used by the projection-edge calculation. |
| `--limit` | unset | Maximum number of ranked results printed. Results are sorted by the largest positive Covers projection edge first. |
| `--include-odds-api` | off | Opt in to querying The Odds API. Covers remains the projection source. |

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

## Projection-Edge Semantics

- For a spread, Covers' predicted margin is compared with each side's posted line. A larger positive difference means the projection supports that side by more points.
- For a total, Covers' predicted total is compared with the posted total. The result identifies an `OVER` or `UNDER` projection edge.
- Results are sorted by the positive point difference, not by bookmaker, number of books, odds payout, or price edge.
- Moneyline upset flags identify cases where Covers' projected winner differs from the market favorite. They are directional signals, not calibrated win probabilities.
- American odds are converted to decimal odds for storage, but odds price is not part of the normal game-edge score.

## Current Limitations And Next Work

These are the most important facts for the next contributor:

- The Covers HTML structure may change and the current parser depends on recognizable picks tables and matchup links.
- Covers HTML structure may change and the current parser depends on recognizable picks tables and matchup cards.
- Projection joins depend on event labels and team aliases exposed by Covers.
- The optional Odds API integration is not part of the default projection-edge calculation.
- Props and game projection edges use different scales and should be interpreted separately.
- The legacy scraper modules remain in the tree for reference but are not active collection sources.
- The props workflow requires a browser because Covers renders player props client-side.
- `odds_data.json` and `odds_report*.html` are generated locally and intentionally not committed.
- Generated report headings use the selected sport (`NBA`, `MLB`, `NFL`, or `NCAAF`).
- Unit tests cover odds conversion, market-cell parsing, normalization, supported sports, player-prop parsing, and exclusion of game projections from player props.

## Recommended Continuation Order

1. Add request timeouts, browser cleanup guarantees, and source-level error handling.
2. Replace table assumptions with fixture-backed Covers parsers for NBA, MLB, NFL, and NCAAF.
3. Extract stable matchup identifiers and normalize team aliases and market names.
4. Keep The Odds API isolated as an explicit opt-in supplemental source.
5. Expand fixture-based tests for live Covers HTML variations and player-props market selectors.

## Validation

Run the local unit tests and syntax checks:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q main.py run_all.py analysis models props reports scrapers tests
```

Live Covers checks require network access and should be run manually through `./run_all.sh` and the props launcher rather than treated as deterministic unit tests. Only use `--include-odds-api` when an API comparison is specifically needed.

## Output And Safety Notes

Lines and projections are time-sensitive and websites may enforce access restrictions or change their markup. Confirm that scraping each source is permitted and do not treat projection edges as independently verified expected value. The application only reports scraped values and simple calculations; it does not validate model probability, betting limits, or data freshness.
