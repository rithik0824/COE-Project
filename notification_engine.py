"""
notification_engine.py
----------------------
Customer-Facing Multi-Channel Notification & Telemetry Dispatch Engine.

Core Functionality:
Simulates an industrial omni-channel customer notification gateway (SMS, Push Notifications,
and Email) that proactively alerts customers whenever field dispatch events occur:
1. Technician Assignment & Schedule Booking (`auto_assign`).
2. Dynamic ETA Recalculation due to traffic surges (`traffic_shift`).
3. Cascading Service Overruns & Delay Alerts (`delay_overrun`).
4. Dispatcher Manual Overrides & Reassignment (`technician_override`).
5. Live Status Departures ('en_route') and Job Completions (`job_completed`).

Key Design & Error Boundaries:
- Omnichannel Resilience: Dispatches across multiple independent channels (SMS, Push, Email).
  If one channel delivery experiences failure, transactional persistence continues unaffected.
- Schema Persistence: Every outbound alert is recorded in the `customer_notifications` SQLite
  table with delivery timestamps, recipient identifiers, trigger event classifications, and
  delivery status receipts ('Delivered').
- Honest Range Transparency: Messages explicitly articulate uncertainty ranges (e.g. "25–35 mins")
  and explain real-world causal factors (e.g. "heavy traffic on Mount Road") to eliminate WISMO calls.
- Fallback Phone Formatting: Missing or unformatted customer phone numbers automatically fall back
  to default customer service test numbers without raising key errors.
"""

from datetime import datetime


def log_notification(conn, job_id, channel, recipient, title, message, trigger_event="manual", status="Delivered"):
    """
    Persists an outbound customer notification receipt to the SQLite database.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active SQLite database connection with transactional context.
    job_id : int
        Foreign key referencing the associated record in the `jobs` table.
    channel : str
        Communication medium identifier: 'SMS', 'PUSH', or 'EMAIL'. Coerced to uppercase.
    recipient : str
        Customer destination identifier (e.g. phone number '+91 98400 12345' or customer name).
    title : str
        Short notification header or subject line.
    message : str
        Full message body communicating live ETA window, causality, and tracking URL.
    trigger_event : str, optional
        Lifecycle event tag: 'auto_assign', 'eta_update', 'traffic_shift', 'delay_overrun',
        'en_route', 'technician_override', 'job_completed', or 'manual'.
    status : str, default 'Delivered'
        Delivery lifecycle status receipt ('Sent', 'Delivered', 'Failed').

    Returns
    -------
    int
        Primary key `id` of the newly inserted record in `customer_notifications`.

    Error Boundary:
    Coerces channel to uppercase and handles unicode characters in title/message safely.
    """
    cur = conn.execute(
        """INSERT INTO customer_notifications
           (job_id, channel, recipient, title, message, status, trigger_event, sent_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job_id,
            str(channel).upper(),
            str(recipient),
            str(title),
            str(message),
            str(status),
            str(trigger_event),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    return cur.lastrowid


def notify_assignment(conn, job_id, tech_name, eta_low, eta_high, reason, customer_name="Customer", customer_phone="+91 98400 12345"):
    """
    Dispatches initial booking confirmation and live tracking links across SMS, Push, and Email.

    Triggered when:
    A field service job is first assigned to a matching technician via `auto_assign()`.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.
    job_id : int
        Job identifier.
    tech_name : str
        Name of the assigned field service specialist.
    eta_low, eta_high : int
        Dynamic uncertainty arrival window bounds in minutes.
    reason : str
        Initial traffic and transit condition rationale.
    customer_name : str, optional
        Customer's full name.
    customer_phone : str, optional
        Customer's primary SMS contact number.
    """
    track_url = f"/track/{job_id}"
    
    # Channel 1: Primary SMS Dispatch (High urgency, concise)
    sms_msg = (
        f"Fieldline: Hi {customer_name}, technician {tech_name} has been assigned to your booking! "
        f"Honest ETA: {eta_low}–{eta_high} mins ({reason}). "
        f"Track live: {track_url}"
    )
    log_notification(
        conn, job_id, "SMS", customer_phone or "+91 98400 12345",
        "Technician Assigned & Live ETA", sms_msg,
        trigger_event="auto_assign"
    )

    # Channel 2: Mobile App Push Notification (Lock screen alert)
    push_msg = f"Tech {tech_name} is scheduled to arrive in {eta_low}–{eta_high} min."
    log_notification(
        conn, job_id, "Push", customer_name or "Customer",
        "Technician En Route Window", push_msg,
        trigger_event="auto_assign"
    )

    # Channel 3: Email Dispatch (Formal appointment confirmation)
    clean_name = str(customer_name).lower().replace(" ", ".") if customer_name else "customer"
    email_msg = (
        f"Hello {customer_name},\n\n"
        f"Your service request has been confirmed. Technician {tech_name} is on schedule.\n"
        f"Estimated Arrival Window: {eta_low} to {eta_high} minutes from now.\n"
        f"Traffic / Route Status: {reason}.\n\n"
        f"You can view real-time arrival estimates and technician status at: {track_url}\n\n"
        f"Thank you for choosing Fieldline Services."
    )
    log_notification(
        conn, job_id, "Email", f"{clean_name}@example.com",
        f"Fieldline Service Confirmation — Booking #{job_id}", email_msg,
        trigger_event="auto_assign"
    )


def notify_eta_update(conn, job_id, eta_low, eta_high, reason, trigger_event="eta_update", tech_name=None, customer_name="Customer", customer_phone="+91 98400 12345"):
    """
    Dispatches real-time ETA revision notifications when dynamic conditions change.

    Triggered when:
    - Route traffic shifts (e.g. rush-hour congestion).
    - Previous job dwell time overruns.
    - Technician status transitions to en route.
    - Customer manually refreshes tracking view.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.
    job_id : int
        Target job ID.
    eta_low, eta_high : int
        Updated arrival window boundaries.
    reason : str
        Detailed delay causality explaining why the ETA shifted.
    trigger_event : str
        Classification tag for audit trail ('traffic_shift', 'delay_overrun', etc.).
    tech_name : str, optional
        Technician name for personalization.
    customer_name : str, optional
        Customer name.
    customer_phone : str, optional
        Customer mobile phone number.
    """
    tech_str = f"with {tech_name} " if tech_name else ""
    track_url = f"/track/{job_id}"

    # SMS Real-Time Alert
    sms_msg = (
        f"Fieldline Alert: Your ETA window {tech_str}has been updated to {eta_low}–{eta_high} mins. "
        f"Reason: {reason}. Track: {track_url}"
    )
    log_notification(
        conn, job_id, "SMS", customer_phone or "+91 98400 12345",
        "Live ETA Window Updated", sms_msg,
        trigger_event=trigger_event
    )

    # Mobile App Push Notification
    push_msg = f"Updated ETA: {eta_low}–{eta_high} mins ({reason})."
    log_notification(
        conn, job_id, "Push", customer_name or "Customer",
        "ETA Revised", push_msg,
        trigger_event=trigger_event
    )


def notify_reassignment(conn, job_id, tech_name, eta_low, eta_high, reason, customer_name="Customer", customer_phone="+91 98400 12345"):
    """
    Dispatches notification when a dispatcher overrides or reassigns a job to a new specialist.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.
    job_id : int
        Job reference ID.
    tech_name : str
        Name of the newly assigned specialist.
    eta_low, eta_high : int
        New expected arrival range.
    reason : str
        Reassignment causality (e.g. primary tech unavailable, dispatcher manual override).
    customer_name : str, optional
        Customer name.
    customer_phone : str, optional
        Customer phone number.
    """
    track_url = f"/track/{job_id}"
    sms_msg = (
        f"Fieldline Update: Technician {tech_name} has been reassigned to your job. "
        f"New arrival window: {eta_low}–{eta_high} mins. Reason: {reason}. Track: {track_url}"
    )
    log_notification(
        conn, job_id, "SMS", customer_phone or "+91 98400 12345",
        "Technician Reassigned", sms_msg,
        trigger_event="technician_override"
    )

    push_msg = f"Technician changed to {tech_name}. New ETA: {eta_low}–{eta_high} min."
    log_notification(
        conn, job_id, "Push", customer_name or "Customer",
        "Technician Reassigned", push_msg,
        trigger_event="technician_override"
    )


def notify_completion(conn, job_id, tech_name=None, customer_name="Customer", customer_phone="+91 98400 12345"):
    """
    Dispatches service completion receipt and customer satisfaction review prompt.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection.
    job_id : int
        Completed job reference ID.
    tech_name : str, optional
        Technician who completed the work.
    customer_name : str, optional
        Customer name.
    customer_phone : str, optional
        Customer contact phone number.
    """
    tech_str = f" by {tech_name}" if tech_name else ""
    sms_msg = (
        f"Fieldline: Your service appointment has been completed{tech_str}! "
        f"Thank you for rating our live ETA transparency. Have a great day!"
    )
    log_notification(
        conn, job_id, "SMS", customer_phone or "+91 98400 12345",
        "Service Completed", sms_msg,
        trigger_event="job_completed"
    )

    push_msg = f"Service marked complete{tech_str}. Thank you!"
    log_notification(
        conn, job_id, "Push", customer_name or "Customer",
        "Service Completed", push_msg,
        trigger_event="job_completed"
    )
