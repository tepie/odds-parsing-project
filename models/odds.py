from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class Odds:
    bookmaker: str
    odds: float  # decimal odds
    market: str  # e.g., 'home_run', 'strikeout'
    player: str
    timestamp: str
    source: Optional[str] = None
    ev: Optional[float] = None  # expected value if calculated
    event: Optional[str] = None
    selection: Optional[str] = None
    line: Optional[str] = None
    fair_odds: Optional[float] = None
    source_ev: Optional[float] = None
    projected_spread: Optional[float] = None
    projected_total: Optional[float] = None
    score_edge: Optional[float] = None
    score_support: Optional[float] = None
    combined_value_score: Optional[float] = None

@dataclass
class Projection:
    site: str
    player: str
    market: str
    projection: float  # projected value
    timestamp: str
    event: Optional[str] = None
    away_score: Optional[float] = None
    home_score: Optional[float] = None
    projected_spread: Optional[float] = None
    projected_total: Optional[float] = None

@dataclass
class OddsComparison:
    player: str
    market: str
    odds_list: List[Odds]
    projections: List[Projection]
    best_odds: Optional[Odds] = None
    blended_score: Optional[float] = None
    market_difference: Optional[float] = None
    value_score: Optional[float] = None
    reference_odds: Optional[float] = None