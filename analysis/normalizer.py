import json
import requests
from typing import List
from models.odds import Odds, Projection
from scrapers import covers_games, the_odds_api
import time

def normalize_odds(odds_list: List[Odds]) -> List[Odds]:
    """
    Normalize odds data: ensure decimal format, standardize player names, etc.
    """
    normalized = []
    for odds in odds_list:
        # Only convert values that are clearly American odds.
        # Decimal odds for sports are usually in the 1.0-20.0 range,
        # so we avoid converting already-decimal values like 1.91 or 2.0.
        if odds.odds < 0:
            odds.odds = (100 / abs(odds.odds)) + 1
        elif odds.odds >= 100 or odds.odds > 20:
            odds.odds = (odds.odds / 100) + 1
        # Standardize player names (simple lowercase)
        odds.player = odds.player.lower().strip()
        normalized.append(odds)
    return normalized

def collect_all_data(sport: str = 'mlb') -> dict:
    """
    Scrape Covers and optional supplemental API data.
    """
    if sport not in {'nba', 'mlb', 'nfl', 'ncaaf'}:
        raise ValueError(f'Unsupported sport: {sport}')

    print(f"Scraping Covers {sport.upper()} picks...")
    covers_odds, covers_projs = covers_games.scrape_covers_picks_data(sport)
    covers_odds = normalize_odds(covers_odds)
    time.sleep(2)
    
    print("Scraping the odds API...")
    try:
        api_markets = 'h2h,spreads,totals'
        api_odds = normalize_odds(the_odds_api.scrape_the_odds_api(sport=sport, markets=api_markets))
    except ValueError as exc:
        print(f"Skipping Odds API source: {exc}")
        api_odds = []
    except requests.RequestException as exc:
        print(f"Skipping Odds API source after request failure: {exc}")
        api_odds = []
    
    all_odds = covers_odds + api_odds
    all_projections = covers_projs
    
    data = {
        'odds': [odds.__dict__ for odds in all_odds],
        'projections': [proj.__dict__ for proj in all_projections],
        'timestamp': __import__('datetime').datetime.now().isoformat()
    }
    
    return data

def save_data_to_json(data: dict, filename: str = 'odds_data.json'):
    """
    Save data to JSON file
    """
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Data saved to {filename}")