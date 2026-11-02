"""
tests/test_routes.py
--------------------
Flask route smoke tests to verify that every route returns expected status codes,
renders cleanly without template errors, and processes forms properly.
"""

import unittest
from app import app, init_db


class TestRouteSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        init_db()

    def setUp(self):
        self.client = app.test_client()

    def test_route_index_redirect(self):
        """GET / must redirect to /dashboard (302)."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/dashboard", res.headers["Location"])

    def test_route_dashboard(self):
        """GET /dashboard must return 200 and contain overview metrics."""
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Large-Scale Simulated Field-Service Dataset", res.data)
        self.assertIn(b"Live queue", res.data)

    def test_route_jobs_board(self):
        """GET /jobs must return 200 and support pagination & filter parameters."""
        res = self.client.get("/jobs")
        self.assertEqual(res.status_code, 200)

        # Filter by search query
        res_q = self.client.get("/jobs?q=Ramesh")
        self.assertEqual(res_q.status_code, 200)

        # Filter by status
        res_status = self.client.get("/jobs?status=assigned")
        self.assertEqual(res_status.status_code, 200)

        # Filter by skill
        res_skill = self.client.get("/jobs?skill=Plumbing")
        self.assertEqual(res_skill.status_code, 200)

    def test_route_job_detail(self):
        """GET /jobs/1 must return 200 and show ETA, history, and customer notifications."""
        res = self.client.get("/jobs/1")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Live ETA to customer", res.data)
        self.assertIn(b"Customer Notifications", res.data)

    def test_route_technicians(self):
        """GET /technicians must return 200 and list technicians."""
        res = self.client.get("/technicians")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Technicians", res.data)

    def test_route_demo_scenarios(self):
        """GET /demo must return 200 and show all four edge case cards."""
        res = self.client.get("/demo")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Four edge cases, seeded automatically", res.data)

    def test_route_baseline(self):
        """GET /baseline must return 200 and render the baseline comparison table."""
        res = self.client.get("/baseline")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Baseline (fixed ETA)", res.data)

    def test_route_analytics(self):
        """GET /analytics must return 200 and render visual analytics charts."""
        res = self.client.get("/analytics")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Large-Scale Benchmark Analytics", res.data)

    def test_route_presentation(self):
        """GET /presentation must return 200 and render slide deck."""
        res = self.client.get("/presentation")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Live ETA", res.data)

    def test_route_validation(self):
        """GET /validation must return 200 and show pilot study KPIs and interview notes (Requirement 1)."""
        res = self.client.get("/validation")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Stakeholder Validation", res.data)
        self.assertIn(b"Rajesh Kannan", res.data)

    def test_route_submit_feedback(self):
        """POST /validation/feedback must save feedback and redirect (Requirement 1)."""
        res = self.client.post("/validation/feedback", data={
            "stakeholder_name": "Test Evaluator",
            "role": "Project Evaluator",
            "organization_or_area": "College Viva Board",
            "rating": "5",
            "category": "ETA Accuracy",
            "feedback_text": "Automated unit tests and edge cases fully verified."
        })
        self.assertEqual(res.status_code, 302)
        self.assertIn("/validation", res.headers["Location"])

    def test_route_customer_tracker(self):
        """GET /track/1 must return 200 and render customer live tracking portal (Requirement 3)."""
        res = self.client.get("/track/1")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Fieldline Customer Care", res.data)
        self.assertIn(b"Simulated Customer Notifications", res.data)

    def test_route_customer_track_refresh(self):
        """POST /track/1/refresh must refresh ETA and redirect back to customer view."""
        res = self.client.post("/track/1/refresh")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/track/1", res.headers["Location"])

    def test_route_add_technician(self):
        """POST /technicians/add must create technician and redirect."""
        res = self.client.post("/technicians/add", data={
            "name": "Smoke Test Tech",
            "skills": ["AC Repair", "Plumbing"],
            "availability": "available",
            "latitude": "13.0100",
            "longitude": "80.2200"
        })
        self.assertEqual(res.status_code, 302)

    def test_route_toggle_technician(self):
        """POST /technicians/1/toggle must update availability and trigger events."""
        res = self.client.post("/technicians/1/toggle", data={
            "availability": "available"
        })
        self.assertEqual(res.status_code, 302)

    def test_route_add_job(self):
        """POST /jobs/add must create a job, auto-assign it, and redirect to job detail."""
        res = self.client.post("/jobs/add", data={
            "customer_name": "Smoke Customer",
            "customer_phone": "+91 98409 99999",
            "required_skill": "AC Repair",
            "latitude": "13.0300",
            "longitude": "80.2400",
            "appointment_time": "2026-10-05T16:00"
        })
        self.assertEqual(res.status_code, 302)
        self.assertIn("/jobs/", res.headers["Location"])

    def test_route_override_job(self):
        """POST /jobs/1/override must manually assign technician and redirect."""
        res = self.client.post("/jobs/1/override", data={
            "technician_id": "2",
            "reason": "Test manual override"
        })
        self.assertEqual(res.status_code, 302)

    def test_route_resimulate_job(self):
        """POST /jobs/1/resimulate must recalculate ETA and redirect."""
        res = self.client.post("/jobs/1/resimulate")
        self.assertEqual(res.status_code, 302)

    def test_route_update_job_status(self):
        """POST /jobs/1/status must change status (e.g. en_route) and update ETA."""
        res = self.client.post("/jobs/1/status", data={
            "status": "en_route"
        })
        self.assertEqual(res.status_code, 302)

    def test_route_report_job_delay(self):
        """POST /jobs/1/report-delay must add on-site delay and notify customer."""
        res = self.client.post("/jobs/1/report-delay", data={
            "delay_minutes": "15"
        })
        self.assertEqual(res.status_code, 302)

    def test_route_send_manual_notification(self):
        """POST /jobs/1/notify must dispatch simulated notification to customer."""
        res = self.client.post("/jobs/1/notify", data={
            "channel": "SMS",
            "title": "Smoke Alert",
            "message": "Testing customer message alert."
        })
        self.assertEqual(res.status_code, 302)

    def test_route_traffic_shift_event(self):
        """POST /events/traffic-shift must auto-update active job ETAs."""
        res = self.client.post("/events/traffic-shift", data={
            "traffic_level": "heavy"
        })
        self.assertEqual(res.status_code, 302)

    def test_route_complete_job(self):
        """POST /jobs/1/complete must mark job as completed and free technician."""
        res = self.client.post("/jobs/1/complete")
        self.assertEqual(res.status_code, 302)

    def test_route_workflow(self):
        """GET /workflow must return 200 and render Field-Workflow Map."""
        res = self.client.get("/workflow")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Field-Workflow Map", res.data)

    def test_route_experiment(self):
        """GET /experiment must return 200 and render Measurable Experiment scorecard."""
        res = self.client.get("/experiment")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Measurable Scorecard", res.data)

    def test_route_experiment_run(self):
        """POST /experiment/run must re-run experiment and redirect to /experiment (302)."""
        res = self.client.post("/experiment/run")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/experiment", res.headers["Location"])

    def test_route_failure_modes(self):
        """GET /failure-modes must return 200 and render Failure-Mode Analysis."""
        res = self.client.get("/failure-modes")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"FMEA Risk Priority Matrix", res.data)

    def test_route_report(self):
        """GET /report must return 200 and render Project Review Report."""
        res = self.client.get("/report")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Project Review Report", res.data)


if __name__ == "__main__":
    unittest.main()
