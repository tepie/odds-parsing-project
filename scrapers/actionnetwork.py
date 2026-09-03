import requests
from bs4 import BeautifulSoup
from typing import List
from datetime import datetime
from models.odds import Odds

def scrape_actionnetwork() -> List[Odds]:
    """
    Scrape home run props from actionnetwork.com
    """
    url = "https://www.actionnetwork.com/mlb/props/home-runs"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html5lib')
    
    odds_list = []
    
    # Find prop elements
    prop_cards = soup.find_all('div', class_='prop-card')  # Placeholder
    
    for card in prop_cards:
        try:
            player = card.find('h3').text.strip()
            bookmaker = card.find('span', class_='book').text.strip()
            odds_str = card.find('span', class_='odds').text.strip()
            odds = convert_to_decimal(odds_str)
            market = 'home_run'
            timestamp = datetime.now().isoformat()
            
            odds_obj = Odds(bookmaker=bookmaker, odds=odds, market=market, player=player, timestamp=timestamp, source='ActionNetwork')
            odds_list.append(odds_obj)
        except AttributeError:
            continue
    
    return odds_list

def convert_to_decimal(odds_str: str) -> float:
    try:
        odds = float(odds_str)
        if odds > 0:
            return (odds / 100) + 1
        else:
            return (100 / abs(odds)) + 1
    except ValueError:
        return float(odds_str)