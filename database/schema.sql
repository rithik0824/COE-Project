-- ============================================================================
-- LIVE ETA COMMUNICATION & TECHNICIAN ASSIGNMENT SYSTEM
-- Relational Database Schema (SQLite 3.x with Foreign Keys Enabled)
-- ============================================================================
-- 
-- Architecture Notes:
-- 1. Foreign Key Enforcement: Requires 'PRAGMA foreign_keys = ON' upon connection.
-- 2. Clean State Recreation: Recreated fresh on system startup via app.py -> init_db().
-- 3. Auditability: Maintains historical audit trails for both ETA recalculations (eta_history)
--    and dispatch assignment decisions (assignment_history).
-- 4. Multi-Channel Ingestion: Outbound customer notifications across SMS, Push, and Email
--    are fully logged in customer_notifications with delivery timestamps and triggers.
-- 5. Stakeholder Feedback: Captures pilot user survey scores and qualitative interview logs.
-- ============================================================================

DROP TABLE IF EXISTS customer_notifications;
DROP TABLE IF EXISTS stakeholder_feedback;
DROP TABLE IF EXISTS eta_history;
DROP TABLE IF EXISTS assignment_history;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS technicians;

-- ----------------------------------------------------------------------------
-- Table 1: technicians
-- Represents field workforce agents, skill qualifications, active availability,
-- and live simulated GPS telematics.
-- ----------------------------------------------------------------------------
CREATE TABLE technicians (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,                        -- Full name of field service technician
    skills        TEXT NOT NULL,                        -- Comma-separated list of certified skills (e.g. "AC Repair,Electrical")
    availability  TEXT NOT NULL DEFAULT 'available',    -- Current status: 'available' | 'busy' | 'unavailable'
    latitude      REAL NOT NULL,                        -- Simulated vehicle latitude in decimal degrees (WGS-84)
    longitude     REAL NOT NULL                         -- Simulated vehicle longitude in decimal degrees (WGS-84)
);

-- ----------------------------------------------------------------------------
-- Table 2: jobs
-- Represents customer service orders, required trade skill, delivery coordinates,
-- assigned technician, dynamic uncertainty bounds, and current lifecycle state.
-- ----------------------------------------------------------------------------
CREATE TABLE jobs (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name           TEXT NOT NULL,              -- Full name of customer receiving the service
    customer_phone          TEXT DEFAULT '+91 98400 12345', -- Primary mobile phone number for SMS tracking links
    required_skill          TEXT NOT NULL,              -- Required service skill (e.g. "AC Repair", "Plumbing")
    customer_latitude       REAL NOT NULL,              -- Service delivery address latitude (WGS-84)
    customer_longitude      REAL NOT NULL,              -- Service delivery address longitude (WGS-84)
    appointment_time        TEXT NOT NULL,              -- Scheduled appointment timestamp ("YYYY-MM-DDTHH:MM")
    status                  TEXT NOT NULL DEFAULT 'pending', -- Lifecycle status: 'pending' | 'assigned' | 'en_route' | 'unassigned' | 'completed'
    assigned_technician_id  INTEGER,                    -- Foreign key referencing technicians.id (NULL if unassigned)
    eta_low                 INTEGER,                    -- Lower bound of dynamic arrival window in minutes from now
    eta_high                INTEGER,                    -- Upper bound of dynamic arrival window in minutes from now
    traffic_level           TEXT,                       -- Active route traffic congestion: 'light' | 'moderate' | 'heavy'
    delay_reason            TEXT,                       -- Natural-language delay causality explaining why ETA shifted
    demo_case               TEXT,                       -- Tags one of 4 demo edge cases ('heavy_traffic', 'unavailable', 'service_overrun', 'skill_mismatch')
    created_at              TEXT DEFAULT CURRENT_TIMESTAMP, -- Job logging creation timestamp
    FOREIGN KEY (assigned_technician_id) REFERENCES technicians(id) ON DELETE SET NULL
);

-- ----------------------------------------------------------------------------
-- Table 3: eta_history
-- Immutable historical time-series ledger of all ETA recalculations per job.
-- Enables retroactive auditing of transit progression and uncertainty shifts.
-- ----------------------------------------------------------------------------
CREATE TABLE eta_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      INTEGER NOT NULL,                       -- Foreign key referencing jobs.id
    eta_low     INTEGER,                                -- Lower bound of arrival window at timestamp
    eta_high    INTEGER,                                -- Upper bound of arrival window at timestamp
    reason      TEXT,                                   -- Delay causality / trigger description (e.g. "traffic shifted to heavy")
    changed_at  TEXT DEFAULT CURRENT_TIMESTAMP,         -- Exact timestamp when the recalculation occurred
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- Table 4: assignment_history
-- Full audit trail for dispatch assignments, automated match decisions,
-- dispatcher manual overrides, skill mismatch warnings, and cancellations.
-- ----------------------------------------------------------------------------
CREATE TABLE assignment_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL,                   -- Foreign key referencing jobs.id
    technician_id   INTEGER,                            -- Foreign key referencing technicians.id (NULL if unassigned)
    action          TEXT NOT NULL,                      -- Action type: 'auto_assigned' | 'manual_override' | 'unassigned' | 'en_route' | 'completed'
    reason          TEXT,                               -- Human-readable rationale or policy override warning note
    changed_at      TEXT DEFAULT CURRENT_TIMESTAMP,     -- Timestamp of assignment event
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (technician_id) REFERENCES technicians(id) ON DELETE SET NULL
);

-- ----------------------------------------------------------------------------
-- Table 5: customer_notifications
-- Omni-channel communication log tracking all outbound simulated alerts
-- dispatched to customers via SMS, Push notifications, and Email receipts.
-- ----------------------------------------------------------------------------
CREATE TABLE customer_notifications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL,                   -- Foreign key referencing jobs.id
    channel         TEXT NOT NULL,                      -- Communication channel: 'SMS' | 'PUSH' | 'EMAIL'
    recipient       TEXT NOT NULL,                      -- Destination phone number, email address, or device identifier
    title           TEXT NOT NULL,                      -- Message header / notification subject
    message         TEXT NOT NULL,                      -- Message body including honest arrival range and tracking link
    status          TEXT NOT NULL DEFAULT 'Delivered',  -- Lifecycle delivery state: 'Sent' | 'Delivered' | 'Failed'
    sent_at         TEXT DEFAULT CURRENT_TIMESTAMP,     -- Exact dispatch timestamp
    trigger_event   TEXT NOT NULL,                      -- System event trigger: 'auto_assign' | 'eta_update' | 'traffic_shift' | 'delay_overrun' | 'manual' | 'job_completed'
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- Table 6: stakeholder_feedback
-- Captures empirical feedback collected from Dispatchers, Field Technicians,
-- End Customers, and Operations QA during the 2-week pilot evaluation study.
-- ----------------------------------------------------------------------------
CREATE TABLE stakeholder_feedback (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    stakeholder_name      TEXT NOT NULL,                -- Name of evaluator / pilot participant
    role                  TEXT NOT NULL,                -- Persona: 'Dispatcher' | 'Field Technician' | 'Customer' | 'Operations Lead'
    organization_or_area  TEXT NOT NULL,                -- Geographic operational zone or company division
    rating                INTEGER NOT NULL,             -- Quantitative Likert rating score (1 to 5 stars)
    category              TEXT NOT NULL,                -- Evaluation category: 'ETA Accuracy' | 'Dispatch Workload' | 'Customer Trust' | 'System Reliability'
    feedback_text         TEXT NOT NULL,                -- Qualitative review transcript and feedback commentary
    created_at            TEXT DEFAULT CURRENT_TIMESTAMP -- Submission timestamp
);

-- ----------------------------------------------------------------------------
-- Suggested Indexes for Production Query Optimization
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_assigned_tech ON jobs(assigned_technician_id);
CREATE INDEX IF NOT EXISTS idx_eta_history_job_id ON eta_history(job_id);
CREATE INDEX IF NOT EXISTS idx_assignment_history_job_id ON assignment_history(job_id);
CREATE INDEX IF NOT EXISTS idx_notifications_job_id ON customer_notifications(job_id);
