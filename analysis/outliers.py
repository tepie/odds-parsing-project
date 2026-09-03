from typing import List
from models.odds import Odds
import statistics
import numpy as np

def detect_outliers_zscore(odds_list: List[Odds], threshold: float = 2.0) -> List[Odds]:
    """
    Remove outliers using z-score method
    """
    if len(odds_list) < 3:
        return odds_list
    
    odds_values = [o.odds for o in odds_list]
    mean = statistics.mean(odds_values)
    stdev = statistics.stdev(odds_values)
    
    filtered = []
    for odds in odds_list:
        z = (odds.odds - mean) / stdev
        if abs(z) <= threshold:
            filtered.append(odds)
    
    return filtered

def detect_outliers_iqr(odds_list: List[Odds]) -> List[Odds]:
    """
    Remove outliers using IQR method
    """
    if len(odds_list) < 4:
        return odds_list
    
    odds_values = sorted([o.odds for o in odds_list])
    q1 = np.percentile(odds_values, 25)
    q3 = np.percentile(odds_values, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    filtered = [o for o in odds_list if lower_bound <= o.odds <= upper_bound]
    return filtered

def remove_outliers(odds_list: List[Odds], method: str = 'zscore') -> List[Odds]:
    """
    Remove outliers from odds list
    """
    if method == 'zscore':
        return detect_outliers_zscore(odds_list)
    elif method == 'iqr':
        return detect_outliers_iqr(odds_list)
    else:
        return odds_list