# Live ETA Communication and Technician Assignment System

A college mini-project: a dispatcher console for a field-service company that assigns
technicians to jobs and communicates a **realistic, honest ETA range** instead of a
false, exact arrival time — with full traceability of every ETA and assignment change.

Everything runs **100% locally** with **no paid APIs, no Google Maps, no cloud
deployment, and no Docker**. All locations, traffic, routes and delays are simulated
in Python.

---

## 1. Tech stack

| Layer      | Technology                                   |
|------------|-----------------------------------------------|
| Backend    | Python 3 + Flask                              |
| Database   | SQLite (built into Python, no server needed)  |
| Frontend   | HTML, CSS, vanilla JavaScript                 |
| Styling    | Custom CSS + Bootstrap 5 CDN (layout helpers) |
| Charts     | Chart.js (CDN, free)                          |

No API keys are required anywhere in this project.

---

## 2. How to run it

### Option A: Run directly with Python (Local)
```bash
pip install -r requirements.txt
python app.py
```

### Option B: Run with Docker Compose (Recommended)
```bash
docker compose up --build
```

### Option C: Run with Docker CLI
```bash
# 1. Build the Docker image
docker build -t live-eta-system .

# 2. Run container on port 5000
docker run -p 5000:5000 --name live_eta_container live-eta-system
```

Then open **http://127.0.0.1:5000** in your browser.

The database (`database/eta_system.db`) is automatically recreated with
fresh sample data (**5,006 jobs, 200 technicians, 10,000+ history logs**)
**every time you start the app**, so you always get a clean, working demo.

---

## 3. Project structure

```
live_eta_technician_system/
│
├── app.py                     # Flask app: all routes & dispatch logic
├── eta_engine.py               # Simulated ETA calculation (distance, traffic, delay)
├── requirements.txt
├── README.md
│
├── database/
│   ├── schema.sql               # Table definitions
│   ├── seed_data.py              # Sample technicians/jobs + 4 demo edge cases
│   └── eta_system.db             # Generated automatically at runtime (git-ignored)
│
├── templates/
│   ├── base.html                 # Sidebar shell / layout
│   ├── dashboard.html            # Overview page with 5k+ benchmark banner
│   ├── jobs.html                 # Paginated Job board with search & filters
│   ├── job_detail.html           # Live ETA, override, full history
│   ├── technicians.html          # Roster + add-technician form
│   ├── demo.html                 # The 4 required edge-case demos
│   ├── baseline.html             # Baseline vs improved ETA comparison
│   ├── analytics.html            # 5,000+ dataset visual analytics dashboard
│   └── presentation.html         # Interactive slide deck (in-app presentation)
│
├── presentation.html             # Standalone openable presentation slide deck
└── static/
    ├── css/style.css              # Design system (dark dispatch-console theme)
    └── js/script.js               # Clock readout, row-click, confirm dialogs
```

---

## 4. Core features (mapped to requirements)

1. **Technician management** — name, skills (multi-select), availability, latitude/longitude.
   Manage from `/technicians`.
2. **Job management** — customer name, required skill, customer location, appointment time,
   status. Manage from `/jobs` (includes SQL pagination and search filters).
3. **5,000+ Record Dataset Benchmark** — `seed_data.py` populates **5,006 jobs**, **200 technicians**, and **10,000+ history logs** using fast SQLite batch operations to demonstrate scale and statistical accuracy.
4. **Interactive Presentation Deck** (`/presentation` or `presentation.html`) — In-browser slide deck with slide navigation, presenter speaker notes (Tamil & English), baseline error comparison, and viva Q&A guide.
5. **Analytics Visualizer** (`/analytics`) — Interactive Chart.js dashboard visualizing status breakdown, ETA error reduction (38.4%), traffic impact, and skill allocation across the 5,000+ dataset.
6. **Automatic assignment** — `auto_assign()` in `app.py` filters technicians by
   matching skill + `available` status, then picks the **nearest** one using the
   haversine distance formula on simulated coordinates.
7. **Simulated ETA calculation** — `eta_engine.calculate_eta()` combines simulated
   distance, a time-of-day traffic model (light/moderate/heavy), and an optional
   "previous job overran" delay to produce a total travel time.
8. **Realistic ETA range** — the engine always returns `eta_low`–`eta_high` (an
   uncertainty band that widens with traffic/delay risk), e.g. "30–45 minutes",
   never a single false-precision number.
9. **Delay reason shown** — every ETA is stored with a human-readable reason:
   heavy/moderate traffic, a previous job's delay, or a skill-mismatch override note.
10. **Dispatcher dashboard** (`/dashboard`, `/jobs`, `/technicians`, job detail page):
   view all jobs, view technicians + skills, view assigned technician & live ETA,
   and manually **override** the assigned technician from the job detail page.
11. **Full history** — every ETA change is logged in `eta_history`, and every
   assignment/override/completion is logged in `assignment_history`, each with a
   timestamp and reason. Shown as timelines on the job detail page.
12. **Four demo edge cases** (seeded automatically, see `/demo`):
   - Heavy traffic
   - Technician unavailable
   - Service/job taking longer than expected
   - Technician does not have the required skill (dispatcher override, flagged)
13. **Baseline vs improved comparison** (`/baseline`) — a fixed naive ETA vs the
    dynamic range across 5,000+ records (38.4% error reduction).
14. **UI** — a dark "dispatch console" design, responsive down to smaller screens,
    consistent status badges/colors, and a live clock readout for a "control room" feel.

---

## 5. How the ETA simulation works (no external APIs)

1. **Distance** — haversine formula between the technician's simulated
   lat/lng and the customer's simulated lat/lng.
2. **Base speed** — a fixed simulated city-driving speed (24 km/h) converts
   distance into a base travel time.
3. **Traffic** — `get_traffic_level()` picks light/moderate/heavy, weighted by
   the appointment's hour of day (rush hours skew heavier), and applies a
   multiplier to travel time.
4. **Delay** — if the assigned technician's previous job is simulated as
   overrunning, 12–28 extra minutes are added and noted as the reason.
5. **Uncertainty band** — the final range width grows with traffic level and
   delay risk, so the customer always sees an honest range instead of a
   falsely precise number.

---

## 6. Assumptions made for this project

- All coordinates are simulated points on a local city grid (no real map data).
- Traffic and delays are simulated with weighted randomness / fixed demo values,
  not a live traffic feed.
- The "baseline vs improved" comparison uses a simulated "true arrival time" and a
  simple assumption that customer status-check calls scale with ETA error — this is
  stated explicitly on the comparison page.
- The database is recreated from scratch on every app restart, which is intentional
  for a reproducible classroom/demo setting.

---

## 7. Run commands

```bash
pip install -r requirements.txt
python app.py
```
