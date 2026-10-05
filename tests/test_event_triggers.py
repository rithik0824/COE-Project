"""
tests/test_event_triggers.py
----------------------------
Unit tests for Requirement 4:
Triggering ETA updates automatically from real status and availability events
rather than only relying on a manual 'resimulate' button.
"""

import unittest
from app import (
    app,
    get_db,
    init_db,
    handle_technician_availability_change,
    handle_traffic_shift,
)


class TestEventTriggers(unittest.TestCase):

    def setUp(self):
        init_db()
        self.conn = get_db()

    def tearDown(self):
        self.conn.close()

    def test_event_tech_becomes_unavailable_auto_reassigns(self):
        """
        When a technician with active jobs becomes 'unavailable', the system
        must automatically trigger re-assignment or mark the job unassigned with customer alerts.
        """
        # Find an assigned job and its technician
        job = self.conn.execute(
            """SELECT jobs.*, technicians.name as tech_name
               FROM jobs JOIN technicians ON jobs.assigned_technician_id = technicians.id
               WHERE jobs.status='assigned' LIMIT 1"""
        ).fetchone()
        self.assertIsNotNone(job)

        tech_id = job["assigned_technician_id"]

        # Trigger event: technician becomes unavailable (e.g. sick / emergency)
        events = handle_technician_availability_change(self.conn, tech_id, "unavailable")
        self.assertGreater(len(events), 0, "Event handler must report triggered events.")

        # Verify job is no longer assigned to the unavailable technician
        refreshed_job = self.conn.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
        self.assertNotEqual(refreshed_job["assigned_technician_id"], tech_id)

        # Verify notifications were created
        notifs = self.conn.execute(
            "SELECT * FROM customer_notifications WHERE job_id=? ORDER BY id DESC", (job["id"],)
        ).fetchall()
        self.assertGreater(len(notifs), 0, "Customer must be alerted of availability change.")

    def test_event_tech_becomes_available_picks_up_waiting_job(self):
        """
        When a technician becomes 'available', the system must automatically
        scan for waiting unassigned jobs requiring matching skills and assign them.
        """
        # Create an unassigned job requiring Electrical
        cur = self.conn.execute(
            """INSERT INTO jobs (customer_name, required_skill, customer_latitude, customer_longitude,
                                  appointment_time, status)
               VALUES ('Waiting Electrical Customer', 'Electrical', 12.9800, 80.1900, '2026-10-05T15:00', 'unassigned')"""
        )
        waiting_job_id = cur.lastrowid
        self.conn.commit()

        # Find or create a technician with Electrical skill who is currently busy
        tech = self.conn.execute(
            "SELECT * FROM technicians WHERE skills LIKE '%Electrical%' AND availability!='available' LIMIT 1"
        ).fetchone()
        if not tech:
            cur = self.conn.execute(
                "INSERT INTO technicians (name, skills, availability, latitude, longitude) VALUES ('Test Electrician', 'Electrical', 'busy', 12.9800, 80.1900)"
            )
            tech_id = cur.lastrowid
            self.conn.commit()
        else:
            tech_id = tech["id"]

        # Trigger event: Technician becomes available
        events = handle_technician_availability_change(self.conn, tech_id, "available")
        self.assertGreater(len(events), 0)

        # Verify the technician was automatically assigned to a waiting unassigned job
        assigned_job = self.conn.execute(
            "SELECT * FROM jobs WHERE assigned_technician_id=? AND status='assigned'", (tech_id,)
        ).fetchone()
        self.assertIsNotNone(assigned_job)
        self.assertEqual(assigned_job["status"], "assigned")
        self.assertEqual(assigned_job["assigned_technician_id"], tech_id)
        self.assertIsNotNone(assigned_job["eta_low"])
        self.assertIsNotNone(assigned_job["eta_high"])

    def test_event_traffic_surge_auto_updates_active_jobs(self):
        """
        When city traffic condition changes to 'heavy', all active assigned jobs
        must have their ETAs recalculated, uncertainty bands expanded, and customer alerts sent.
        """
        # Trigger city-wide traffic shift
        updated_count = handle_traffic_shift(self.conn, "heavy")
        self.assertGreater(updated_count, 0, "Active jobs must be automatically updated.")

        # Verify eta_history reflects auto-update
        recent_log = self.conn.execute(
            "SELECT * FROM eta_history WHERE reason LIKE '%city traffic shifted to heavy%' LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(recent_log, "ETA history must log traffic shift event.")

        # Verify customer notification dispatched
        notif = self.conn.execute(
            "SELECT * FROM customer_notifications WHERE trigger_event='traffic_shift' LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(notif, "Customer notification must be dispatched on traffic shift.")


if __name__ == "__main__":
    unittest.main()
