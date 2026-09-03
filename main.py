#!/usr/bin/env python3
import argparse
import sys
import os
sys.path.append(os.path.dirname(__file__))

from analysis.normalizer import collect_all_data, save_data_to_json
from analysis.comparator import group_odds_by_player_market, analyze_comparisons, find_top_value_bets
from analysis.outliers import remove_outliers
from reports.generator import generate_html_report
from datetime import datetime

def decimal_to_american(decimal_odds):
    if decimal_odds >= 2.0:
        return int((decimal_odds - 1) * 100)
    else:
        return int(-100 / (decimal_odds - 1))

def main():
    parser = argparse.ArgumentParser(description='Consolidate sports odds review')
    parser.add_argument('--sport', type=str, default='mlb', choices=['mlb', 'ncaaf'], help='Sport to collect (mlb or ncaaf)')
    parser.add_argument('--market', type=str, default='all', help='Market to focus on (e.g., home_run)')
    parser.add_argument('--output', type=str, default='odds_report.html', help='Output HTML file')
    parser.add_argument('--outlier-method', type=str, default='zscore', choices=['zscore', 'iqr', 'none'], help='Outlier detection method')
    parser.add_argument('--bookmakers', nargs='+', default=None, help='Optional list of bookmakers to include; defaults to all discovered books')
    parser.add_argument('--min-odds', type=float, default=1.909, help='Minimum decimal odds to include (default: 1.909 = -110 or better)')
    parser.add_argument('--min-ev', type=float, default=None, help='Minimum EV to include (e.g., -0.10 for -10% or better)')
    
    args = parser.parse_args()
    
    print("Collecting data from all sources...")
    data = collect_all_data(args.sport)
    
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
    
    print("Generating report...")
    timestamp = datetime.now().isoformat()
    top_value_bets = find_top_value_bets(analyzed) if args.sport == 'ncaaf' else []
    generate_html_report(analyzed, timestamp, args.output, sport=args.sport.upper(), top_value_bets=top_value_bets)
    
    # Save raw data
    save_data_to_json(data, 'odds_data.json')
    
    print("Done!")

if __name__ == '__main__':
    main()