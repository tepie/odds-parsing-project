import re
from datetime import datetime
from typing import List

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from models.odds import Odds


URL = ('https://crazyninjaodds.com/site/tools/positive-ev.aspx?'
       'allow_same_book_hedge=0&hedge_main=0&ev_min=0_PCT_&live=0&main=0&'
       'sport=0&league=3&books_min=3&site_id=0&sides_min=2&complete_book=1')


def american_to_decimal(odds_value: str) -> float:
    odds = float(odds_value)
    if odds > 0:
        return (odds / 100) + 1
    return (100 / abs(odds)) + 1


def normalize_market(market: str) -> str:
    normalized = re.sub(r'[^a-z0-9]+', '_', market.lower()).strip('_')
    if normalized.startswith('1st_quarter_'):
        normalized = normalized.replace('1st_quarter_', 'q1_', 1)
    if normalized.startswith('1st_half_'):
        normalized = normalized.replace('1st_half_', 'h1_', 1)
    replacements = {
        'point_spread': 'spread',
        'total_points': 'total',
        'game_moneyline': 'moneyline',
        'q1_point_spread': 'spread_q1',
        'q1_total_points': 'total_q1',
        'h1_point_spread': 'spread_h1',
        'h1_total_points': 'total_h1',
    }
    return replacements.get(normalized, normalized)


def parse_bet_line(line: str, ev: float):
    field_pattern = (
        r'Event\s*:\s*(?P<event>.*?)\s+Market\s*:\s*(?P<market>.*?)\s+'
        r'Bet Name\s*:\s*(?P<selection>.*?)\s+Odds\s*:\s*'
        r'(?P<odds>[+-]?\d+(?:\.\d+)?)(?:\s+\([^)]*\))?\s+'
        r'Sportsbook\s*:\s*(?P<book>.*?)\s+Fair Odds\s*:\s*'
        r'(?P<fair>[+-]?\d+(?:\.\d+)?)\s+Books\s*:\s*(?P<books>\d+)'
    )
    match = re.search(field_pattern, line)
    if not match:
        return None

    values = match.groupdict()
    try:
        odds = american_to_decimal(values['odds'])
        fair_odds = american_to_decimal(values['fair'])
    except ValueError:
        return None

    event = values['event'].strip()
    selection = values['selection'].strip()
    return Odds(
        bookmaker=values['book'].strip(),
        odds=odds,
        market=normalize_market(values['market']),
        player=f'{event} - {selection}'.lower(),
        timestamp=datetime.now().isoformat(),
        source='CrazyNinjaOddsNCAAF',
        event=event,
        selection=selection,
        fair_odds=fair_odds,
        source_ev=ev,
    )


def scrape_crazyninjaodds_ncaaf() -> List[Odds]:
    """Scrape CNO's positive-EV NCAAF rows from the supplied league=3 page."""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(URL)
        soup = BeautifulSoup(driver.page_source, 'html5lib')
    finally:
        driver.quit()

    lines = [line.strip() for line in soup.get_text('\n').splitlines() if line.strip()]
    odds_list: List[Odds] = []
    current_ev = None
    for line in lines:
        ev_match = re.fullmatch(r'(\d+(?:\.\d+)?)%', line)
        if ev_match:
            current_ev = float(ev_match.group(1))
            continue
        if 'Event :' not in line or current_ev is None:
            continue
        parsed = parse_bet_line(line, current_ev)
        if parsed:
            odds_list.append(parsed)

    return odds_list