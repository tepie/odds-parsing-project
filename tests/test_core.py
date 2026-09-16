import unittest

from analysis.normalizer import normalize_odds
from models.odds import Odds
from props.covers_props import Prop, filter_props, parse_prop
from scrapers.covers_games import SPORT_URLS, american_to_decimal, parse_market_cell


class OddsParsingTests(unittest.TestCase):
    def test_american_to_decimal(self):
        self.assertAlmostEqual(american_to_decimal("-110"), 1.9090909)
        self.assertAlmostEqual(american_to_decimal("+150"), 2.5)

    def test_parse_market_cell(self):
        self.assertEqual(
            parse_market_cell("-3.5 -110 DraftKings", "spread"),
            ("-110", "DraftKings"),
        )
        self.assertEqual(
            parse_market_cell("o 45.5 +105 FanDuel", "total"),
            ("+105", "FanDuel"),
        )

    def test_normalize_odds_preserves_decimal_and_converts_american(self):
        odds = [
            Odds("Book A", -110, "spread", "Team", "now"),
            Odds("Book B", 2.5, "moneyline", "Team", "now"),
        ]
        normalized = normalize_odds(odds)
        self.assertAlmostEqual(normalized[0].odds, 1.9090909)
        self.assertEqual(normalized[1].odds, 2.5)
        self.assertEqual(normalized[0].player, "team")

    def test_all_game_sports_have_covers_urls(self):
        self.assertEqual(set(SPORT_URLS), {"nba", "mlb", "nfl", "ncaaf"})


class PropsParsingTests(unittest.TestCase):
    def test_parse_nfl_prop(self):
        prop = parse_prop(
            "J. Daniels (QB) o200.5 Passing Yards 267.15 PROJECTION "
            "+66.7 DIFFERENCE 26.30% EV"
        )
        self.assertIsNotNone(prop)
        self.assertEqual(prop.player, "J. Daniels")
        self.assertEqual(prop.line, 200.5)
        self.assertEqual(prop.difference, 66.7)

    def test_game_projection_is_excluded_from_player_props(self):
        game_prop = Prop(
            "BAL @ NYM", "GAME", "Total", "o8.5 Total", 8.5, 10.66, 2.2, 17.56, "o8.5 -110", "BAL @ NYM"
        )
        player_prop = Prop(
            "B. Rice", "DH", "Total Bases", "o1.5 Total Bases", 1.5, 2.0, 0.3, 5.0, "o1.5 +110", "NYY @ MIN"
        )
        filtered = filter_props([game_prop, player_prop], [])
        self.assertEqual(filtered, [player_prop])


if __name__ == "__main__":
    unittest.main()
