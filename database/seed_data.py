"""
seed_data.py
------------
Populates the freshly-created SQLite database with sample technicians and
jobs so the app is immediately usable.

Seeds 5,000+ realistic job records, 200+ technicians, and 10,000+ history logs
for a large-scale statistical benchmark, while keeping the four required demo edge
cases deterministically seeded at the top.
"""

import random
from datetime import datetime, timedelta

from eta_engine import calculate_eta, haversine_km

SKILL_LIST = ["AC Repair", "Electrical", "Plumbing", "Appliance Repair", "General Maintenance"]

FIRST_NAMES = [
    "Arun", "Priya", "Suresh", "Divya", "Karthik", "Meena", "Anitha", "Vignesh", "Kavya", "Ganesh",
    "Rajesh", "Lakshmi", "Rahul", "Vikram", "Maya", "Sanjay", "Deepa", "Vijay", "Swetha", "Harish",
    "Surya", "Nandhini", "Ashok", "Revathi", "Balaji", "Sindhu", "Pradeep", "Keerthi", "Manoj", "Pooja",
    "Santhosh", "Bhavana", "Dinesh", "Preeti", "Gokul", "Aswini", "Kiran", "Sowmya", "Naveen", "Archana",
    "Ramesh", "Geetha", "Siddharth", "Aarthi", "Venkat", "Janani", "Srinivasan", "Pavithra", "Mohan", "Devi"
]

LAST_NAMES = [
    "Kumar", "Sharma", "Babu", "Rajan", "Raja", "Iyer", "Rao", "Menon", "Nair", "Prasad",
    "Kannan", "Reddy", "Chandran", "Sundaram", "Krishnan", "Subramanian", "Murugan", "Nathan", "Pillai", "Venkatesh"
]

CUSTOMER_PREFIXES = [
    "Mr. Anand", "Mrs. Rekha", "Dr. Karthi", "Prof. Selvi", "Er. Muthu", "Ms. Nitya", "Mr. Baskar",
    "Mrs. Uma", "Mr. Saravanan", "Mrs. Latha", "Mr. Elango", "Mrs. Chitra", "Mr. Gopinath", "Mrs. Vidya"
]


def _log_eta(conn, job_id, low, high, reason):
    conn.execute(
        "INSERT INTO eta_history (job_id, eta_low, eta_high, reason) VALUES (?,?,?,?)",
        (job_id, low, high, reason),
    )


def _log_assign(conn, job_id, tech_id, action, reason):
    conn.execute(
        "INSERT INTO assignment_history (job_id, technician_id, action, reason) VALUES (?,?,?,?)",
        (job_id, tech_id, action, reason),
    )


def _insert_job(conn, customer, skill, lat, lng, time_str, demo_case=None):
    cur = conn.execute(
        """INSERT INTO jobs
           (customer_name, required_skill, customer_latitude, customer_longitude,
            appointment_time, status, demo_case)
           VALUES (?,?,?,?,?,?,?)""",
        (customer, skill, lat, lng, time_str, "pending", demo_case),
    )
    return cur.lastrowid


def seed(conn):
    rng = random.Random(7)  # fixed seed -> same demo every time the app starts
    today = datetime.now().strftime("%Y-%m-%d")
    today_dt = datetime.now()

    # ---------------------------------------------------------------
    # Demo Technicians (Top 6 for exact demo reproducibility)
    # ---------------------------------------------------------------
    demo_techs = [
        ("Arun Kumar",   "AC Repair,Electrical",                "available",   12.9550, 80.2100),
        ("Priya Sharma", "General Maintenance,Appliance Repair", "available",   13.0200, 80.2500),
        ("Suresh Babu",  "Electrical,Appliance Repair",          "busy",        12.9800, 80.1800),
        ("Divya Rajan",  "AC Repair,Appliance Repair",           "available",   13.0500, 80.1500),
        ("Karthik Raja", "Plumbing",                             "unavailable", 12.9200, 80.2200),
        ("Meena Iyer",   "General Maintenance,Electrical",       "unavailable", 13.0000, 80.2800),
    ]

    tech_id = {}
    for name, skills, avail, lat, lng in demo_techs:
        cur = conn.execute(
            "INSERT INTO technicians (name, skills, availability, latitude, longitude) VALUES (?,?,?,?,?)",
            (name, skills, avail, lat, lng),
        )
        tech_id[name] = cur.lastrowid

    # Generate additional 194 technicians (Total: 200 technicians)
    additional_techs = []
    for i in range(7, 201):
        fn = rng.choice(FIRST_NAMES)
        ln = rng.choice(LAST_NAMES)
        t_name = f"{fn} {ln} ({i})"
        k = rng.randint(1, 3)
        t_skills = ",".join(rng.sample(SKILL_LIST, k))
        t_avail = rng.choice(["available", "available", "available", "busy", "busy", "unavailable"])
        t_lat = round(rng.uniform(12.9000, 13.1500), 4)
        t_lng = round(rng.uniform(80.1000, 80.3000), 4)
        additional_techs.append((t_name, t_skills, t_avail, t_lat, t_lng))

    conn.executemany(
        "INSERT INTO technicians (name, skills, availability, latitude, longitude) VALUES (?,?,?,?,?)",
        additional_techs,
    )
    conn.commit()

    all_techs = conn.execute("SELECT * FROM technicians").fetchall()

    def tech_row(name):
        return conn.execute("SELECT * FROM technicians WHERE id=?", (tech_id[name],)).fetchone()

    def job_row(job_id):
        return conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()

    # ---------------------------------------------------------------
    # Demo Case 1: HEAVY TRAFFIC
    # ---------------------------------------------------------------
    j1 = _insert_job(conn, "Ramesh Iyer", "AC Repair", 13.0270, 80.2100, f"{today}T09:00", "heavy_traffic")
    eta1 = calculate_eta(tech_row("Arun Kumar"), job_row(j1), previous_job_delay=False, rng=rng, forced_traffic="heavy")
    conn.execute(
        "UPDATE jobs SET assigned_technician_id=?, status=?, eta_low=?, eta_high=?, traffic_level=?, delay_reason=? WHERE id=?",
        (tech_id["Arun Kumar"], "assigned", eta1["eta_low"], eta1["eta_high"], eta1["traffic_level"], eta1["reason"], j1),
    )
    conn.execute("UPDATE technicians SET availability='busy' WHERE id=?", (tech_id["Arun Kumar"],))
    _log_assign(conn, j1, tech_id["Arun Kumar"], "auto_assigned",
                f"Nearest available AC Repair technician selected ({eta1['distance_km']} km away).")
    _log_eta(conn, j1, eta1["eta_low"], eta1["eta_high"], eta1["reason"])

    # ---------------------------------------------------------------
    # Demo Case 2: TECHNICIAN UNAVAILABLE
    # ---------------------------------------------------------------
    j2 = _insert_job(conn, "Lakshmi Menon", "Plumbing", 13.0100, 80.1950, f"{today}T11:30", "technician_unavailable")
    conn.execute(
        "UPDATE jobs SET status=?, assigned_technician_id=NULL, delay_reason=? WHERE id=?",
        ("unassigned", "No technician with the required skill (Plumbing) is currently available.", j2),
    )
    _log_assign(conn, j2, None, "unassigned",
                "Auto-assignment failed: the only Plumbing-skilled technician (Karthik Raja) is unavailable (on leave).")

    # ---------------------------------------------------------------
    # Demo Case 3: SERVICE / JOB TAKING LONGER THAN EXPECTED
    # ---------------------------------------------------------------
    j3 = _insert_job(conn, "Anitha Rao", "Electrical", 12.9750, 80.1850, f"{today}T14:00", "service_overrun")
    eta3 = calculate_eta(tech_row("Suresh Babu"), job_row(j3), previous_job_delay=True, rng=rng, forced_traffic="moderate")
    conn.execute(
        "UPDATE jobs SET assigned_technician_id=?, status=?, eta_low=?, eta_high=?, traffic_level=?, delay_reason=? WHERE id=?",
        (tech_id["Suresh Babu"], "assigned", eta3["eta_low"], eta3["eta_high"], eta3["traffic_level"], eta3["reason"], j3),
    )
    _log_assign(conn, j3, tech_id["Suresh Babu"], "auto_assigned",
                "Suresh Babu pre-assigned for this Electrical job; still finishing a previous appointment.")
    _log_eta(conn, j3, eta3["eta_low"], eta3["eta_high"], eta3["reason"])
    eta3b = calculate_eta(tech_row("Suresh Babu"), job_row(j3), previous_job_delay=True, rng=rng, forced_traffic="moderate")
    eta3b["eta_low"] += 8
    eta3b["eta_high"] += 10
    conn.execute(
        "UPDATE jobs SET eta_low=?, eta_high=?, delay_reason=? WHERE id=?",
        (eta3b["eta_low"], eta3b["eta_high"], eta3b["reason"], j3),
    )
    _log_eta(conn, j3, eta3b["eta_low"], eta3b["eta_high"],
              "previous job at prior address overran further than first estimated")

    # ---------------------------------------------------------------
    # Demo Case 4: TECHNICIAN DOES NOT HAVE REQUIRED SKILL
    # ---------------------------------------------------------------
    j4 = _insert_job(conn, "Vignesh S", "Plumbing", 12.9450, 80.2400, f"{today}T16:00", "skill_mismatch")
    conn.execute(
        "UPDATE jobs SET status=?, assigned_technician_id=NULL, delay_reason=? WHERE id=?",
        ("unassigned", "No technician with the required skill (Plumbing) is currently available.", j4),
    )
    _log_assign(conn, j4, None, "unassigned", "Auto-assignment failed: no available Plumbing technician.")
    eta4 = calculate_eta(tech_row("Priya Sharma"), job_row(j4), previous_job_delay=False, rng=rng, forced_traffic="light")
    conn.execute(
        "UPDATE jobs SET assigned_technician_id=?, status=?, eta_low=?, eta_high=?, traffic_level=?, delay_reason=? WHERE id=?",
        (tech_id["Priya Sharma"], "assigned", eta4["eta_low"], eta4["eta_high"], eta4["traffic_level"],
         eta4["reason"] + " | skill mismatch override", j4),
    )
    conn.execute("UPDATE technicians SET availability='busy' WHERE id=?", (tech_id["Priya Sharma"],))
    _log_assign(conn, j4, tech_id["Priya Sharma"], "manual_override",
                "Dispatcher override: nearest technician dispatched for a temporary fix while awaiting a "
                "Plumbing specialist. WARNING: technician does not have the required skill for this job.")
    _log_eta(conn, j4, eta4["eta_low"], eta4["eta_high"], eta4["reason"])

    # Additional demo jobs
    j5 = _insert_job(conn, "Kavya Nair", "AC Repair", 13.0450, 80.1600, f"{today}T13:00")
    eta5 = calculate_eta(tech_row("Divya Rajan"), job_row(j5), previous_job_delay=False, rng=rng, forced_traffic="light")
    conn.execute(
        "UPDATE jobs SET assigned_technician_id=?, status=?, eta_low=?, eta_high=?, traffic_level=?, delay_reason=? WHERE id=?",
        (tech_id["Divya Rajan"], "assigned", eta5["eta_low"], eta5["eta_high"], eta5["traffic_level"], eta5["reason"], j5),
    )
    conn.execute("UPDATE technicians SET availability='busy' WHERE id=?", (tech_id["Divya Rajan"],))
    _log_assign(conn, j5, tech_id["Divya Rajan"], "auto_assigned",
                f"Nearest available AC Repair technician selected ({eta5['distance_km']} km away).")
    _log_eta(conn, j5, eta5["eta_low"], eta5["eta_high"], eta5["reason"])

    j6 = _insert_job(conn, "Ganesh Prasad", "General Maintenance", 13.0350, 80.2450, f"{today}T10:00")
    conn.execute("UPDATE jobs SET status='completed' WHERE id=?", (j6,))
    _log_assign(conn, j6, tech_id["Meena Iyer"], "completed", "Completed earlier today before Meena went on leave.")
    conn.execute(
        "UPDATE jobs SET assigned_technician_id=?, eta_low=?, eta_high=?, traffic_level=?, delay_reason=? WHERE id=?",
        (tech_id["Meena Iyer"], 25, 35, "light", "normal traffic conditions", j6),
    )
    _log_eta(conn, j6, 25, 35, "normal traffic conditions")

    conn.commit()

    # ---------------------------------------------------------------
    # Bulk generation of 5,000 jobs to reach 5,006 total benchmark dataset
    # ---------------------------------------------------------------
    bulk_jobs = []
    statuses = ["assigned", "assigned", "assigned", "completed", "completed", "unassigned", "pending"]
    traffic_types = ["light", "moderate", "heavy"]

    for i in range(7, 5007):
        prefix = rng.choice(CUSTOMER_PREFIXES)
        fn = rng.choice(FIRST_NAMES)
        ln = rng.choice(LAST_NAMES)
        cname = f"{prefix} {fn} {ln}"
        skill = rng.choice(SKILL_LIST)
        clat = round(rng.uniform(12.9000, 13.1500), 4)
        clng = round(rng.uniform(80.1000, 80.3000), 4)

        offset_days = rng.randint(-14, 3)
        offset_hours = rng.randint(8, 20)
        offset_mins = rng.choice([0, 15, 30, 45])
        job_dt = today_dt + timedelta(days=offset_days, hours=(offset_hours - today_dt.hour), minutes=(offset_mins - today_dt.minute))
        time_str = job_dt.strftime("%Y-%m-%dT%H:%M")

        status = rng.choice(statuses)

        if status == "unassigned":
            tech_assigned = None
            eta_l, eta_h = None, None
            traffic = None
            d_reason = "No available technician with matching skill."
        else:
            matching_techs = [t for t in all_techs if skill in t["skills"].split(",")]
            chosen_tech = rng.choice(matching_techs) if matching_techs else rng.choice(all_techs)
            tech_assigned = chosen_tech["id"]

            dist_km = haversine_km(chosen_tech["latitude"], chosen_tech["longitude"], clat, clng)
            traffic = rng.choice(traffic_types)
            base_min = (dist_km / 24.0) * 60
            mult = 1.7 if traffic == "heavy" else (1.3 if traffic == "moderate" else 1.0)
            t_min = base_min * mult + 5

            prev_delay = rng.random() < 0.15
            delay_min = rng.randint(10, 25) if prev_delay else 0
            t_min += delay_min

            unc = 10 + (8 if traffic == "heavy" else 4) + (10 if prev_delay else 0)
            eta_l = max(5, round(t_min - unc / 2))
            eta_h = round(t_min + unc / 2)

            reasons = []
            if traffic == "heavy":
                reasons.append("heavy traffic on route")
            elif traffic == "moderate":
                reasons.append("moderate traffic")
            if prev_delay:
                reasons.append("previous job overran")
            d_reason = "; ".join(reasons) if reasons else "normal traffic conditions"

        created_str = job_dt.strftime("%Y-%m-%d %H:%M:%S")
        bulk_jobs.append((cname, skill, clat, clng, time_str, status, tech_assigned, eta_l, eta_h, traffic, d_reason, None, created_str))

    conn.executemany(
        """INSERT INTO jobs
           (customer_name, required_skill, customer_latitude, customer_longitude,
            appointment_time, status, assigned_technician_id, eta_low, eta_high, traffic_level, delay_reason, demo_case, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        bulk_jobs,
    )
    conn.commit()

    # Bulk generation of 5,000+ history records
    job_rows = conn.execute("SELECT id, assigned_technician_id, eta_low, eta_high, delay_reason, status FROM jobs WHERE id >= 7").fetchall()
    bulk_eta_logs = []
    bulk_assign_logs = []

    for row in job_rows:
        jid = row["id"]
        tid = row["assigned_technician_id"]
        st = row["status"]
        if row["eta_low"] is not None:
            bulk_eta_logs.append((jid, row["eta_low"], row["eta_high"], row["delay_reason"]))
        if st in ("assigned", "completed"):
            act = "auto_assigned" if st == "assigned" else "completed"
            bulk_assign_logs.append((jid, tid, act, f"Job processed with status {st}."))
        elif st == "unassigned":
            bulk_assign_logs.append((jid, None, "unassigned", "Auto-assignment failed: no matching technician."))

    conn.executemany(
        "INSERT INTO eta_history (job_id, eta_low, eta_high, reason) VALUES (?,?,?,?)",
        bulk_eta_logs,
    )
    conn.executemany(
        "INSERT INTO assignment_history (job_id, technician_id, action, reason) VALUES (?,?,?,?)",
        bulk_assign_logs,
    )

    conn.commit()

