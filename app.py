"""
Live ETA Communication and Technician Assignment System
---------------------------------------------------------
College mini-project. Fully local, fully simulated:
- No paid APIs, no Google Maps, no cloud services, no Docker.
- Flask + SQLite + HTML/CSS/JS (Bootstrap CDN for styling only).

Run with:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000 in a browser.
"""

import os
import random
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash

from eta_engine import calculate_eta, haversine_km, random_coordinate
from database import seed_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "eta_system.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")

app = Flask(__name__)
app.secret_key = "college-project-live-eta-system-2026"

SKILL_OPTIONS = ["AC Repair", "Electrical", "Plumbing", "Appliance Repair", "General Maintenance"]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """(Re)create the database with fresh schema + sample data on every start."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_db()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    seed_data.seed(conn)
    conn.close()


def log_eta(conn, job_id, low, high, reason):
    conn.execute(
        "INSERT INTO eta_history (job_id, eta_low, eta_high, reason) VALUES (?,?,?,?)",
        (job_id, low, high, reason),
    )


def log_assignment(conn, job_id, tech_id, action, reason):
    conn.execute(
        "INSERT INTO assignment_history (job_id, technician_id, action, reason) VALUES (?,?,?,?)",
        (job_id, tech_id, action, reason),
    )


def auto_assign(conn, job_id):
    """Core assignment algorithm: matching skill + availability + nearest technician."""
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    technicians = conn.execute("SELECT * FROM technicians").fetchall()

    candidates = [
        t for t in technicians
        if job["required_skill"] in [s.strip() for s in t["skills"].split(",")]
    ]
    available = [t for t in candidates if t["availability"] == "available"]

    if not available:
        conn.execute(
            "UPDATE jobs SET status=?, assigned_technician_id=NULL, delay_reason=?, eta_low=NULL, eta_high=NULL WHERE id=?",
            ("unassigned", "No technician with the required skill is currently available.", job_id),
        )
        log_assignment(conn, job_id, None, "unassigned",
                        "Auto-assignment failed: no available technician with matching skill.")
        conn.commit()
        return

    best = min(available, key=lambda t: haversine_km(
        t["latitude"], t["longitude"], job["customer_latitude"], job["customer_longitude"]))

    previous_delay = random.random() < 0.18
    eta = calculate_eta(best, job, previous_job_delay=previous_delay)

    conn.execute(
        "UPDATE jobs SET assigned_technician_id=?, status=?, eta_low=?, eta_high=?, traffic_level=?, delay_reason=? WHERE id=?",
        (best["id"], "assigned", eta["eta_low"], eta["eta_high"], eta["traffic_level"], eta["reason"], job_id),
    )
    conn.execute("UPDATE technicians SET availability='busy' WHERE id=?", (best["id"],))
    log_assignment(conn, job_id, best["id"], "auto_assigned",
                    f"Nearest available technician with matching skill selected ({eta['distance_km']} km away).")
    log_eta(conn, job_id, eta["eta_low"], eta["eta_high"], eta["reason"])
    conn.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    conn = get_db()
    jobs = conn.execute(
        """SELECT jobs.*, technicians.name AS tech_name
           FROM jobs LEFT JOIN technicians ON jobs.assigned_technician_id = technicians.id
           ORDER BY jobs.id DESC LIMIT 20"""
    ).fetchall()
    technicians = conn.execute("SELECT * FROM technicians ORDER BY name LIMIT 20").fetchall()

    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    assigned = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='assigned'").fetchone()[0]
    unassigned = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='unassigned'").fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='completed'").fetchone()[0]
    total_tech = conn.execute("SELECT COUNT(*) FROM technicians").fetchone()[0]
    available_tech = conn.execute("SELECT COUNT(*) FROM technicians WHERE availability='available'").fetchone()[0]

    stats = {
        "total_jobs": total_jobs,
        "assigned": assigned,
        "unassigned": unassigned,
        "completed": completed,
        "total_tech": total_tech,
        "available_tech": available_tech,
    }
    conn.close()
    return render_template("dashboard.html", jobs=jobs, technicians=technicians, stats=stats, now=datetime.now())


@app.route("/technicians")
def technicians():
    conn = get_db()
    techs = conn.execute("SELECT * FROM technicians ORDER BY name").fetchall()
    conn.close()
    return render_template("technicians.html", technicians=techs, skill_options=SKILL_OPTIONS)


@app.route("/technicians/add", methods=["POST"])
def add_technician():
    name = request.form["name"].strip()
    skills = ",".join(request.form.getlist("skills"))
    availability = request.form["availability"]
    lat = float(request.form["latitude"])
    lng = float(request.form["longitude"])
    conn = get_db()
    conn.execute(
        "INSERT INTO technicians (name, skills, availability, latitude, longitude) VALUES (?,?,?,?,?)",
        (name, skills, availability, lat, lng),
    )
    conn.commit()
    conn.close()
    flash(f'Technician "{name}" added.', "success")
    return redirect(url_for("technicians"))


@app.route("/technicians/<int:tech_id>/toggle", methods=["POST"])
def toggle_technician(tech_id):
    conn = get_db()
    tech = conn.execute("SELECT * FROM technicians WHERE id=?", (tech_id,)).fetchone()
    new_status = request.form["availability"]
    conn.execute("UPDATE technicians SET availability=? WHERE id=?", (new_status, tech_id))
    conn.commit()
    conn.close()
    flash(f'{tech["name"]} status updated to "{new_status}".', "info")
    return redirect(url_for("technicians"))


@app.route("/jobs")
def jobs():
    conn = get_db()
    page = request.args.get("page", 1, type=int)
    per_page = 50
    search_q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    skill_filter = request.args.get("skill", "").strip()

    where_clauses = []
    params = []

    if search_q:
        where_clauses.append("jobs.customer_name LIKE ?")
        params.append(f"%{search_q}%")
    if status_filter:
        where_clauses.append("jobs.status = ?")
        params.append(status_filter)
    if skill_filter:
        where_clauses.append("jobs.required_skill = ?")
        params.append(skill_filter)

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    count_query = f"SELECT COUNT(*) FROM jobs {where_sql}"
    total_count = conn.execute(count_query, params).fetchone()[0]

    offset = (page - 1) * per_page
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    select_query = f"""
        SELECT jobs.*, technicians.name AS tech_name
        FROM jobs LEFT JOIN technicians ON jobs.assigned_technician_id = technicians.id
        {where_sql}
        ORDER BY jobs.id ASC
        LIMIT ? OFFSET ?
    """
    params.extend([per_page, offset])
    job_rows = conn.execute(select_query, params).fetchall()

    conn.close()
    return render_template(
        "jobs.html",
        jobs=job_rows,
        skill_options=SKILL_OPTIONS,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        search_q=search_q,
        status_filter=status_filter,
        skill_filter=skill_filter,
    )


@app.route("/jobs/add", methods=["POST"])
def add_job():
    customer_name = request.form["customer_name"].strip()
    required_skill = request.form["required_skill"]
    lat = float(request.form["latitude"])
    lng = float(request.form["longitude"])
    appointment_time = request.form["appointment_time"]

    conn = get_db()
    cur = conn.execute(
        """INSERT INTO jobs (customer_name, required_skill, customer_latitude, customer_longitude,
                              appointment_time, status)
           VALUES (?,?,?,?,?,?)""",
        (customer_name, required_skill, lat, lng, appointment_time, "pending"),
    )
    job_id = cur.lastrowid
    conn.commit()
    auto_assign(conn, job_id)
    conn.close()
    flash(f'Job for "{customer_name}" created and processed by the assignment engine.', "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    conn = get_db()
    job = conn.execute(
        """SELECT jobs.*, technicians.name AS tech_name, technicians.skills AS tech_skills
           FROM jobs LEFT JOIN technicians ON jobs.assigned_technician_id = technicians.id
           WHERE jobs.id=?""",
        (job_id,),
    ).fetchone()
    all_technicians = conn.execute(
        """SELECT * FROM technicians 
           ORDER BY CASE WHEN id=? THEN 0 WHEN availability='available' THEN 1 ELSE 2 END, name 
           LIMIT 150""",
        (job["assigned_technician_id"] or 0,),
    ).fetchall()
    eta_history = conn.execute(
        "SELECT * FROM eta_history WHERE job_id=? ORDER BY id DESC", (job_id,)
    ).fetchall()
    assignment_history = conn.execute(
        """SELECT assignment_history.*, technicians.name AS tech_name
           FROM assignment_history LEFT JOIN technicians ON assignment_history.technician_id = technicians.id
           WHERE job_id=? ORDER BY id DESC""",
        (job_id,),
    ).fetchall()
    conn.close()
    return render_template(
        "job_detail.html", job=job, technicians=all_technicians,
        eta_history=eta_history, assignment_history=assignment_history,
    )


@app.route("/jobs/<int:job_id>/override", methods=["POST"])
def override_job(job_id):
    technician_id = int(request.form["technician_id"])
    reason = request.form.get("reason", "").strip() or "Manual dispatcher override"

    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    tech = conn.execute("SELECT * FROM technicians WHERE id=?", (technician_id,)).fetchone()
    old_tech_id = job["assigned_technician_id"]

    skill_match = job["required_skill"] in [s.strip() for s in tech["skills"].split(",")]
    eta = calculate_eta(tech, job, previous_job_delay=False)

    note = reason
    reason_text = eta["reason"]
    if not skill_match:
        note += " | WARNING: technician does not have the required skill for this job."
        reason_text += " | skill mismatch override"

    if old_tech_id and old_tech_id != technician_id:
        conn.execute("UPDATE technicians SET availability='available' WHERE id=?", (old_tech_id,))

    conn.execute(
        "UPDATE jobs SET assigned_technician_id=?, status=?, eta_low=?, eta_high=?, traffic_level=?, delay_reason=? WHERE id=?",
        (technician_id, "assigned", eta["eta_low"], eta["eta_high"], eta["traffic_level"], reason_text, job_id),
    )
    conn.execute("UPDATE technicians SET availability='busy' WHERE id=?", (technician_id,))
    log_assignment(conn, job_id, technician_id, "manual_override", note)
    log_eta(conn, job_id, eta["eta_low"], eta["eta_high"], reason_text)
    conn.commit()
    conn.close()
    flash("Assignment manually overridden by dispatcher." + (" (Skill mismatch flagged)" if not skill_match else ""),
          "warning" if not skill_match else "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.route("/jobs/<int:job_id>/resimulate", methods=["POST"])
def resimulate(job_id):
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job["assigned_technician_id"]:
        auto_assign(conn, job_id)
        flash("Re-ran assignment engine for this job.", "info")
    else:
        tech = conn.execute("SELECT * FROM technicians WHERE id=?", (job["assigned_technician_id"],)).fetchone()
        previous_delay = random.random() < 0.25
        eta = calculate_eta(tech, job, previous_job_delay=previous_delay)
        conn.execute(
            "UPDATE jobs SET eta_low=?, eta_high=?, traffic_level=?, delay_reason=? WHERE id=?",
            (eta["eta_low"], eta["eta_high"], eta["traffic_level"], eta["reason"], job_id),
        )
        log_eta(conn, job_id, eta["eta_low"], eta["eta_high"], eta["reason"])
        conn.commit()
        flash("ETA re-simulated with current live conditions.", "info")
    conn.close()
    return redirect(url_for("job_detail", job_id=job_id))


@app.route("/jobs/<int:job_id>/complete", methods=["POST"])
def complete_job(job_id):
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.execute("UPDATE jobs SET status='completed' WHERE id=?", (job_id,))
    free_note = "technician freed for new jobs."
    if job["assigned_technician_id"]:
        other_active = conn.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE assigned_technician_id=? AND status='assigned' AND id!=?",
            (job["assigned_technician_id"], job_id),
        ).fetchone()["c"]
        if other_active == 0:
            conn.execute("UPDATE technicians SET availability='available' WHERE id=?", (job["assigned_technician_id"],))
        else:
            free_note = "technician still has other active jobs, so availability was left unchanged."
    log_assignment(conn, job_id, job["assigned_technician_id"], "completed",
                    f"Job marked completed by dispatcher; {free_note}")
    conn.commit()
    conn.close()
    flash("Job marked as completed.", "success")
    return redirect(url_for("job_detail", job_id=job_id))


@app.route("/demo")
def demo():
    conn = get_db()
    demo_jobs = conn.execute(
        """SELECT jobs.*, technicians.name AS tech_name
           FROM jobs LEFT JOIN technicians ON jobs.assigned_technician_id = technicians.id
           WHERE jobs.demo_case IS NOT NULL
           ORDER BY CASE jobs.demo_case
               WHEN 'heavy_traffic' THEN 1
               WHEN 'technician_unavailable' THEN 2
               WHEN 'service_overrun' THEN 3
               WHEN 'skill_mismatch' THEN 4 END"""
    ).fetchall()
    conn.close()
    return render_template("demo.html", jobs=demo_jobs)


@app.route("/baseline")
def baseline():
    conn = get_db()
    jobs_with_eta = conn.execute(
        """SELECT jobs.*, technicians.name AS tech_name
           FROM jobs LEFT JOIN technicians ON jobs.assigned_technician_id = technicians.id
           WHERE jobs.eta_low IS NOT NULL
           ORDER BY jobs.id ASC LIMIT 100"""
    ).fetchall()

    all_eta_jobs = conn.execute("SELECT eta_low, eta_high FROM jobs WHERE eta_low IS NOT NULL").fetchall()
    conn.close()

    rng = random.Random(99)
    fixed_baseline_eta = 35

    rows = []
    baseline_errors, improved_errors = [], []
    for j in all_eta_jobs:
        improved_mid = (j["eta_low"] + j["eta_high"]) // 2
        true_arrival = max(5, improved_mid + rng.randint(-4, 4))

        baseline_error = abs(fixed_baseline_eta - true_arrival)
        improved_error = abs(improved_mid - true_arrival)
        baseline_errors.append(baseline_error)
        improved_errors.append(improved_error)

    for j in jobs_with_eta:
        improved_mid = (j["eta_low"] + j["eta_high"]) // 2
        true_arrival = max(5, improved_mid + rng.randint(-4, 4))
        rows.append({
            "customer": j["customer_name"],
            "baseline_eta": fixed_baseline_eta,
            "improved_low": j["eta_low"],
            "improved_high": j["eta_high"],
            "true_arrival": true_arrival,
            "baseline_error": abs(fixed_baseline_eta - true_arrival),
            "improved_error": abs(improved_mid - true_arrival),
        })

    avg_baseline_error = round(sum(baseline_errors) / len(baseline_errors), 1) if baseline_errors else 0
    avg_improved_error = round(sum(improved_errors) / len(improved_errors), 1) if improved_errors else 0
    error_reduction_pct = (
        round((avg_baseline_error - avg_improved_error) / avg_baseline_error * 100, 1)
        if avg_baseline_error > 0 else 0
    )
    enquiry_reduction_pct = error_reduction_pct

    return render_template(
        "baseline.html", rows=rows,
        avg_baseline_error=avg_baseline_error, avg_improved_error=avg_improved_error,
        error_reduction_pct=error_reduction_pct, enquiry_reduction_pct=enquiry_reduction_pct,
        fixed_baseline_eta=fixed_baseline_eta,
    )


@app.route("/analytics")
def analytics():
    conn = get_db()
    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    total_techs = conn.execute("SELECT COUNT(*) FROM technicians").fetchone()[0]
    total_logs = conn.execute("SELECT COUNT(*) FROM eta_history").fetchone()[0]

    status_data = dict(conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall())
    traffic_data = dict(conn.execute("SELECT COALESCE(traffic_level, 'N/A'), COUNT(*) FROM jobs WHERE traffic_level IS NOT NULL GROUP BY traffic_level").fetchall())
    skill_data = dict(conn.execute("SELECT required_skill, COUNT(*) FROM jobs GROUP BY required_skill").fetchall())

    avg_range = conn.execute("SELECT AVG(eta_high - eta_low) FROM jobs WHERE eta_low IS NOT NULL").fetchone()[0]
    avg_range_val = round(avg_range, 1) if avg_range else 0

    all_eta_jobs = conn.execute("SELECT eta_low, eta_high FROM jobs WHERE eta_low IS NOT NULL").fetchall()
    conn.close()

    rng = random.Random(42)
    b_errs, i_errs = [], []
    fixed_baseline = 35
    for j in all_eta_jobs:
        mid = (j["eta_low"] + j["eta_high"]) // 2
        true_arr = max(5, mid + rng.randint(-4, 4))
        b_errs.append(abs(fixed_baseline - true_arr))
        i_errs.append(abs(mid - true_arr))

    avg_b = round(sum(b_errs) / len(b_errs), 1) if b_errs else 0
    avg_i = round(sum(i_errs) / len(i_errs), 1) if i_errs else 0
    error_reduction = round((avg_b - avg_i) / avg_b * 100, 1) if avg_b > 0 else 0

    return render_template(
        "analytics.html",
        total_jobs=total_jobs,
        total_techs=total_techs,
        total_logs=total_logs,
        status_data=status_data,
        traffic_data=traffic_data,
        skill_data=skill_data,
        avg_range_val=avg_range_val,
        avg_b=avg_b,
        avg_i=avg_i,
        error_reduction=error_reduction,
    )


@app.route("/presentation")
def presentation():
    return render_template("presentation.html")


def find_available_port(host, default_port):
    import socket
    for p in [default_port, 5001, 5050, 8000, 8080]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    return default_port


if __name__ == "__main__":
    init_db()
    print(">> Database initialised with fresh sample data at", DB_PATH)
    host = os.environ.get("HOST", "0.0.0.0")
    req_port = int(os.environ.get("PORT", 5000))
    port = find_available_port(host, req_port)
    if port != req_port:
        print(f">> Notice: Port {req_port} is in use (e.g. macOS AirPlay). Running on http://127.0.0.1:{port} instead.")
    else:
        print(f">> Running on http://127.0.0.1:{port}")
    app.run(debug=True, host=host, port=port)
else:
    init_db()

