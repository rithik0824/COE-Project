"""
tests/test_eta_engine.py
------------------------
Unit tests for eta_engine.py:
- Haversine distance accuracy, symmetry, and zero distance
- Traffic multiplier and time-of-day weighting
- calculate_eta invariants (range order, lower bounds, uncertainty bands, reason text)
- City coordinate boundary checks
"""

import unittest
import random
from eta_engine import (
    haversine_km,
    get_traffic_level,
    calculate_eta,
    random_coordinate,
    CITY_LAT_RANGE,
    CITY_LNG_RANGE,
    TRAFFIC_MULTIPLIER,
)


class TestETAEngine(unittest.TestCase):

    def test_haversine_km_zero_distance(self):
        """Distance between identical coordinates must be zero."""
        dist = haversine_km(13.0827, 80.2707, 13.0827, 80.2707)
        self.assertAlmostEqual(dist, 0.0, places=4)

    def test_haversine_km_symmetry(self):
        """Distance from A to B must equal distance from B to A."""
        lat1, lng1 = 12.9550, 80.2100
        lat2, lng2 = 13.0270, 80.2500
        d_ab = haversine_km(lat1, lng1, lat2, lng2)
        d_ba = haversine_km(lat2, lng2, lat1, lng1)
        self.assertAlmostEqual(d_ab, d_ba, places=4)

    def test_haversine_km_known_scale(self):
        """Distance between 1 deg latitude is approximately 111 km."""
        dist = haversine_km(12.0, 80.0, 13.0, 80.0)
        self.assertGreater(dist, 110.0)
        self.assertLess(dist, 112.0)

    def test_traffic_multiplier_values(self):
        """Traffic multipliers must be strictly non-decreasing from light to heavy."""
        self.assertEqual(TRAFFIC_MULTIPLIER["light"], 1.0)
        self.assertGreater(TRAFFIC_MULTIPLIER["moderate"], TRAFFIC_MULTIPLIER["light"])
        self.assertGreater(TRAFFIC_MULTIPLIER["heavy"], TRAFFIC_MULTIPLIER["moderate"])

    def test_get_traffic_level_rush_hour(self):
        """Morning rush hours (08:00 - 10:00) and evening rush hours (17:00 - 20:00) should skew heavy/moderate."""
        rng = random.Random(42)
        rush_samples = [get_traffic_level("2026-10-05T09:00", rng) for _ in range(30)]
        self.assertTrue(all(lvl in ("heavy", "moderate") for lvl in rush_samples))
        self.assertIn("heavy", rush_samples)

    def test_get_traffic_level_invalid_fallback(self):
        """Invalid timestamp strings must fall back gracefully to the current hour without throwing."""
        lvl = get_traffic_level("invalid-timestamp")
        self.assertIn(lvl, ("light", "moderate", "heavy"))

    def test_calculate_eta_invariants(self):
        """Core ETA calculation invariants: low <= high, positive duration, minimum bound 5 mins."""
        rng = random.Random(123)
        tech = {"latitude": 12.9550, "longitude": 80.2100}
        job = {"customer_latitude": 13.0200, "customer_longitude": 80.2500, "appointment_time": "2026-10-05T10:00"}

        eta = calculate_eta(tech, job, rng=rng)
        self.assertIn("eta_low", eta)
        self.assertIn("eta_high", eta)
        self.assertIn("traffic_level", eta)
        self.assertIn("reason", eta)
        self.assertIn("distance_km", eta)

        # Range Invariant
        self.assertLessEqual(eta["eta_low"], eta["eta_high"])
        # Minimum bound invariant
        self.assertGreaterEqual(eta["eta_low"], 5)
        # Distance must be positive
        self.assertGreater(eta["distance_km"], 0)

    def test_calculate_eta_heavy_vs_light_traffic(self):
        """Heavy traffic must increase total ETA and widen the uncertainty band compared to light traffic."""
        rng1 = random.Random(7)
        rng2 = random.Random(7)
        tech = {"latitude": 12.9500, "longitude": 80.2000}
        job = {"customer_latitude": 13.0500, "customer_longitude": 80.2800, "appointment_time": "2026-10-05T12:00"}

        eta_light = calculate_eta(tech, job, forced_traffic="light", rng=rng1)
        eta_heavy = calculate_eta(tech, job, forced_traffic="heavy", rng=rng2)

        # Travel time under heavy traffic must be longer
        self.assertGreater(eta_heavy["eta_high"], eta_light["eta_high"])
        # Uncertainty band (high - low) under heavy traffic must be wider
        light_band = eta_light["eta_high"] - eta_light["eta_low"]
        heavy_band = eta_heavy["eta_high"] - eta_heavy["eta_low"]
        self.assertGreater(heavy_band, light_band)
        self.assertIn("heavy traffic", eta_heavy["reason"])

    def test_calculate_eta_service_overrun_delay(self):
        """When previous_job_delay is True, 12-28 mins delay is added and reason noted."""
        rng1 = random.Random(99)
        rng2 = random.Random(99)
        tech = {"latitude": 12.9800, "longitude": 80.1800}
        job = {"customer_latitude": 13.0100, "customer_longitude": 80.2200, "appointment_time": "2026-10-05T14:00"}

        eta_normal = calculate_eta(tech, job, previous_job_delay=False, rng=rng1, forced_traffic="moderate")
        eta_delayed = calculate_eta(tech, job, previous_job_delay=True, rng=rng2, forced_traffic="moderate")

        self.assertGreater(eta_delayed["eta_low"], eta_normal["eta_low"])
        self.assertIn("previous job running longer than expected", eta_delayed["reason"])

    def test_random_coordinate_bounds(self):
        """random_coordinate must generate coordinates strictly within defined city boundaries."""
        rng = random.Random(42)
        for _ in range(50):
            lat, lng = random_coordinate(rng)
            self.assertGreaterEqual(lat, CITY_LAT_RANGE[0])
            self.assertLessEqual(lat, CITY_LAT_RANGE[1])
            self.assertGreaterEqual(lng, CITY_LNG_RANGE[0])
            self.assertLessEqual(lng, CITY_LNG_RANGE[1])


if __name__ == "__main__":
    unittest.main()
