import requests
from bs4 import BeautifulSoup
from typing import List
from datetime import datetime
from models.odds import Odds
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape_crazyninjaodds() -> List[Odds]:
    """
    Scrape positive EV props from crazyninjaodds.com
    """
    markets = [
        ('1st Inning Total Runs', '1st+Inning+Total+Runs', 'first_inning_total_runs'),
        ('Player Home Runs', 'Player+Home+Runs', 'home_runs'),
        ('Total Bases', 'Total+Bases', 'total_bases'),
        ('Strikeouts Thrown', 'Strikeouts+Thrown', 'strikeouts'),
        ('Outs Recorded', 'Outs+Recorded', 'outs_recorded'),
    ]
    
    all_odds = []
    
    for market_name, sv_title, normalized_market in markets:
        url = f"https://crazyninjaodds.com/site/tools/positive-ev.aspx?sv_title={sv_title}&allow_same_book_hedge=0&hedge_main=0&market_name={market_name}&ev_min=-10_PCT_&live=0&main=0&sport=0&league=1&odds_min=-110&books_min=4&site_id=&sides_min=2&complete_book=1"
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        
        # Wait a bit
        import time
        time.sleep(10)
        
        soup = BeautifulSoup(driver.page_source, 'html5lib')
        driver.quit()
        
        # Find the div with the data
        data_div = soup.find('div', id='ContentPlaceHolderMain_ContentPlaceHolderRight_UpdatePanelGridView')
        if not data_div:
            continue
        
        table = data_div.find('table')
        if not table:
            continue
        
        rows = table.find_all('tr')
        odds_list = []
        for row in rows[1:]:  # skip header
            cells = row.find_all('td')
            if len(cells) >= 13:
                ev_pct = cells[0].get_text().strip()
                calc = cells[1].get_text().strip()
                extra = cells[2].get_text().strip()
                date = cells[3].get_text().strip()
                sport = cells[4].get_text().strip()
                league = cells[5].get_text().strip()
                event = cells[6].get_text().strip()
                market = cells[7].get_text().strip()
                bet_name = cells[8].get_text().strip()
                odds_full = cells[9].get_text().strip()
                bookmaker = cells[10].get_text().strip()
                fair_odds = cells[11].get_text().strip()
                books = cells[12].get_text().strip() if len(cells) > 12 else ''
                
                if market == market_name and sport == 'Baseball' and league == 'MLB':
                    # Extract odds, e.g., "-109 ($250)" -> "-109"
                    odds_str = odds_full.split()[0]
                    player = f"{event} - {bet_name}"
                    
                    try:
                        odds = convert_to_decimal(odds_str)
                        timestamp = datetime.now().isoformat()
                        
                        odds_obj = Odds(bookmaker=bookmaker, odds=odds, market=normalized_market, player=player, timestamp=timestamp, source='CrazyNinjaOdds')
                        odds_list.append(odds_obj)
                    except (ValueError, KeyError):
                        continue
        
        all_odds.extend(odds_list)
    
    return all_odds
    
    # The table is in text format, not HTML table
    text = soup.get_text()
    
    # Find the table start
    start_marker = "+ev bets:\n"
    start = text.find(start_marker)
    if start == -1:
        return []
    
    table_text = text[start + len(start_marker):]
    lines = table_text.split('\n')
    
    odds_list = []
    for line in lines:
        if '|' in line:
            print("Line with |:", repr(line))
        if '|' in line and 'Sport : Baseball' in line and 'Market : 1st Inning Total Runs' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2:
                ev_str = parts[0]
                details = parts[1]
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2:
                ev_str = parts[0]
                details = parts[1]
                
                # Parse details like "Calc : Calc Extra : Date : ... : Odds : -109 ($250) : Sportsbook : Pinnacle"
                detail_parts = details.split(' : ')
                detail_dict = {}
                i = 0
                while i < len(detail_parts) - 1:
                    key = detail_parts[i].strip()
                    value = detail_parts[i+1].strip()
                    if key in ['Calc', 'Date', 'Sport', 'League', 'Event', 'Market', 'Bet Name', 'Odds', 'Sportsbook', 'Fair Odds', 'Books']:
                        detail_dict[key] = value
                        i += 2
                    else:
                        i += 1
                
                try:
                    event = detail_dict.get('Event', '')
                    bet_name = detail_dict.get('Bet Name', '')
                    odds_full = detail_dict.get('Odds', '')
                    odds_str = odds_full.split()[0]  # remove ($250)
                    bookmaker = detail_dict.get('Sportsbook', '')
                    market = 'first_inning_total_runs'
                    player = f"{event} - {bet_name}"  # e.g., "Washington Nationals @ Miami Marlins - Under 0.5"
                    
                    odds = convert_to_decimal(odds_str)
                    timestamp = datetime.now().isoformat()
                    
                    odds_obj = Odds(bookmaker=bookmaker, odds=odds, market=market, player=player, timestamp=timestamp, source='CrazyNinjaOdds')
                    odds_list.append(odds_obj)
                except (ValueError, KeyError):
                    continue
    
    return odds_list

def convert_to_decimal(odds_str: str) -> float:
    """
    Convert American odds to decimal
    """
    try:
        odds = float(odds_str)
        if odds > 0:
            return (odds / 100) + 1
        else:
            return (100 / abs(odds)) + 1
    except ValueError:
        # Assume already decimal
        return float(odds_str)