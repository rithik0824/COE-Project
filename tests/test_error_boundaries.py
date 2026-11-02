"""
tests/test_error_boundaries.py
------------------------------
Granular unit tests specifically validating the multi-layered Error Boundary Architecture
of the Live ETA Communication and Technician Assignment System.

Error Boundary Layers Tested:
1. Client & HTTP Request Validation Boundary (404 Not Found, 400 Bad Request, route fallbacks)
2. Algorithmic Invariant & Math Boundary (zero distance, division-by-zero, extreme coords, clamp guards)
3. Database Transaction & Relational Boundary (foreign keys, missing records, transaction rollback)
4. External Notification Simulation Boundary (missing phone/email, special characters, fallback channels)
5. State Machine & Event Isolation Boundary (unexpected status transitions, isolated error handling)
"""

import unittest
import sqlite3
from app import app, get_db, init_db, auto_assign, get_customer_phone, handle_technician_availability_change
from eta_engine import haversine_km, calculate_eta, get_traffic_level, BASE_SPEED_KMH, PREP_BUFFER_MIN
from notification_engine import log_notification


class TestErrorBoundaries(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        init_db()

    def setUp(self):
        self.client = app.test_client()
        self.conn = get_db()

    def tearDown(self):
        self.conn.close()

    # -------------------------------------------------------------------------
    # Layer 1: Client & HTTP Request Validation Boundary
    # -------------------------------------------------------------------------
    def test_boundary_route_not_found_returns_404(self):
        """Requesting an unregistered URL route must trigger the 404 error boundary gracefully."""
        res = self.client.get("/non-existent-endpoint-xyz")
        self.assertEqual(res.status_code, 404)
        self.assertTrue(b"404" in res.data or b"Not Found" in res.data)

    def test_boundary_nonexistent_job_detail_redirects_safely(self):
        """Accessing a non-existent job ID must redirect gracefully to /jobs with a flash warning."""
        res = self.client.get("/jobs/99999999")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/jobs", res.headers["Location"])

    def test_boundary_nonexistent_customer_track_returns_404(self):
        """Tracking portal request for a non-existent job must return HTTP 404 error boundary."""
        res = self.client.get("/track/99999999")
        self.assertEqual(res.status_code, 404)

    def test_boundary_override_nonexistent_job_handles_safely(self):
        """Manual override on an invalid job ID must fail safely and redirect with warning."""
        res = self.client.post("/jobs/99999999/override", data={
            "technician_id": "1",
            "reason": "Test override non-existent job"
        })
        self.assertEqual(res.status_code, 302)

    def test_boundary_invalid_filter_params_on_jobs_board(self):
        """Malformed query parameters (e.g. invalid page number, SQL injection chars) must not crash."""
        res = self.client.get("/jobs?page=invalid_number&status=' OR 1=1--&skill=<script>")
        self.assertEqual(res.status_code, 200)

    # -------------------------------------------------------------------------
    # Layer 2: Algorithmic Invariant & Math Boundary
    # -------------------------------------------------------------------------
    def test_boundary_haversine_identical_coords_zero_distance(self):
        """Haversine formula must return exactly 0.0 without precision instability or domain errors."""
        dist = haversine_km(13.0827, 80.2707, 13.0827, 80.2707)
        self.assertEqual(dist, 0.0)

    def test_boundary_haversine_extreme_antipodal_coordinates(self):
        """Haversine formula must handle extreme coordinate ranges across the globe without overflow."""
        # Chennai to approximate antipode in South Pacific
        dist = haversine_km(13.0827, 80.2707, -13.0827, -99.7293)
        self.assertIsInstance(dist, float)
        self.assertGreater(dist, 19000.0)
        self.assertLess(dist, 21000.0)

    def test_boundary_eta_clamp_guarantees_minimum_time(self):
        """calculate_eta must enforce the lower clamp bound (eta_low >= 5 min) even for 0 km distance."""
        tech_mock = {"latitude": 13.0000, "longitude": 80.2000}
        job_mock = {
            "customer_latitude": 13.0000,
            "customer_longitude": 80.2000,
            "appointment_time": "2026-10-05T12:00"
        }
        eta = calculate_eta(tech_mock, job_mock, forced_traffic="light")
        # Invariant 1: Low must be clamped to at least 5 minutes
        self.assertGreaterEqual(eta["eta_low"], 5)
        # Invariant 2: High must be greater than or equal to low
        self.assertGreaterEqual(eta["eta_high"], eta["eta_low"])
        # Invariant 3: Distance must be 0
        self.assertEqual(eta["distance_km"], 0.0)

    def test_boundary_traffic_level_invalid_timestamp_graceful_fallback(self):
        """get_traffic_level must gracefully fall back on None, empty string, or corrupt timestamp."""
        for invalid_input in [None, "", "2026-99-99T99:99", "corrupted-date"]:
            level = get_traffic_level(invalid_input)
            self.assertIn(level, ("light", "moderate", "heavy"))

    def test_boundary_unknown_forced_traffic_tier_handled(self):
        """Passing an unrecognized forced_traffic value must not crash the calculation."""
        tech_mock = {"latitude": 12.9500, "longitude": 80.2100}
        job_mock = {
            "customer_latitude": 13.0200,
            "customer_longitude": 80.2500,
            "appointment_time": "2026-10-05T10:00"
        }
        # If forced_traffic is unknown, function should fall back to standard calculation
        try:
            eta = calculate_eta(tech_mock, job_mock, forced_traffic=None)
            self.assertIn(eta["traffic_level"], ("light", "moderate", "heavy"))
        except Exception as e:
            self.fail(f"calculate_eta raised unexpected exception: {e}")

    # -------------------------------------------------------------------------
    # Layer 3: Database Transaction & Relational Boundary
    # -------------------------------------------------------------------------
    def test_boundary_database_foreign_key_enforcement(self):
        """Foreign key constraint must prevent referencing non-existent technicians."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """INSERT INTO jobs (customer_name, required_skill, customer_latitude,
                                      customer_longitude, appointment_time, assigned_technician_id)
                   VALUES ('FK Violator', 'Electrical', 13.0, 80.2, '2026-10-05T10:00', 999999)"""
            )
            self.conn.commit()
        # Roll back failed transaction to maintain clean session
        self.conn.rollback()

    def test_boundary_null_constraint_rejection(self):
        """Required columns must reject NULL values to maintain schema integrity."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """INSERT INTO technicians (name, skills, availability, latitude, longitude)
                   VALUES (NULL, 'Electrical', 'available', 13.0, 80.2)"""
            )
            self.conn.commit()
        self.conn.rollback()

    # -------------------------------------------------------------------------
    # Layer 4: External Notification Simulation Boundary
    # -------------------------------------------------------------------------
    def test_boundary_missing_customer_phone_fallback(self):
        """get_customer_phone must return valid default phone if job dictionary lacks the key or is None."""
        self.assertEqual(get_customer_phone(None), "+91 98400 12345")
        self.assertEqual(get_customer_phone({}), "+91 98400 12345")
        self.assertEqual(get_customer_phone({"customer_phone": None}), "+91 98400 12345")
        self.assertEqual(get_customer_phone({"customer_phone": ""}), "+91 98400 12345")
        self.assertEqual(get_customer_phone({"customer_phone": "+91 99999 88888"}), "+91 99999 88888")

    def test_boundary_notification_special_characters_and_emojis(self):
        """Notification system must persist and retrieve Unicode, emojis, and quotes without corruption."""
        unicode_title = "🚨 Heavy Rain Alert: கோடம்பாக்கம் Route Delayed"
        unicode_msg = "Technician Arun 🔧 is navigating heavy monsoon traffic. 30–45 mins ETA."
        notif_id = log_notification(
            self.conn, job_id=1, channel="SMS", recipient="+91 98400 00000",
            title=unicode_title, message=unicode_msg, trigger_event="traffic_shift"
        )
        self.conn.commit()

        retrieved = self.conn.execute(
            "SELECT * FROM customer_notifications WHERE id=?", (notif_id,)
        ).fetchone()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["title"], unicode_title)
        self.assertEqual(retrieved["message"], unicode_msg)

    # -------------------------------------------------------------------------
    # Layer 5: State Machine & Event Isolation Boundary
    # -------------------------------------------------------------------------
    def test_boundary_tech_availability_unknown_technician_id(self):
        """handle_technician_availability_change must safely return empty events for invalid tech_id."""
        events = handle_technician_availability_change(self.conn, 999999, "unavailable")
        self.assertEqual(events, [])

    def test_boundary_auto_assign_when_all_technicians_busy(self):
        """auto_assign must gracefully set job to 'unassigned' when zero specialists are free."""
        cur = self.conn.execute(
            """INSERT INTO jobs (customer_name, required_skill, customer_latitude, customer_longitude,
                                  appointment_time, status)
               VALUES ('Peak Demand Customer', 'General Maintenance', 13.04, 80.20, '2026-10-05T14:00', 'pending')"""
        )
        test_job_id = cur.lastrowid
        self.conn.commit()

        # Set all General Maintenance technicians to busy
        self.conn.execute(
            "UPDATE technicians SET availability='busy' WHERE skills LIKE '%General Maintenance%'"
        )
        self.conn.commit()

        # Execute auto_assign under full capacity
        auto_assign(self.conn, test_job_id)

        job = self.conn.execute("SELECT * FROM jobs WHERE id=?", (test_job_id,)).fetchone()
        self.assertEqual(job["status"], "unassigned")
        self.assertIsNone(job["assigned_technician_id"])
        self.assertIn("No technician", job["delay_reason"])


if __name__ == "__main__":
    unittest.main()
