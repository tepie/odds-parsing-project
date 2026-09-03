import re
from datetime import datetime
from typing import List

import requests
from bs4 import BeautifulSoup

from models.odds import Odds, Projection


URL = 'https://www.covers.com/picks/ncaaf'


def american_to_decimal(odds_value: str) -> float:
    odds = float(odds_value)
    if odds > 0:
        return (odds / 100) + 1
    return (100 / abs(odds)) + 1


def parse_market_cell(text: str, market: str):
    text = ' '.join(text.split())
    if text in {'', '--'}:
        return None

    if market == 'spread':
        match = re.search(r'(?P<line>[+-]?\d+(?:\.\d+)?)\s+(?P<price>[+-]\d{3,5})\s+(?P<book>.+)$', text)
    elif market == 'total':
        match = re.search(r'(?P<line>[ou]\s*\d+(?:\.\d+)?)\s+(?P<price>[+-]\d{3,5})\s+(?P<book>.+)$', text, re.IGNORECASE)
    else:
        match = re.search(r'(?P<price>[+-]\d{3,5})\s+(?P<book>.+)$', text)

    if not match:
        return None

    return match.group('price'), match.group('book').strip()


def scrape_covers_ncaaf_picks() -> List[Odds]:
    """Scrape Covers' listed NCAAF game prices from the picks page."""
    odds_list, _ = scrape_covers_ncaaf_data()
    return odds_list


def scrape_covers_ncaaf_data():
    """Return Covers NCAAF game prices and predicted-score projections."""
    response = requests.get(URL, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html5lib')
    timestamp = datetime.now().isoformat()
    odds_list: List[Odds] = []
    projections: List[Projection] = []

    for link in soup.find_all('a', href=re.compile(r'/matchup/')):
        link_text = ' '.join(link.get_text(' ', strip=True).split())
        matchup = re.search(r'for (.+?) at (.+?)(?:$|\s+\|)', link_text, re.IGNORECASE)
        if not matchup:
            continue
        event = f'{matchup.group(1).strip()} @ {matchup.group(2).strip()}'
        ancestor = link
        card_text = ''
        for _ in range(5):
            ancestor = ancestor.parent
            if not ancestor:
                break
            card_text = ' '.join(ancestor.get_text(' ', strip=True).split())
            if 'Predicted Score' in card_text and re.search(r'\d+(?:\.\d+)?\s*@\s*\d+(?:\.\d+)?', card_text):
                break
        score_match = re.search(r'Predicted Score.*?(\d+(?:\.\d+)?)\s*@\s*(\d+(?:\.\d+)?)', card_text, re.IGNORECASE)
        if score_match:
            away_score = float(score_match.group(1))
            home_score = float(score_match.group(2))
            projections.append(Projection(
                site='covers', player=event.lower(), market='score', projection=home_score - away_score,
                timestamp=timestamp, event=event, away_score=away_score, home_score=home_score,
                projected_spread=home_score - away_score, projected_total=home_score + away_score,
            ))

    for row in soup.find_all('tr'):
        cells = row.find_all(['th', 'td'])
        if len(cells) < 4:
            continue

        team = ' '.join(cells[0].get_text(' ', strip=True).split())
        if not team or team.lower() in {'team', 'matchup'}:
            continue

        for index, market in ((2, 'spread'), (3, 'total'), (4, 'moneyline')):
            if index >= len(cells):
                continue
            parsed = parse_market_cell(cells[index].get_text(' ', strip=True), market)
            if not parsed:
                continue

            price, bookmaker = parsed
            try:
                decimal_odds = american_to_decimal(price)
            except ValueError:
                continue

            odds_list.append(Odds(
                bookmaker=bookmaker,
                odds=decimal_odds,
                market=market,
                player=team.lower(),
                timestamp=timestamp,
                source='CoversNCAAF',
                line=cells[index].get_text(' ', strip=True).split()[0] if market != 'moneyline' else None,
            ))

    return odds_list, projections