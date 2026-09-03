"""
eta_engine.py
--------------
Fully simulated ETA calculation engine.

No external APIs (no Google Maps, no traffic APIs) are used anywhere in this
project. Distance is computed with the haversine formula on simulated
latitude/longitude coordinates. Traffic and service delays are simulated
using time-of-day rules and randomised (but bounded) conditions, so the
whole system runs offline on a local laptop.
"""

import random
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

# ---------------------------------------------------------------------------
# Simulated city grid (used only to keep generated coordinates realistic)
# ---------------------------------------------------------------------------
CITY_LAT_RANGE = (12.90, 13.15)
CITY_LNG_RANGE = (80.10, 80.30)

BASE_SPEED_KMH = 24          # average simulated city driving speed
PREP_BUFFER_MIN = 5          # fixed prep/parking buffer added to every job

TRAFFIC_MULTIPLIER = {
    "light": 1.0,
    "moderate": 1.3,
    "heavy": 1.7,
}


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two simulated coordinates, in km."""
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def get_traffic_level(appointment_time_str, rng=None):
    """
    Simulates a traffic condition based on the hour of the appointment.
    Rush hours (8-10, 17-19) are weighted towards heavier traffic.
    """
    rng = rng or random
    try:
        hour = datetime.strptime(appointment_time_str, "%Y-%m-%dT%H:%M").hour
    except (ValueError, TypeError):
        hour = datetime.now().hour

    if hour in (8, 9, 17, 18, 19):
        return rng.choice(["heavy", "heavy", "moderate"])
    elif hour in (12, 13, 14):
        return rng.choice(["moderate", "light", "moderate"])
    else:
        return rng.choice(["light", "light", "moderate"])


def calculate_eta(technician, job_row, previous_job_delay=False, rng=None, forced_traffic=None):
    """
    Calculates a realistic ETA *range* (not a false-precision single number)
    for a technician travelling to a job.

    Parameters
    ----------
    technician : sqlite3.Row / dict with latitude, longitude
    job_row    : sqlite3.Row / dict with customer_latitude, customer_longitude,
                 appointment_time
    previous_job_delay : bool - simulate the technician's previous job
                 overrunning (edge case: "service taking longer than expected")
    forced_traffic : optional "light"|"moderate"|"heavy" to force a specific
                 traffic condition (used to make the 4 demo scenarios
                 reproducible on every app start instead of random).

    Returns
    -------
    dict with eta_low, eta_high, traffic_level, reason, distance_km
    """
    rng = rng or random

    distance_km = haversine_km(
        technician["latitude"], technician["longitude"],
        job_row["customer_latitude"], job_row["customer_longitude"],
    )

    travel_minutes = (distance_km / BASE_SPEED_KMH) * 60

    traffic_level = forced_traffic or get_traffic_level(job_row["appointment_time"], rng)
    travel_minutes *= TRAFFIC_MULTIPLIER[traffic_level]

    reasons = []
    if traffic_level == "heavy":
        reasons.append("heavy traffic on the route")
    elif traffic_level == "moderate":
        reasons.append("moderate traffic")

    delay_minutes = 0
    if previous_job_delay:
        delay_minutes = rng.randint(12, 28)
        reasons.append("previous job running longer than expected")

    total_minutes = travel_minutes + delay_minutes + PREP_BUFFER_MIN

    # Uncertainty band width grows with traffic and delay risk - this is what
    # drives an honest "30-45 minutes" style range instead of false precision.
    uncertainty = 10
    if traffic_level == "heavy":
        uncertainty += 8
    if traffic_level == "moderate":
        uncertainty += 4
    if delay_minutes > 0:
        uncertainty += 10

    eta_low = max(5, round(total_minutes - uncertainty / 2))
    eta_high = round(total_minutes + uncertainty / 2)

    reason_text = "; ".join(reasons) if reasons else "normal traffic conditions"

    return {
        "eta_low": int(eta_low),
        "eta_high": int(eta_high),
        "traffic_level": traffic_level,
        "reason": reason_text,
        "distance_km": round(distance_km, 2),
    }


def random_coordinate(rng=None):
    rng = rng or random
    lat = round(rng.uniform(*CITY_LAT_RANGE), 4)
    lng = round(rng.uniform(*CITY_LNG_RANGE), 4)
    return lat, lng
