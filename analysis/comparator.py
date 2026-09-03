from typing import List, Dict
from collections import defaultdict
from models.odds import Odds, Projection, OddsComparison
import statistics
import re


MARKET_PREFERENCE = {
    'spread': 1.15,
    'spread_h1': 1.10,
    'spread_q1': 1.05,
    'total': 1.00,
    'total_h1': 0.95,
    'total_q1': 0.90,
    'moneyline': 0.70,
}


def odds_group_key(odds: Odds) -> str:
    if odds.event and odds.selection:
        return f'{odds.event.lower().strip()}_{odds.market}_{odds.selection.lower().strip()}'
    return f'{odds.player}_{odds.market}'


def find_top_value_bets(comparisons: Dict[str, OddsComparison], limit: int = 5) -> List[Odds]:
    """Return unique CrazyNinja opportunities ranked by its published EV."""
    candidates = []
    for comparison in comparisons.values():
        candidates.extend(
            odds for odds in comparison.odds_list
            if odds.source == 'CrazyNinjaOddsNCAAF' and odds.source_ev is not None
        )

    unique = {}
    for odds in candidates:
        key = (odds.event or odds.player, odds.market, odds.selection or odds.player)
        if key not in unique or odds.source_ev > unique[key].source_ev:
            unique[key] = odds

    return sorted(
        unique.values(),
        key=lambda odds: (odds.combined_value_score or odds.source_ev) * MARKET_PREFERENCE.get(odds.market, 0.85),
        reverse=True,
    )[:limit]


def events_match(first: str, second: str) -> bool:
    first_parts = [part.strip().lower() for part in first.split('@', 1)]
    second_parts = [part.strip().lower() for part in second.split('@', 1)]
    return len(first_parts) == 2 and len(second_parts) == 2 and all(
        left in right or right in left
        for left, right in zip(first_parts, second_parts)
    )


def calculate_score_edge(odds: Odds, projection: Projection) -> float:
    if not odds.selection or not projection.event:
        return 0
    if odds.market == 'spread':
        match = re.search(r'(.+?)\s+([+-]?\d+(?:\.\d+)?)$', odds.selection)
        if not match or projection.projected_spread is None:
            return 0
        team = match.group(1).lower().strip()
        line = float(match.group(2))
        away, home = [part.strip().lower() for part in projection.event.split('@', 1)]
        team_margin = projection.projected_spread if team in home else -projection.projected_spread if team in away else None
        return team_margin + line if team_margin is not None else 0
    if odds.market == 'total':
        match = re.search(r'([ou])\s*([+-]?\d+(?:\.\d+)?)$', odds.selection, re.IGNORECASE)
        if not match or projection.projected_total is None:
            return 0
        line = float(match.group(2))
        return projection.projected_total - line if match.group(1).lower() == 'o' else line - projection.projected_total
    return 0


def attach_score_value(odds: Odds, projections: List[Projection]) -> None:
    if not odds.event:
        return
    for projection in projections:
        if projection.event and events_match(odds.event, projection.event):
            odds.projected_spread = projection.projected_spread
            odds.projected_total = projection.projected_total
            odds.score_edge = calculate_score_edge(odds, projection)
            odds.score_support = min(max(odds.score_edge, 0) * 10, 100)
            return

def calculate_ev(odds: Odds, projection: Projection = None) -> float:
    """
    Calculate expected value. Simplified: EV = (implied_prob * (odds - 1)) - (1 - implied_prob)
    But for positive EV bets.
    """
    implied_prob = 1 / odds.odds
    if projection:
        true_prob = projection.projection / 100  # assume projection is percentage
        ev = (true_prob * (odds.odds - 1)) - ((1 - true_prob) * 1)
    else:
        ev = 0  # no projection
    odds.ev = ev
    return ev

def group_odds_by_player_market(odds_list: List[Odds], projections: List[Projection]) -> Dict[str, OddsComparison]:
    """
    Group odds and projections by player and market
    """
    comparisons = defaultdict(lambda: OddsComparison(player='', market='', odds_list=[], projections=[]))
    
    for odds in odds_list:
        key = odds_group_key(odds)
        if not comparisons[key].player:
            comparisons[key].player = odds.player
            comparisons[key].market = odds.market
        comparisons[key].odds_list.append(odds)
    
    for proj in projections:
        key = f"{proj.player}_{proj.market}"
        comparisons[key].projections.append(proj)
    
    return dict(comparisons)

def find_best_odds(comparison: OddsComparison) -> Odds:
    """
    Find the odds with highest decimal (best payout)
    """
    if not comparison.odds_list:
        return None
    return max(comparison.odds_list, key=lambda o: o.odds)

def calculate_blended_score(comparison: OddsComparison) -> float:
    """
    Blended score: average odds weighted by book reliability or simple average
    """
    if not comparison.odds_list:
        return 0
    odds_values = [o.odds for o in comparison.odds_list]
    return statistics.mean(odds_values)


def calculate_market_difference(comparison: OddsComparison) -> float:
    """Measure the best price against the market median as a percentage."""
    if not comparison.odds_list:
        return 0
    prices = [odds.odds for odds in comparison.odds_list]
    reference = statistics.median(prices)
    best = max(prices)
    comparison.reference_odds = reference
    return ((best - reference) / reference) * 100 if reference else 0

def analyze_comparisons(comparisons: Dict[str, OddsComparison]) -> Dict[str, OddsComparison]:
    """
    Analyze each comparison: calculate EVs or % diff from sharp, find best, blended score
    """
    sharp_bookmakers = {'pinnacle', 'circa'}
    projections = [projection for comparison in comparisons.values() for projection in comparison.projections]
    
    for key, comp in comparisons.items():
        # Find sharp odds (highest from Pinnacle or Circa, or fallback to best odds)
        sharp_odds = None
        for odds in comp.odds_list:
            if any(sb in odds.bookmaker.lower() for sb in sharp_bookmakers):
                if sharp_odds is None or odds.odds > sharp_odds:
                    sharp_odds = odds.odds
        
        # If no sharp bookmaker, use the best odds as reference
        if sharp_odds is None:
            sharp_odds = max((o.odds for o in comp.odds_list), default=None)
        
        # Calculate % diff from sharp for each odds
        for odds in comp.odds_list:
            if sharp_odds is not None:
                odds.ev = ((odds.odds - sharp_odds) / sharp_odds) * 100
            else:
                odds.ev = None
            attach_score_value(odds, projections)
        
        comp.best_odds = find_best_odds(comp)
        comp.blended_score = calculate_blended_score(comp)
        comp.market_difference = calculate_market_difference(comp)
        cno_values = [o.source_ev for o in comp.odds_list if o.source_ev is not None]
        best_cno = max((o for o in comp.odds_list if o.source_ev is not None), key=lambda o: o.source_ev, default=None)
        if best_cno:
            best_cno.combined_value_score = (
                (best_cno.source_ev * 0.5)
                + ((best_cno.score_support or 0) * 0.3)
                + (comp.market_difference * 0.2)
            )
            comp.value_score = best_cno.combined_value_score * MARKET_PREFERENCE.get(best_cno.market, 0.85)
        else:
            comp.value_score = comp.market_difference * MARKET_PREFERENCE.get(comp.market, 0.85)
    
    return comparisons