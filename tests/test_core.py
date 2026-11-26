import unittest

from analysis.comparator import (
    calculate_score_edge,
    detect_moneyline_upset,
    projection_recommendation,
    select_moneyline_underdogs,
    group_odds_by_player_market,
)
from analysis.normalizer import normalize_odds
from models.odds import Odds, Projection
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
        self.assertEqual(set(SPORT_URLS), {"nba", "mlb", "nfl", "ncaaf", "ncaab", "nhl"})

    def test_projection_score_edge_supports_spread_and_total(self):
        projection = Projection(
            "covers", "game", "score", 7, "now",
            event="Away @ Home", projected_spread=7, projected_total=52,
        )
        home_spread = Odds(
            "Book", 1.91, "spread", "home", "now",
            event="Away @ Pittsburgh Panthers", selection="PITT PITT -3.5",
        )
        over = Odds(
            "Book", 1.91, "total", "home", "now",
            event="Away @ Pittsburgh Panthers", selection="Home o45.5", line="o45.5",
        )
        projection.event = "Away @ Pittsburgh Panthers"
        self.assertEqual(calculate_score_edge(home_spread, projection), 3.5)
        self.assertEqual(calculate_score_edge(over, projection), 6.5)
        over.selection = "Home u58.5"
        over.line = "u58.5"
        over.projected_spread = 7
        over.projected_total = 52
        over.score_edge = 6.5
        self.assertTrue(projection_recommendation(over).startswith("UNDER"))

    def test_detect_moneyline_upset_flags_model_side_when_market_favorite_differs(self):
        projection = Projection(
            "covers", "game", "score", 7, "now",
            event="Away @ Home", projected_spread=7, projected_total=52,
        )
        sides = [
            Odds("Book A", 1.55, "moneyline", "away", "now", event="Away @ Home", selection="Away"),
            Odds("Book A", 2.40, "moneyline", "home", "now", event="Away @ Home", selection="Home"),
        ]
        self.assertEqual(detect_moneyline_upset("Away @ Home", sides, projection), "Home")

        sides = [
            Odds("Book A", 1.30, "moneyline", "away", "now", event="Away @ Home", selection="Away"),
            Odds("Book B", 1.55, "moneyline", "home", "now", event="Away @ Home", selection="Home"),
        ]
        self.assertIsNone(detect_moneyline_upset("Away @ Home", sides, Projection(
            "covers", "game", "score", 7, "now",
            event="Away @ Home", projected_spread=-7, projected_total=52,
        )))

        projection = Projection(
            "covers", "game", "score", 7, "now",
            event="Away @ Home", projected_spread=7, projected_total=52,
        )
        self.assertEqual(detect_moneyline_upset("Away @ Home", sides, projection), "Home")

    def test_select_moneyline_underdog_returns_one_side_per_event(self):
        sides = [
            Odds("Book A", 1.50, "moneyline", "away", "now", event="Away @ Home", selection="Away"),
            Odds("Book B", 1.52, "moneyline", "away", "now", event="Away @ Home", selection="Away"),
            Odds("Book A", 2.40, "moneyline", "home", "now", event="Away @ Home", selection="Home"),
            Odds("Book B", 2.30, "moneyline", "home", "now", event="Away @ Home", selection="Home"),
        ]
        comparisons = group_odds_by_player_market(sides, [])
        projection = Projection(
            "covers", "game", "score", 3, "now",
            event="Away @ Home", away_score=20, home_score=17,
        )

        underdogs = select_moneyline_underdogs(comparisons, [projection])

        self.assertEqual(len(underdogs), 1)
        self.assertEqual(underdogs[0].odds_list[0].selection, "Home")

    def test_select_moneyline_underdog_skips_projection_more_than_three_points_behind(self):
        sides = [
            Odds("Book", 1.20, "moneyline", "away", "now", event="Away @ Home", selection="Away"),
            Odds("Book", 4.50, "moneyline", "home", "now", event="Away @ Home", selection="Home"),
        ]
        projection = Projection(
            "covers", "game", "score", 12, "now",
            event="Away @ Home", away_score=28, home_score=16,
        )

        self.assertEqual(
            select_moneyline_underdogs(group_odds_by_player_market(sides, []), [projection]),
            [],
        )

    def test_select_moneyline_underdog_keeps_projected_winner(self):
        sides = [
            Odds("Book", 1.40, "moneyline", "away", "now", event="Away @ Home", selection="Away"),
            Odds("Book", 3.20, "moneyline", "home", "now", event="Away @ Home", selection="Home"),
        ]
        projection = Projection(
            "covers", "game", "score", 4, "now",
            event="Away @ Home", away_score=17, home_score=21,
        )

        underdogs = select_moneyline_underdogs(
            group_odds_by_player_market(sides, []), [projection]
        )

        self.assertEqual(len(underdogs), 1)
        self.assertEqual(underdogs[0].odds_list[0].selection, "Home")

    def test_select_moneyline_underdog_skips_tcu_when_projection_trails_by_sixteen(self):
        event = "TCU Horned Frogs @ Texas Tech Red Raiders"
        sides = [
            Odds("Book", 1.15, "moneyline", "texas tech", "now", event=event,
                 selection="Texas Tech Red Raiders"),
            Odds("Book", 6.50, "moneyline", "tcu", "now", event=event,
                 selection="TCU Horned Frogs"),
        ]
        projection = Projection(
            "covers", "game", "score", 15.87, "now",
            event=event, away_score=16.24, home_score=32.11,
        )

        self.assertEqual(
            select_moneyline_underdogs(
                group_odds_by_player_market(sides, []), [projection]
            ),
            [],
        )

    def test_select_moneyline_underdog_skips_equal_prices(self):
        sides = [
            Odds("Book A", 1.90, "moneyline", "away", "now", event="Away @ Home", selection="Away"),
            Odds("Book A", 1.90, "moneyline", "home", "now", event="Away @ Home", selection="Home"),
        ]

        projection = Projection(
            "covers", "game", "score", 0, "now",
            event="Away @ Home", away_score=20, home_score=20,
        )
        self.assertEqual(
            select_moneyline_underdogs(
                group_odds_by_player_market(sides, []), [projection]
            ),
            [],
        )


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

    def test_probability_prop_minimum_projection_is_configurable(self):
        touchdown_prop = Prop(
            "Player One", "RB", "Anytime Touchdown", "Anytime Touchdown",
            None, 0.20, 23.7, 23.67, "+265", "TEN @ BAL",
        )
        self.assertEqual(filter_props([touchdown_prop], ["touchdowns"]), [])
        self.assertEqual(
            filter_props([touchdown_prop], ["touchdowns"], min_projection=0.20),
            [touchdown_prop],
        )


if __name__ == "__main__":
    unittest.main()
