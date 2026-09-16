import os
from typing import List, Optional
from datetime import datetime
import requests
from models.odds import Odds

ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/{sport_key}/odds"

SPORT_KEYS = {
    'nba': 'basketball_nba',
    'mlb': 'baseball_mlb',
    'nfl': 'americanfootball_nfl',
    'ncaaf': 'americanfootball_ncaaf',
}


def american_to_decimal(odds_value: Optional[float]) -> float:
    if odds_value is None:
        raise ValueError("Odds value is required")
    try:
        odds = float(odds_value)
    except (TypeError, ValueError):
        raise ValueError(f"Unsupported odds value: {odds_value}")

    if odds > 1 and odds < 20:
        return odds
    if odds > 0:
        return (odds / 100) + 1
    return (100 / abs(odds)) + 1


def build_player_name(event: dict, market_key: str, outcome: dict) -> str:
    away = event.get('away_team', '').strip()
    home = event.get('home_team', '').strip()
    name = outcome.get('name', '').strip()
    point = outcome.get('point')

    matchup = f"{away} @ {home}"
    if market_key == 'h2h':
        return f"{matchup} - {name}"
    if market_key.startswith('spreads'):
        point_text = f"{point:+g}" if isinstance(point, (int, float)) else str(point)
        return f"{matchup} - {name} {point_text}"
    if market_key.startswith('totals'):
        return f"{matchup} - {name} {point}"
    return f"{matchup} - {market_key} - {name}"


def build_selection(market_key: str, outcome: dict) -> str:
    name = outcome.get('name', '').strip()
    point = outcome.get('point')
    if market_key.startswith(('spreads', 'totals')) and point is not None:
        point_text = f"{point:+g}" if isinstance(point, (int, float)) else str(point)
        return f'{name} {point_text}'
    return name


def normalize_market_key(market_key: str) -> str:
    if market_key == 'h2h':
        return 'moneyline'
    if market_key == 'spreads':
        return 'spread'
    if market_key == 'totals':
        return 'total'
    if market_key.endswith('_h1'):
        return f'{market_key[:-3]}_h1'
    if market_key.endswith('_q1'):
        return f'{market_key[:-3]}_q1'
    return market_key


def scrape_the_odds_api(bookmakers: Optional[List[str]] = None, regions: str = 'us', markets: str = 'h2h,spreads,totals', odds_format: str = 'american', sport: str = 'mlb') -> List[Odds]:
    api_key = os.getenv('ODDS_API_KEY')
    if not api_key:
        raise ValueError('ODDS_API_KEY environment variable is not set')
    if sport not in SPORT_KEYS:
        raise ValueError(f'Unsupported sport: {sport}')

    params = {
        'apiKey': api_key,
        'regions': regions,
        'markets': markets,
        'oddsFormat': odds_format,
        'dateFormat': 'iso',
    }
    if bookmakers:
        params['bookmakers'] = ','.join(bookmakers)

    response = requests.get(ODDS_API_BASE.format(sport_key=SPORT_KEYS[sport]), params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    odds_list: List[Odds] = []
    for event in data:
        for bookmaker in event.get('bookmakers', []):
            bookmaker_name = bookmaker.get('title', '').strip()
            for market in bookmaker.get('markets', []):
                market_key = market.get('key', '')
                normalized_market = normalize_market_key(market_key)
                for outcome in market.get('outcomes', []):
                    try:
                        price = outcome.get('price')
                        decimal_odds = american_to_decimal(price)
                        player = build_player_name(event, market_key, outcome)
                        timestamp = datetime.now().isoformat()
                        odds_list.append(Odds(
                            bookmaker=bookmaker_name,
                            odds=decimal_odds,
                            market=normalized_market,
                            player=player,
                            timestamp=timestamp,
                            source='TheOddsAPI',
                            event=f"{event.get('away_team', '').strip()} @ {event.get('home_team', '').strip()}",
                            selection=build_selection(market_key, outcome),
                            line=str(outcome.get('point')) if outcome.get('point') is not None else None,
                        ))
                    except ValueError:
                        continue

    return odds_list
