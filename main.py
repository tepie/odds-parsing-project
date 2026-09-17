#!/usr/bin/env python3
import argparse
import sys
import os
sys.path.append(os.path.dirname(__file__))

from analysis.normalizer import collect_all_data, save_data_to_json
from analysis.comparator import (
    group_odds_by_player_market,
    analyze_comparisons,
    find_top_value_bets,
    projection_recommendation,
    events_match,
)
from analysis.outliers import remove_outliers
from reports.generator import generate_html_report
from datetime import datetime

def decimal_to_american(decimal_odds):
    if decimal_odds >= 2.0:
        return int((decimal_odds - 1) * 100)
    else:
        return int(-100 / (decimal_odds - 1))

def main():
    parser = argparse.ArgumentParser(description='Consolidate Covers sports odds review')
    parser.add_argument('--sport', type=str, default='mlb', choices=['nba', 'mlb', 'nfl', 'ncaaf'], help='Sport to collect (nba, mlb, nfl, or ncaaf)')
    parser.add_argument('--market', type=str, default='all', help='Market to focus on (e.g., home_run)')
    parser.add_argument('--output', type=str, default=None, help='Optional HTML output file')
    parser.add_argument('--outlier-method', type=str, default='zscore', choices=['zscore', 'iqr', 'none'], help='Outlier detection method')
    parser.add_argument('--bookmakers', nargs='+', default=None, help='Optional list of bookmakers to include; defaults to all discovered books')
    parser.add_argument('--min-odds', type=float, default=1.0, help='Minimum decimal odds to include (default: 1.0; retain all listed game prices)')
    parser.add_argument('--min-ev', type=float, default=None, help='Minimum EV to include (e.g., -0.10 for -10%% or better)')
    parser.add_argument('--limit', type=int, default=None, help='Maximum number of ranked results to print')
    parser.add_argument('--include-odds-api', action='store_true', help='Also query The Odds API; Covers is used by default')
    
    args = parser.parse_args()
    
    print("Collecting data from all sources...")
    data = collect_all_data(args.sport, include_api=args.include_odds_api)
    
    # Convert back to objects
    from models.odds import Odds, Projection
    odds_list = [Odds(**o) for o in data['odds']]
    projections = [Projection(**p) for p in data['projections']]
    
    # Filter by bookmakers
    if args.bookmakers:
        allowed_bookmakers = [b.lower() for b in args.bookmakers]
        odds_list = [o for o in odds_list if o.bookmaker.lower() in allowed_bookmakers]
    
    # Filter by minimum odds
    odds_list = [o for o in odds_list if o.odds >= args.min_odds]
    
    # Filter by minimum EV if specified
    if args.min_ev is not None:
        odds_list = [o for o in odds_list if o.ev is not None and o.ev >= args.min_ev]
    
    # Filter by market if specified
    if args.market != 'all':
        odds_list = [o for o in odds_list if o.market == args.market]
        projections = [p for p in projections if p.market == args.market]
    
    # Remove outliers
    if args.outlier_method != 'none':
        # Group and remove outliers per group
        grouped = {}
        for odds in odds_list:
            key = f"{odds.player}_{odds.market}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(odds)
        
        filtered_odds = []
        for key, odds_group in grouped.items():
            filtered_odds.extend(remove_outliers(odds_group, args.outlier_method))
        odds_list = filtered_odds
    
    print("Analyzing comparisons...")
    comparisons = group_odds_by_player_market(odds_list, projections)
    analyzed = analyze_comparisons(comparisons)
    
    timestamp = datetime.now().isoformat()
    top_value_bets = find_top_value_bets(analyzed) if args.sport == 'ncaaf' else []
    print(f"\n{args.sport.upper()} Covers odds summary ({len(odds_list)} retained prices)")
    print("=" * 88)
    def ranking_key(item):
        best = item.best_odds
        score_edge = best.score_edge if best and best.score_edge and best.score_edge > 0 else -1
        return score_edge

    comparisons_with_model_edges = [
        item for item in analyzed.values()
        if item.best_odds and item.best_odds.score_edge is not None
        and item.best_odds.score_edge > 0
    ]
    ranked_comparisons = sorted(
        comparisons_with_model_edges or analyzed.values(),
        key=ranking_key,
        reverse=True,
    )
    if args.limit is not None:
        if args.limit < 1:
            parser.error('--limit must be at least 1')
        ranked_comparisons = ranked_comparisons[:args.limit]

    for comparison in ranked_comparisons:
        best = comparison.best_odds
        if not best:
            continue
        event = best.event or best.player
        selection = best.selection or best.player
        projection = next(
            (
                item for item in projections
                if item.event and best.event and events_match(best.event, item.event)
            ),
            None,
        )
        if not projection or best.score_edge is None:
            continue
        predicted = f"{projection.away_score:.2f}-{projection.home_score:.2f}"
        direction = projection_recommendation(best) or selection
        print(
            f"{event} | predicted: {predicted} | "
            f"{comparison.market:<10} | {direction:<34} | "
            f"projection edge: {best.score_edge:+.2f} pts"
        )

    if args.output:
        generate_html_report(analyzed, timestamp, args.output, sport=args.sport.upper(), top_value_bets=top_value_bets)
    
    # Persist the analyzed odds so projection and comparison fields are visible
    # in odds_data.json instead of saving the pre-analysis scrape only.
    data["odds"] = [odds.__dict__ for odds in odds_list]
    save_data_to_json(data, 'odds_data.json')
    
    print("Done!")

if __name__ == '__main__':
    main()