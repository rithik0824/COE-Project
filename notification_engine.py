"""
notification_engine.py
----------------------
Customer-facing notification and communication channel simulation.

Dispatches realistic simulated multi-channel notifications (SMS, Email, Push)
to customers whenever:
1. A technician is assigned / reassigned.
2. ETA ranges change due to traffic conditions or job delays.
3. Technician status updates (e.g. En Route, Arrived).
4. Jobs are completed.
5. Manual dispatcher outreach.

All notifications are persisted to the SQLite `customer_notifications` table
with real timestamps, delivery status receipts, and channel identifiers.
"""

from datetime import datetime


def log_notification(conn, job_id, channel, recipient, title, message, trigger_event="manual", status="Delivered"):
    """Inserts a customer-facing notification into the database."""
    cur = conn.execute(
        """INSERT INTO customer_notifications
           (job_id, channel, recipient, title, message, status, trigger_event, sent_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job_id,
            channel.upper(),
            recipient,
            title,
            message,
            status,
            trigger_event,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    return cur.lastrowid


def notify_assignment(conn, job_id, tech_name, eta_low, eta_high, reason, customer_name="Customer", customer_phone="+91 98400 12345"):
    """Dispatches initial assignment notifications across SMS and Push."""
    track_url = f"/track/{job_id}"
    
    # SMS Dispatch
    sms_msg = (
        f"Fieldline: Hi {customer_name}, technician {tech_name} has been assigned to your booking! "
        f"Honest ETA: {eta_low}–{eta_high} mins ({reason}). "
        f"Track live: {track_url}"
    )
    log_notification(
        conn, job_id, "SMS", customer_phone,
        "Technician Assigned & Live ETA", sms_msg,
        trigger_event="auto_assign"
    )

    # Push Notification
    push_msg = f"Tech {tech_name} is scheduled to arrive in {eta_low}–{eta_high} min."
    log_notification(
        conn, job_id, "Push", customer_name,
        "Technician En Route Window", push_msg,
        trigger_event="auto_assign"
    )

    # Email Dispatch (Booking Confirmation)
    email_msg = (
        f"Hello {customer_name},\n\n"
        f"Your service request has been confirmed. Technician {tech_name} is on schedule.\n"
        f"Estimated Arrival Window: {eta_low} to {eta_high} minutes from now.\n"
        f"Traffic / Route Status: {reason}.\n\n"
        f"You can view real-time arrival estimates and technician status at: {track_url}\n\n"
        f"Thank you for choosing Fieldline Services."
    )
    log_notification(
        conn, job_id, "Email", f"{customer_name.lower().replace(' ', '.')}@example.com",
        f"Fieldline Service Confirmation — Booking #{job_id}", email_msg,
        trigger_event="auto_assign"
    )


def notify_eta_update(conn, job_id, eta_low, eta_high, reason, trigger_event="eta_update", tech_name=None, customer_name="Customer", customer_phone="+91 98400 12345"):
    """Dispatches ETA change alerts when traffic, delays, or resimulation occurs."""
    tech_str = f"with {tech_name} " if tech_name else ""
    track_url = f"/track/{job_id}"

    # SMS Alert
    sms_msg = (
        f"Fieldline Alert: Your ETA window {tech_str}has been updated to {eta_low}–{eta_high} mins. "
        f"Reason: {reason}. Track: {track_url}"
    )
    log_notification(
        conn, job_id, "SMS", customer_phone,
        "Live ETA Window Updated", sms_msg,
        trigger_event=trigger_event
    )

    # Push Alert
    push_msg = f"Updated ETA: {eta_low}–{eta_high} mins ({reason})."
    log_notification(
        conn, job_id, "Push", customer_name,
        "ETA Revised", push_msg,
        trigger_event=trigger_event
    )


def notify_reassignment(conn, job_id, tech_name, eta_low, eta_high, reason, customer_name="Customer", customer_phone="+91 98400 12345"):
    """Dispatches notification when dispatcher overrides or reassigns technician."""
    track_url = f"/track/{job_id}"
    sms_msg = (
        f"Fieldline Update: Technician {tech_name} has been reassigned to your job. "
        f"New arrival window: {eta_low}–{eta_high} mins. Reason: {reason}. Track: {track_url}"
    )
    log_notification(
        conn, job_id, "SMS", customer_phone,
        "Technician Reassigned", sms_msg,
        trigger_event="technician_override"
    )

    push_msg = f"Technician changed to {tech_name}. New ETA: {eta_low}–{eta_high} min."
    log_notification(
        conn, job_id, "Push", customer_name,
        "Technician Reassigned", push_msg,
        trigger_event="technician_override"
    )


def notify_completion(conn, job_id, tech_name=None, customer_name="Customer", customer_phone="+91 98400 12345"):
    """Dispatches service completion notification and customer feedback link."""
    tech_str = f" by {tech_name}" if tech_name else ""
    sms_msg = (
        f"Fieldline: Your service appointment has been completed{tech_str}! "
        f"Thank you for rating our live ETA transparency. Have a great day!"
    )
    log_notification(
        conn, job_id, "SMS", customer_phone,
        "Service Completed", sms_msg,
        trigger_event="job_completed"
    )

    push_msg = f"Service marked complete{tech_str}. Thank you!"
    log_notification(
        conn, job_id, "Push", customer_name,
        "Service Completed", push_msg,
        trigger_event="job_completed"
    )
