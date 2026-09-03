from jinja2 import Template
from typing import Dict
from models.odds import Odds, OddsComparison

def decimal_to_american(decimal_odds):
    if decimal_odds >= 2.0:
        return f"+{int((decimal_odds - 1) * 100)}"
    else:
        return f"{int(-100 / (decimal_odds - 1))}"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ sport }} Odds Review</title>
    <style>
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .best { background-color: #d4edda; }
            body { font-family: Arial, sans-serif; margin: 32px; color: #222; }
            table { margin-bottom: 28px; }
            .muted { color: #666; }
    </style>
</head>
<body>
    <h1>{{ sport }} Odds Consolidated Review</h1>
    <p>Generated at: {{ timestamp }}</p>

    {% if top_value_bets %}
    <h2>Top 5 CrazyNinja Value Opportunities</h2>
    <table>
        <tr>
            <th>Rank</th>
            <th>Event</th>
            <th>Market</th>
            <th>Selection</th>
            <th>Sportsbook</th>
            <th>Odds</th>
            <th>Fair Odds</th>
            <th>CNO EV</th>
            <th>Score Edge</th>
            <th>Combined Score</th>
        </tr>
        {% for odds in top_value_bets %}
        <tr class="best">
            <td>{{ loop.index }}</td>
            <td>{{ odds.event }}</td>
            <td>{{ odds.market }}</td>
            <td>{{ odds.selection }}</td>
            <td>{{ odds.bookmaker }}</td>
            <td>{{ decimal_to_american(odds.odds) }}</td>
            <td>{{ decimal_to_american(odds.fair_odds) if odds.fair_odds else 'N/A' }}</td>
            <td>{{ odds.source_ev | round(2) }}%</td>
            <td>{{ odds.score_edge | round(2) if odds.score_edge is not none else 'N/A' }} pts</td>
            <td>{{ odds.combined_value_score | round(2) if odds.combined_value_score is not none else odds.source_ev | round(2) }}%</td>
        </tr>
        {% endfor %}
    </table>
    {% endif %}
    
    <h2>All Markets Ranked By Value</h2>
    <p class="muted">Spreads are preferred, followed by first-half and first-quarter spreads, totals, and then moneylines. Combined score weights CNO EV 50%, Covers score support 30%, and market difference 20%.</p>
    {% for comp in ranked_comparisons %}
    <h3>{{ loop.index }}. {{ comp.event or comp.player }} | {{ comp.market }} | {{ comp.selection or 'Unspecified selection' }}</h3>
    <p>Best available: {{ comp.best_odds.bookmaker if comp.best_odds else 'N/A' }} at {{ decimal_to_american(comp.best_odds.odds) if comp.best_odds else 'N/A' }}{% if comp.best_odds and comp.best_odds.line %} ({{ comp.best_odds.line }}){% endif %}. Market difference: {{ comp.market_difference | round(2) }}% versus median price {{ decimal_to_american(comp.reference_odds) if comp.reference_odds else 'N/A' }}. Score edge: {{ comp.best_odds.score_edge | round(2) if comp.best_odds and comp.best_odds.score_edge is not none else 'N/A' }} points.</p>
    
    <h3>Odds</h3>
    <table>
        <tr>
            <th>Bookmaker</th>
            <th>Odds</th>
            <th>Source</th>
            <th>% vs Sharp</th>
            <th>Best?</th>
        </tr>
        {% for odds in comp.odds_list %}
        <tr class="{% if odds == comp.best_odds %}best{% endif %}">
            <td>{{ odds.bookmaker }}</td>
            <td>{{ decimal_to_american(odds.odds) }}{% if odds.line %} ({{ odds.line }}){% endif %}</td>
            <td>{{ odds.source or 'Unknown' }}</td>
            <td>{{ odds.ev | round(2) if odds.ev != None else 'N/A' }}</td>
            <td>{% if odds == comp.best_odds %}Yes{% else %}No{% endif %}</td>
        </tr>
        {% endfor %}
    </table>
    
    {% if comp.projections %}
    <h3>Projections</h3>
    <table>
        <tr>
            <th>Site</th>
            <th>Projection</th>
        </tr>
        {% for proj in comp.projections %}
        <tr>
            <td>{{ proj.site }}</td>
            <td>{{ proj.projection }}</td>
        </tr>
        {% endfor %}
    </table>
    {% endif %}
    {% endfor %}
</body>
</html>
"""

def generate_html_report(comparisons: Dict[str, OddsComparison], timestamp: str, filename: str = 'odds_report.html', sport: str = 'MLB', top_value_bets: list[Odds] = None):
    """
    Generate HTML report from comparisons
    """
    # Sort odds within each comparison by odds descending (best first)
    for comp in comparisons.values():
        comp.odds_list.sort(key=lambda o: o.odds, reverse=True)
    
    ranked_comparisons = sorted(comparisons.values(), key=lambda comp: comp.value_score or 0, reverse=True)
    for comp in ranked_comparisons:
        first_odds = comp.odds_list[0] if comp.odds_list else None
        comp.event = first_odds.event if first_odds else None
        comp.selection = first_odds.selection if first_odds else None

    template = Template(HTML_TEMPLATE)
    html_content = template.render(comparisons=comparisons, ranked_comparisons=ranked_comparisons, timestamp=timestamp, decimal_to_american=decimal_to_american, sport=sport, top_value_bets=top_value_bets or [])
    
    with open(filename, 'w') as f:
        f.write(html_content)
    
    print(f"Report generated: {filename}")