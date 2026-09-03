# MLB Odds Parsing Project

A small Python scraper and reporting pipeline for consolidating MLB and NCAAF betting odds, normalizing them into a common model, comparing bookmakers, filtering records, and generating an HTML review.

This repository is best understood as a prototype. The data model and reporting path are present, but some source integrations still contain placeholder selectors or incomplete projection matching. Treat the generated report as an inspection aid, not as a production betting or pricing system.

## What It Does

`main.py` runs this pipeline:

1. For MLB, scrapes odds from CrazyNinjaOdds, OddsShark, Action Network, and The Odds API, plus projections from Covers.
2. For NCAAF, scrapes CrazyNinjaOdds positive-EV rows, Covers game prices, and The Odds API game markets (`h2h`, `spreads`, and `totals`). The other sources are baseball-specific and are not called.
3. Normalizes scraped odds to decimal format and lowercases player/event keys.
4. Reconstructs `Odds` and `Projection` dataclass objects.
5. Filters odds by bookmaker, minimum decimal odds, optional EV, and market.
6. Removes per-player/per-market outliers with z-score or IQR filtering.
7. Groups odds and projections by event, market, and selection when source metadata is available.
8. Calculates a bookmaker-relative percentage, identifies the best decimal odds, and calculates an unweighted average (“Blended Score”).
9. Ranks five unique CrazyNinjaOdds NCAAF opportunities by the source-published EV, then ranks the remaining market groups by best-price difference versus the market median.
10. Writes an HTML report and saves the unfiltered scrape data as JSON.

The project does not place bets, persist historical runs, expose an API, or provide a web server.

## AI Handoff: Goals And Progress

### Project Goals

- Collect current sports odds from multiple sources.
- Normalize bookmaker, event, market, selection, and price data into shared records.
- Compare available prices and identify the strongest value opportunities.
- Produce a readable HTML report, including a ranked NCAAF top-five summary.
- Keep the pipeline easy for another AI session to inspect, test, and extend.

### Completed Progress

- Added `--sport mlb|ncaaf` routing while preserving the MLB path.
- Added The Odds API support for `baseball_mlb` and `americanfootball_ncaaf`.
- Added the Covers NCAAF picks-page integration for listed game prices.
- Added the CrazyNinjaOdds NCAAF `league=3` integration using the positive-EV page.
- Added odds metadata for event, selection, line, fair odds, and source-published EV.
- Added event/market/selection grouping support for records that provide those fields.
- Added a deduplicated “Top 5 CrazyNinja Value Opportunities” report table.
- Updated this README with setup, runtime behavior, limitations, and continuation guidance.

### Current Working Behavior

- MLB uses the existing CrazyNinjaOdds, Covers, OddsShark, Action Network, and The Odds API paths.
- NCAAF uses CrazyNinjaOdds, Covers, and The Odds API.
- The NCAAF top-five table ranks unique CNO opportunities by CNO's published EV and shows offered versus fair odds.
- NCAAF value ranking combines CNO published EV (50%), positive Covers score support (30%), and best-price market difference (20%). Spread support compares the Covers projected margin with the selected spread; total support compares projected total points with the over/under line.
- The detailed NCAAF report is ordered by the weighted value score, which includes market difference and market preference. Each market identifies the event, market type, selection, best sportsbook, line, all retained books, and the market's median reference price.
- NCAAF market preference favors full-game spreads, first-half/first-quarter spreads, totals, and then moneylines. CNO supplies first-half and first-quarter markets; The Odds API supplies stable full-game spreads and totals.
- Regional sportsbook duplicates from CrazyNinjaOdds are collapsed to one opportunity before ranking.

### Next AI Session Checklist

1. Run a fresh NCAAF collection and confirm the CNO parser returns records from the live page.
2. Inspect the generated top-five table for correct event, selection, market, sportsbook, and odds values.
3. Add fixture-based tests for CNO detail-line parsing and American-to-decimal conversion.
4. Extract stable matchup identifiers from Covers so its prices can join CNO and API records.
5. Revisit `--min-ev`; it currently filters before comparison EV is calculated and should be separated from CNO's source EV.
6. Add `numpy` to `requirements.txt` and improve source-level error handling.

When continuing work, preserve the distinction between CNO's published EV and the comparator's percentage relative to a bookmaker/reference price. They are different signals and should not share the same field without an explicit decision.

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
  crazyninjaodds.py        Multi-market Selenium scraper
  crazyninjaodds_ncaaf.py  CrazyNinjaOdds NCAAF positive-EV scraper
  covers.py                Selenium projection scraper
  covers_ncaaf.py          Covers NCAAF game-picks scraper
  oddsshark.py             Requests/BeautifulSoup scraper
  actionnetwork.py         Requests/BeautifulSoup scraper
  the_odds_api.py         Optional The Odds API integration
odds_data.json             Checked-in example/raw output
odds_report.html           Checked-in example report
```

## Requirements

- Python 3
- Packages listed in `requirements.txt`
- Google Chrome, because CrazyNinjaOdds and Covers use Selenium
- Internet access to the scraped sites
- `ODDS_API_KEY` only when The Odds API source should be included

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

Basic run, writing the default report to `odds_report.html`:

```bash
python main.py
```

Collect NCAAF odds through The Odds API:

```bash
export ODDS_API_KEY="your-key"
python main.py --sport ncaaf --outlier-method none --output odds_report_ncaaf.html
```

The run always writes raw collected data to `odds_data.json`, even when a different HTML output path is supplied.

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
| `--sport` | `mlb` | `mlb` runs the existing baseball scrapers; `ncaaf` uses The Odds API with the `americanfootball_ncaaf` sport key. |
| `--market` | `all` | Keep one normalized market, such as `home_runs`, `home_run`, or `first_inning_total_runs`. The exact value must match scraper output. |
| `--output` | `odds_report.html` | HTML report path. Parent directories must already exist. |
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

- `scrapers/actionnetwork.py` and `scrapers/oddsshark.py` use selectors marked `Placeholder`; they may return no records or break when site markup changes.
- `scrapers/covers.py` currently creates projections with `player="Unknown"` and `market="unknown"` when it finds a projection value. Those projections will not join normal odds groups, so the report commonly has empty projection tables.
- `scrapers/crazyninjaodds.py` contains unreachable legacy parsing code after an earlier `return`. Preserve or remove it only after confirming the active table parser is complete.
- CrazyNinjaOdds creates a new headless browser for every market and waits 10 seconds for each one, so collection can be slow and resource-heavy.
- `--min-ev` is currently unreliable: it filters before `analyze_comparisons()` assigns the relative percentage to `Odds.ev`. With the usual scraped records, setting it can remove records whose `ev` is still `None`.
- The default minimum odds filter runs before comparison and may exclude otherwise useful prices.
- The default bookmaker list includes `NoviG`; matching is case-insensitive, so it matches `Novig`, but bookmaker aliases are not otherwise normalized.
- The Odds API integration defaults to game-level `h2h`, `spreads`, and `totals` markets. NCAAF also imports CrazyNinjaOdds positive-EV rows and Covers game-market prices. The Covers parser does not yet import the page's player-projection recommendations or predicted-score values.
- NCAAF reports include a “Top 5 CrazyNinja Value Opportunities” table. It deduplicates regional sportsbook rows by event, market, and selection, then ranks by CrazyNinjaOdds' published EV and displays the offered and fair odds.
- Covers NCAAF prices are collected into the report, but they are not yet event-joined to CNO rows because the page parser does not currently extract a stable matchup identifier.
- The checked-in `odds_data.json` and `odds_report.html` are snapshots, not guaranteed current data.
- Generated report headings use the selected sport (`MLB` or `NCAAF`).
- There are no test files or configuration files in the repository. When changing parsing or matching, add fixture-based tests before relying on live websites.

## Recommended Continuation Order

1. Add `numpy` to `requirements.txt`.
2. Add request timeouts, browser cleanup guarantees, and source-level error handling.
3. Replace placeholder selectors with fixture-backed parsers for each site.
4. Add NCAAF projections or additional college-football sources if model-based analysis is needed.
5. Make Covers extract the actual player, market, and projection meaning.
6. Normalize bookmaker aliases and market names in one shared layer.
7. Move EV/reference calculation before `--min-ev`, or rename the option to reflect that it is a relative percentage.
8. Add tests for odds conversion, normalization, grouping, outlier behavior, and report rendering.

## Output And Safety Notes

Odds are time-sensitive and websites may enforce access restrictions or change their markup. Confirm that scraping each source is permitted and do not treat the report’s relative percentages as independently verified expected value. The application only reports scraped values and simple calculations; it does not validate lines, model probability, betting limits, or data freshness.
