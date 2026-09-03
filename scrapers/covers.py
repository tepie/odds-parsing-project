import requests
from bs4 import BeautifulSoup
from typing import List
from datetime import datetime
from models.odds import Projection
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

def scrape_covers_projections() -> List[Projection]:
    """
    Scrape player prop projections from covers.com
    """
    url = "https://www.covers.com/sport/baseball/mlb/player-props"
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)
    
    # Wait for projections to load
    try:
        WebDriverWait(driver, 20).until(
            lambda driver: 'projection' in driver.page_source.lower()
        )
    except:
        print("Timeout waiting for projections")
        driver.quit()
        return []
    
    soup = BeautifulSoup(driver.page_source, 'html5lib')
    driver.quit()
    
    projections = []
    
    # Find tables
    tables = soup.find_all('table')
    for table in tables:
        if 'projection' in table.get_text().lower():
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                for cell in cells:
                    text = cell.get_text().strip()
                    # Look for projection in text
                    if 'projection' in text.lower():
                        # Parse the text
                        import re
                        match = re.search(r'(\d+\.?\d*)projection', text.lower())
                        if match:
                            projection_val = float(match.group(1))
                            # Find player name from nearby
                            player = "Unknown"
                            market = 'unknown'
                            timestamp = datetime.now().isoformat()
                            proj = Projection(site='covers', player=player, market=market, projection=projection_val, timestamp=timestamp)
                            projections.append(proj)
    
    return projections