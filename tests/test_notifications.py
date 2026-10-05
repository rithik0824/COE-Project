"""
tests/test_notifications.py
---------------------------
Unit tests for Requirement 3:
Customer-facing notification and communication channel (simulated SMS/Email/Push).
"""

import unittest
from app import get_db, init_db
from notification_engine import (
    log_notification,
    notify_assignment,
    notify_eta_update,
    notify_reassignment,
    notify_completion,
)


class TestNotifications(unittest.TestCase):

    def setUp(self):
        init_db()
        self.conn = get_db()

    def tearDown(self):
        self.conn.close()

    def test_log_notification_persists_to_database(self):
        """Simulated notification must persist to customer_notifications table with Delivered status."""
        notif_id = log_notification(
            self.conn, job_id=1, channel="SMS", recipient="+91 98401 11111",
            title="Test SMS Alert", message="Your technician is 15 mins away.",
            trigger_event="manual"
        )
        self.conn.commit()

        row = self.conn.execute("SELECT * FROM customer_notifications WHERE id=?", (notif_id,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["channel"], "SMS")
        self.assertEqual(row["recipient"], "+91 98401 11111")
        self.assertEqual(row["title"], "Test SMS Alert")
        self.assertEqual(row["status"], "Delivered")
        self.assertIsNotNone(row["sent_at"])

    def test_notify_assignment_dispatches_sms_push_email(self):
        """notify_assignment must generate SMS, Push, and Email notifications containing live tracking link."""
        cur = self.conn.execute(
            """INSERT INTO jobs (customer_name, required_skill, customer_latitude, customer_longitude, appointment_time)
               VALUES ('Notification Test Customer', 'AC Repair', 13.01, 80.21, '2026-10-05T10:00')"""
        )
        test_job_id = cur.lastrowid
        self.conn.commit()

        notify_assignment(
            self.conn, job_id=test_job_id, tech_name="Arun Kumar",
            eta_low=25, eta_high=35, reason="moderate traffic",
            customer_name="Ramesh", customer_phone="+91 98401 22222"
        )
        self.conn.commit()

        rows = self.conn.execute(
            "SELECT * FROM customer_notifications WHERE job_id=? AND trigger_event='auto_assign'",
            (test_job_id,)
        ).fetchall()

        channels = [r["channel"] for r in rows]
        self.assertIn("SMS", channels)
        self.assertIn("PUSH", channels)
        self.assertIn("EMAIL", channels)

        # Verify SMS text contains honest range and tracking link
        sms_row = [r for r in rows if r["channel"] == "SMS"][0]
        self.assertIn("25–35", sms_row["message"])
        self.assertIn(f"/track/{test_job_id}", sms_row["message"])

    def test_notify_eta_update(self):
        """notify_eta_update must dispatch SMS and Push alerts with new ETA range and reason."""
        cur = self.conn.execute(
            """INSERT INTO jobs (customer_name, required_skill, customer_latitude, customer_longitude, appointment_time)
               VALUES ('ETA Test Customer', 'Electrical', 13.02, 80.22, '2026-10-05T12:00')"""
        )
        test_job_id = cur.lastrowid
        self.conn.commit()

        notify_eta_update(
            self.conn, job_id=test_job_id, eta_low=40, eta_high=55,
            reason="heavy traffic congestion", trigger_event="traffic_shift",
            customer_name="Ramesh", customer_phone="+91 98401 22222"
        )
        self.conn.commit()

        rows = self.conn.execute(
            "SELECT * FROM customer_notifications WHERE job_id=? AND trigger_event='traffic_shift'",
            (test_job_id,)
        ).fetchall()
        self.assertGreaterEqual(len(rows), 2)
        sms = [r for r in rows if r["channel"] == "SMS"][0]
        self.assertIn("40–55", sms["message"])
        self.assertIn("heavy traffic congestion", sms["message"])




if __name__ == "__main__":
    unittest.main()
