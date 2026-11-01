import unittest

from routing.services.geo import (
    bearing_degrees,
    haversine_miles,
    interpolate_profile,
    offset_point,
    sample_miles,
)
from routing.services.risk import (
    apply_load_to_wind,
    classify_checkpoint,
    classify_rain,
    classify_snow,
    classify_wind,
    rank_routes,
    recommendation_reason,
    summarize_checkpoints,
)


class WindTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(classify_wind(24.9), "low")
        self.assertEqual(classify_wind(25), "moderate")
        self.assertEqual(classify_wind(34.9), "moderate")
        self.assertEqual(classify_wind(35), "high")
        self.assertEqual(classify_wind(44.9), "high")
        self.assertEqual(classify_wind(45), "severe")
        self.assertEqual(classify_wind(54.9), "severe")
        self.assertEqual(classify_wind(55), "no_travel")


class RainTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(classify_rain(0.099), "low")
        self.assertEqual(classify_rain(0.10), "moderate")
        self.assertEqual(classify_rain(0.249), "moderate")
        self.assertEqual(classify_rain(0.25), "high")
        self.assertEqual(classify_rain(0.499), "high")
        self.assertEqual(classify_rain(0.50), "severe")
        self.assertEqual(classify_rain(1.00), "severe")
        self.assertEqual(classify_rain(1.001), "no_travel")


class SnowTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(classify_snow(0.49), "low")
        self.assertEqual(classify_snow(0.5), "moderate")
        self.assertEqual(classify_snow(0.99), "moderate")
        self.assertEqual(classify_snow(1.0), "high")
        self.assertEqual(classify_snow(1.99), "high")
        self.assertEqual(classify_snow(2.0), "severe")
        self.assertEqual(classify_snow(3.0), "severe")
        self.assertEqual(classify_snow(3.01), "no_travel")


class LoadTests(unittest.TestCase):
    def test_exact_thresholds_do_not_upgrade(self):
        self.assertEqual(apply_load_to_wind(54, "severe", 30000), "severe")
        self.assertEqual(apply_load_to_wind(44, "high", 40000), "high")

    def test_upgrades(self):
        self.assertEqual(apply_load_to_wind(54, "severe", 30001), "no_travel")
        self.assertEqual(apply_load_to_wind(44, "high", 40001), "severe")
        self.assertEqual(apply_load_to_wind(55, "no_travel", 1000), "no_travel")
        self.assertEqual(apply_load_to_wind(30, "moderate", 80000), "moderate")

    def test_overall_uses_the_worst_condition(self):
        result = classify_checkpoint(wind_mph=10, rain_in_hr=0, snow_in_hr=2.4, load_lb=10000)
        self.assertEqual(result["level"], "severe")
        self.assertEqual(result["wind_level"], "low")

    def test_heavy_load_can_raise_wind_above_rain(self):
        result = classify_checkpoint(wind_mph=46, rain_in_hr=0.05, snow_in_hr=0, load_lb=35000)
        self.assertEqual(result["wind_level"], "no_travel")
        self.assertEqual(result["level"], "no_travel")


class SummaryTests(unittest.TestCase):
    def test_weighted_average_and_mile_buckets(self):
        summary = summarize_checkpoints(
            [
                {"segment_miles": 0, "level": "low"},
                {"segment_miles": 10, "level": "high"},
                {"segment_miles": 10, "level": "severe"},
            ]
        )
        self.assertEqual(summary["high_miles"], 10)
        self.assertEqual(summary["severe_miles"], 10)
        self.assertEqual(summary["low_miles"], 0)
        self.assertAlmostEqual(summary["average_risk"], 3.5)


class RankingTests(unittest.TestCase):
    def test_severe_miles_beat_a_shorter_high_risk_route(self):
        routes = rank_routes(
            [
                _metrics("long", no_travel=0, severe=10, high=1, average=2, seconds=100),
                _metrics("safer", no_travel=0, severe=2, high=40, average=3, seconds=400),
            ]
        )
        self.assertEqual(routes[0]["name"], "safer")
        self.assertEqual(recommendation_reason(routes), "Fewest severe miles")

    def test_no_travel_miles_outrank_severe(self):
        routes = rank_routes(
            [
                _metrics("blocked", no_travel=5, severe=0, high=0, average=5, seconds=100),
                _metrics("open", no_travel=0, severe=30, high=10, average=4, seconds=500),
            ]
        )
        self.assertEqual(routes[0]["name"], "open")
        self.assertEqual(recommendation_reason(routes), "Fewest no-travel miles")

    def test_travel_time_breaks_a_risk_tie(self):
        routes = rank_routes(
            [
                _metrics("slow", no_travel=0, severe=4, high=4, average=2, seconds=300),
                _metrics("fast", no_travel=0, severe=4, high=4, average=2, seconds=200),
            ]
        )
        self.assertEqual(routes[0]["name"], "fast")
        self.assertEqual(recommendation_reason(routes), "Shortest travel time")

    def test_high_miles_used_when_severe_is_tied(self):
        routes = rank_routes(
            [
                _metrics("windier", no_travel=0, severe=5, high=20, average=3, seconds=100),
                _metrics("calmer", no_travel=0, severe=5, high=8, average=2.4, seconds=180),
                _metrics("worse", no_travel=0, severe=9, high=0, average=3, seconds=90),
            ]
        )
        self.assertEqual(routes[0]["name"], "calmer")
        self.assertEqual(recommendation_reason(routes), "Fewest high-risk miles")


class GeoTests(unittest.TestCase):
    def test_sample_miles_includes_start_and_end(self):
        self.assertEqual(sample_miles(100, 25), [0.0, 25.0, 50.0, 75.0, 100.0])
        self.assertEqual(sample_miles(25, 25), [0.0, 25.0])
        self.assertEqual(sample_miles(10, 25), [0.0, 10.0])

    def test_latitude_degree_is_about_69_miles(self):
        self.assertAlmostEqual(haversine_miles((0, 0), (1, 0)), 69.09, places=1)

    def test_bearing_and_offset(self):
        self.assertAlmostEqual(bearing_degrees((0, 0), (1, 0)), 0, places=5)
        self.assertAlmostEqual(bearing_degrees((0, 0), (0, 1)), 90, places=5)
        lat, lon = offset_point(0, 0, 0, 69.093)
        self.assertAlmostEqual(lat, 1, places=2)
        self.assertAlmostEqual(lon, 0, places=2)

    def test_interpolate_midpoint(self):
        profile = [
            (0.0, 0.0, 0.0, 0.0),
            (100.0, 3600.0, 1.0, 2.0),
        ]
        lat, lon, seconds = interpolate_profile(profile, 25)
        self.assertAlmostEqual(lat, 0.25)
        self.assertAlmostEqual(lon, 0.5)
        self.assertAlmostEqual(seconds, 900)


def _metrics(name, no_travel, severe, high, average, seconds):
    return {
        "name": name,
        "no_travel_miles": no_travel,
        "severe_miles": severe,
        "high_miles": high,
        "average_risk": average,
        "duration_seconds": seconds,
    }


if __name__ == "__main__":
    unittest.main()
