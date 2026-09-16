import re
from datetime import datetime
from typing import List

import requests
from bs4 import BeautifulSoup

from models.odds import Odds, Projection


SPORT_URLS = {
    'nba': 'https://www.covers.com/picks/nba',
    'mlb': 'https://www.covers.com/picks/mlb',
    'nfl': 'https://www.covers.com/picks/nfl',
    'ncaaf': 'https://www.covers.com/picks/ncaaf',
}

TEAM_ALIASES = {
    'nfl': {
        'ari': 'Arizona Cardinals', 'atl': 'Atlanta Falcons', 'bal': 'Baltimore Ravens',
        'buf': 'Buffalo Bills', 'car': 'Carolina Panthers', 'chi': 'Chicago Bears',
        'cin': 'Cincinnati Bengals', 'cle': 'Cleveland Browns', 'dal': 'Dallas Cowboys',
        'den': 'Denver Broncos', 'det': 'Detroit Lions', 'gb': 'Green Bay Packers',
        'hou': 'Houston Texans', 'ind': 'Indianapolis Colts', 'jax': 'Jacksonville Jaguars',
        'kc': 'Kansas City Chiefs', 'lv': 'Las Vegas Raiders', 'lac': 'Los Angeles Chargers',
        'lar': 'Los Angeles Rams', 'mia': 'Miami Dolphins', 'min': 'Minnesota Vikings',
        'ne': 'New England Patriots', 'no': 'New Orleans Saints', 'nyg': 'New York Giants',
        'nyj': 'New York Jets', 'phi': 'Philadelphia Eagles', 'pit': 'Pittsburgh Steelers',
        'sf': 'San Francisco 49ers', 'sea': 'Seattle Seahawks', 'tb': 'Tampa Bay Buccaneers',
        'ten': 'Tennessee Titans', 'was': 'Washington Commanders',
    },
}


def _event_for_card(card) -> tuple[str | None, dict[str, str]]:
    """Extract a readable matchup and team aliases from a Covers game card."""
    link = card.select_one('a[aria-label*=" at "]')
    if not link:
        return None, {}

    label = link.get('aria-label', '')
    match = re.search(r'for (.+?) at (.+?)$', label, re.IGNORECASE)
    if not match:
        return None, {}

    away, home = match.groups()
    event = f'{away} @ {home}'
    aliases = {}
    for team in (away, home):
        words = re.findall(r'[A-Za-z]+', team)
        aliases[''.join(word[0] for word in words).lower()] = team
        aliases[''.join(words[0])[:3].lower()] = team
        aliases[''.join(words[-1])[:3].lower()] = team
    return event, aliases


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
    odds_list, _ = scrape_covers_picks_data('ncaaf')
    return odds_list


def scrape_covers_ncaaf_data():
    """Return Covers NCAAF game prices and predicted-score projections."""
    return scrape_covers_picks_data('ncaaf')


def scrape_covers_picks_data(sport: str):
    """Return Covers game prices and predicted-score projections for a sport."""
    if sport not in SPORT_URLS:
        raise ValueError(f'Unsupported Covers sport: {sport}')

    response = requests.get(SPORT_URLS[sport], timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
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

        card = row.find_parent(id=re.compile(r'^computer-picks-\d+$'))
        event, aliases = _event_for_card(card) if card else (None, {})
        team_code = team.split()[0].lower()
        full_team = TEAM_ALIASES.get(sport, {}).get(team_code, aliases.get(team_code, team))
        player = full_team.lower()

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
                player=player,
                timestamp=timestamp,
                source=f'Covers{sport.upper()}',
                event=event,
                selection=(
                    f'{full_team} {cells[index].get_text(" ", strip=True).split()[0]}'
                    if market != 'moneyline'
                    else full_team
                ),
                line=cells[index].get_text(' ', strip=True).split()[0] if market != 'moneyline' else None,
            ))

    return odds_list, projections