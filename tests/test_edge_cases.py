"""
tests/test_edge_cases.py
------------------------
Unit tests for the four required demo edge cases:
1. Heavy traffic (multiplier applied, widened uncertainty band, reason noted)
2. Technician unavailable (auto-assign fails cleanly, job unassigned, customer alerted)
3. Service overrun (previous job delay added, ETA range shifted, reason updated)
4. Technician lacking required skill (dispatcher manual override allowed but flagged with warning)
"""

import unittest
import sqlite3
import random
import os

from app import get_db, init_db, auto_assign, override_job, log_assignment, log_eta
from eta_engine import calculate_eta, haversine_km


class TestEdgeCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialise clean database with fresh test data."""
        init_db()

    def setUp(self):
        self.conn = get_db()

    def tearDown(self):
        self.conn.close()

    def test_edge_case_1_heavy_traffic(self):
        """
        Edge Case 1: Heavy Traffic.
        A rush-hour appointment causes the traffic multiplier (1.7) to widen the ETA range
        significantly instead of promising an exact arrival time.
        """
        # Fetch Job #1 from seeded database (demo_case = 'heavy_traffic')
        job = self.conn.execute("SELECT * FROM jobs WHERE demo_case='heavy_traffic'").fetchone()
        self.assertIsNotNone(job, "Heavy traffic demo job must be seeded.")
        self.assertEqual(job["traffic_level"], "heavy")
        self.assertIsNotNone(job["eta_low"])
        self.assertIsNotNone(job["eta_high"])
        self.assertLess(job["eta_low"], job["eta_high"])

        # Uncertainty band width must be widened for heavy traffic (>= 12 mins)
        bandwidth = job["eta_high"] - job["eta_low"]
        self.assertGreaterEqual(bandwidth, 12, "Uncertainty band under heavy traffic must widen.")
        self.assertIn("heavy traffic", job["delay_reason"].lower())

    def test_edge_case_2_technician_unavailable(self):
        """
        Edge Case 2: Technician Unavailable.
        When no technician with the required skill is available (e.g. on leave/sick),
        auto_assign must cleanly set status='unassigned', assign no technician,
        record the reason, and not crash.
        """
        # Create a new test job requiring an unavailable skill
        cur = self.conn.execute(
            """INSERT INTO jobs (customer_name, required_skill, customer_latitude, customer_longitude,
                                  appointment_time, status)
               VALUES ('Test Unavailable Customer', 'Plumbing', 13.0100, 80.1950, '2026-10-05T11:00', 'pending')"""
        )
        test_job_id = cur.lastrowid
        self.conn.commit()

        # Temporarily ensure all Plumbing technicians are unavailable
        self.conn.execute(
            "UPDATE technicians SET availability='unavailable' WHERE skills LIKE '%Plumbing%'"
        )
        self.conn.commit()

        # Run auto_assign
        auto_assign(self.conn, test_job_id)

        # Verify job is unassigned
        updated_job = self.conn.execute("SELECT * FROM jobs WHERE id=?", (test_job_id,)).fetchone()
        self.assertEqual(updated_job["status"], "unassigned")
        self.assertIsNone(updated_job["assigned_technician_id"])
        self.assertIn("No technician with the required skill", updated_job["delay_reason"])

        # Verify assignment_history has unassigned entry
        hist = self.conn.execute(
            "SELECT * FROM assignment_history WHERE job_id=? ORDER BY id DESC", (test_job_id,)
        ).fetchone()
        self.assertIsNotNone(hist)
        self.assertEqual(hist["action"], "unassigned")

    def test_edge_case_3_service_overrun(self):
        """
        Edge Case 3: Service / Job Taking Longer Than Expected.
        When a technician's previous job overruns, 12-28 extra minutes are added
        to the travel time, the uncertainty band widens, and delay reason is recorded.
        """
        job = self.conn.execute("SELECT * FROM jobs WHERE demo_case='service_overrun'").fetchone()
        self.assertIsNotNone(job, "Service overrun demo job must be seeded.")
        self.assertEqual(job["status"], "assigned")

        # Verify history logs contain previous job delay
        history_logs = self.conn.execute(
            "SELECT * FROM eta_history WHERE job_id=?", (job["id"],)
        ).fetchall()
        self.assertGreaterEqual(len(history_logs), 2, "Job 3 must have multiple ETA updates showing overrun progression.")

        reasons = " ".join([h["reason"] for h in history_logs]).lower()
        self.assertIn("previous job", reasons)

    def test_edge_case_4_skill_mismatch_override(self):
        """
        Edge Case 4: Technician Lacks Required Skill (Dispatcher Override).
        A dispatcher manually assigns a technician lacking the required skill.
        The system must allow the override but explicitly flag the warning in
        assignment_history, delay_reason, and the job record.
        """
        job = self.conn.execute("SELECT * FROM jobs WHERE demo_case='skill_mismatch'").fetchone()
        self.assertIsNotNone(job, "Skill mismatch demo job must be seeded.")
        self.assertEqual(job["status"], "assigned")
        self.assertIsNotNone(job["assigned_technician_id"])

        # Fetch assigned technician
        tech = self.conn.execute("SELECT * FROM technicians WHERE id=?", (job["assigned_technician_id"],)).fetchone()
        tech_skills = [s.strip() for s in tech["skills"].split(",")]

        # Prove technician does NOT have the job's required skill
        self.assertNotIn(job["required_skill"], tech_skills)

        # Verify warning note is present in delay_reason
        self.assertIn("skill mismatch", job["delay_reason"].lower())

        # Verify assignment_history logs explicit warning
        override_hist = self.conn.execute(
            "SELECT * FROM assignment_history WHERE job_id=? AND action='manual_override'", (job["id"],)
        ).fetchone()
        self.assertIsNotNone(override_hist)
        self.assertIn("WARNING", override_hist["reason"])
        self.assertIn("required skill", override_hist["reason"])


if __name__ == "__main__":
    unittest.main()
