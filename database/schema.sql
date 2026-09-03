-- Schema for Live ETA Communication and Technician Assignment System
-- SQLite database, recreated fresh every time the app starts (see app.py -> init_db).

DROP TABLE IF EXISTS eta_history;
DROP TABLE IF EXISTS assignment_history;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS technicians;

CREATE TABLE technicians (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    skills        TEXT NOT NULL,                 -- comma-separated list, e.g. "AC Repair,Electrical"
    availability  TEXT NOT NULL DEFAULT 'available', -- available | busy | unavailable
    latitude      REAL NOT NULL,
    longitude     REAL NOT NULL
);

CREATE TABLE jobs (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name           TEXT NOT NULL,
    required_skill          TEXT NOT NULL,
    customer_latitude       REAL NOT NULL,
    customer_longitude      REAL NOT NULL,
    appointment_time        TEXT NOT NULL,        -- "YYYY-MM-DDTHH:MM"
    status                  TEXT NOT NULL DEFAULT 'pending', -- pending|assigned|unassigned|completed
    assigned_technician_id  INTEGER,
    eta_low                 INTEGER,
    eta_high                INTEGER,
    traffic_level           TEXT,
    delay_reason            TEXT,
    demo_case               TEXT,                 -- tags one of the 4 required demo edge cases, else NULL
    created_at              TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_technician_id) REFERENCES technicians(id)
);

CREATE TABLE eta_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      INTEGER NOT NULL,
    eta_low     INTEGER,
    eta_high    INTEGER,
    reason      TEXT,
    changed_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE TABLE assignment_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL,
    technician_id   INTEGER,
    action          TEXT NOT NULL,     -- auto_assigned | manual_override | unassigned | completed
    reason          TEXT,
    changed_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (technician_id) REFERENCES technicians(id)
);
