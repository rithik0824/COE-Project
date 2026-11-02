"""
eta_engine.py
--------------
Autonomous Simulated ETA Calculation & Uncertainty Quantification Engine.

Core Mathematical Principles:
1. Haversine Great-Circle Distance Formulation:
   Computes orthodromic distance across the spherical Earth model (WGS-84 mean radius R = 6,371.0 km)
   without requiring external geospatial routing APIs or network dependencies.
   Formula:
       a = sin^2(Δφ / 2) + cos(φ1) * cos(φ2) * sin^2(Δλ / 2)
       c = 2 * atan2(sqrt(a), sqrt(1 - a))
       d = R * c

2. Dynamic Uncertainty Band Model:
   Rejects false single-point precision (e.g. "10:15 AM") in favor of an honest, bounded
   arrival interval [eta_low, eta_high]. The interval width dynamically scales with:
       - Baseline transit variance (W0 = 10 min)
       - Traffic condition penalty (+4 min for moderate, +8 min for heavy)
       - Cascading dwell-time overrun risk (+10 min)

3. Invariant Enforcement:
   - Non-negativity and lower clamp: eta_low >= 5 minutes (prep and parking buffer).
   - Interval ordering: eta_low <= eta_high.
   - Explainability: Generates human-readable causal delay text accompanying each update.
"""

import random
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

# ---------------------------------------------------------------------------
# Simulated Coordinate Bounds (Chennai Metropolitan Area Grid)
# ---------------------------------------------------------------------------
# Kept within realistic geographical bounds of Chennai urban clusters
CITY_LAT_RANGE = (12.90, 13.15)
CITY_LNG_RANGE = (80.10, 80.30)

# Simulated nominal urban driving velocity in congested city streets
BASE_SPEED_KMH = 24.0

# Fixed dispatch preparation, vehicle ingress, and customer site parking buffer
PREP_BUFFER_MIN = 5

# Empirically calibrated transit multipliers based on urban congestion indices
TRAFFIC_MULTIPLIER = {
    "light": 1.0,      # Off-peak midday / late evening free flow
    "moderate": 1.3,   # Normal daytime arterial congestion (+30% travel time)
    "heavy": 1.7,      # Peak morning/evening rush hour (+70% travel time)
}


def haversine_km(lat1, lng1, lat2, lng2):
    """
    Computes great-circle distance between two geographic coordinates in kilometers.

    Parameters
    ----------
    lat1, lng1 : float
        Latitude and longitude of technician / vehicle origin in decimal degrees.
    lat2, lng2 : float
        Latitude and longitude of customer appointment destination in decimal degrees.

    Returns
    -------
    float
        Great-circle distance in kilometers (>= 0.0).

    Error Boundary & Invariants:
    - If origin and destination are identical, returns exactly 0.0.
    - Handles extreme coordinates across opposite hemispheres without trigonometric domain error.
    """
    if lat1 == lat2 and lng1 == lng2:
        return 0.0

    r = 6371.0  # Mean volumetric radius of the Earth in km
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    
    # Haversine formula formulation
    a = sin(dlat / 2.0) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2.0) ** 2
    
    # Numerical stability clamp: prevent domain error in sqrt if a slightly exceeds 1.0
    a = min(1.0, max(0.0, a))
    c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a))
    return r * c


def get_traffic_level(appointment_time_str, rng=None):
    """
    Evaluates probabilistic traffic congestion based on scheduled appointment time.

    Temporal Distribution Rules:
    - Morning Rush (08:00 - 10:59): Skewed towards 'heavy' (67%) and 'moderate' (33%).
    - Evening Rush (17:00 - 19:59): Skewed towards 'heavy' (67%) and 'moderate' (33%).
    - Lunch Peak (12:00 - 14:59): Skewed towards 'moderate' (67%) and 'light' (33%).
    - Off-Peak: Predominantly 'light' (67%) with occasional 'moderate' (33%).

    Parameters
    ----------
    appointment_time_str : str or None
        ISO formatted datetime string ('YYYY-MM-DDTHH:MM') or timestamp.
    rng : random.Random, optional
        Seeded pseudo-random number generator for deterministic benchmarking.

    Returns
    -------
    str
        One of 'light', 'moderate', or 'heavy'.

    Error Boundary:
    If appointment_time_str is corrupt, None, or unparseable, falls back safely to
    the current local system hour without raising an uncaught exception.
    """
    rng = rng or random
    try:
        if appointment_time_str:
            hour = datetime.strptime(str(appointment_time_str), "%Y-%m-%dT%H:%M").hour
        else:
            hour = datetime.now().hour
    except (ValueError, TypeError):
        hour = datetime.now().hour

    if hour in (8, 9, 10, 17, 18, 19):
        return rng.choice(["heavy", "heavy", "moderate"])
    elif hour in (12, 13, 14):
        return rng.choice(["moderate", "light", "moderate"])
    else:
        return rng.choice(["light", "light", "moderate"])


def calculate_eta(technician, job_row, previous_job_delay=False, rng=None, forced_traffic=None):
    """
    Computes a realistic, dynamic arrival uncertainty interval [eta_low, eta_high]
    and causal explanation text for an assigned field technician.

    Mathematical Workflow:
    1. Distance: d = haversine_km(tech_coords, customer_coords)
    2. Nominal Travel Duration: T_nom = (d / BASE_SPEED_KMH) * 60 minutes
    3. Traffic Scaling: T_traffic = T_nom * TRAFFIC_MULTIPLIER[tier]
    4. Service Overrun Delay: Adds D_overrun ∈ [12, 28] minutes if prior job dwell exceeded SLA.
    5. Preparation Buffer: Adds fixed 5 minutes for vehicle parking and tool preparation.
    6. Uncertainty Window: Width W = W0 + ΔW_traffic + ΔW_overrun.
    7. Clamping: eta_low = max(5, round(T_total - W/2)), eta_high = round(T_total + W/2).

    Parameters
    ----------
    technician : sqlite3.Row or dict
        Record containing 'latitude' and 'longitude' coordinates.
    job_row : sqlite3.Row or dict
        Record containing 'customer_latitude', 'customer_longitude', and 'appointment_time'.
    previous_job_delay : bool, default False
        Simulates preceding customer site dwell overrun (Edge Case 3).
    rng : random.Random, optional
        Seeded pseudo-random generator for reproducible simulations.
    forced_traffic : str, optional ('light', 'moderate', 'heavy')
        Forces specific traffic state to guarantee deterministic demo scenarios.

    Returns
    -------
    dict
        {
            'eta_low': int (minimum expected arrival minutes),
            'eta_high': int (maximum expected arrival minutes),
            'traffic_level': str ('light' | 'moderate' | 'heavy'),
            'reason': str (natural-language explanation of delay causality),
            'distance_km': float (calculated great-circle distance)
        }

    Error Boundary & Invariants:
    - Guaranteed: eta_low <= eta_high.
    - Guaranteed: eta_low >= 5 minutes (prep buffer).
    - Unrecognized traffic tier gracefully falls back to 'moderate'.
    """
    rng = rng or random

    # Step 1: Great-circle distance computation
    distance_km = haversine_km(
        float(technician["latitude"]), float(technician["longitude"]),
        float(job_row["customer_latitude"]), float(job_row["customer_longitude"]),
    )

    # Step 2: Uncongested driving minutes
    travel_minutes = (distance_km / BASE_SPEED_KMH) * 60.0

    # Step 3: Traffic assessment and scaling
    appt_time = None
    try:
        appt_time = job_row["appointment_time"]
    except (KeyError, IndexError, TypeError):
        pass
    traffic_level = forced_traffic or get_traffic_level(appt_time, rng)
    # Fallback to moderate if unknown traffic key supplied
    multiplier = TRAFFIC_MULTIPLIER.get(traffic_level, 1.3)
    travel_minutes *= multiplier

    reasons = []
    if traffic_level == "heavy":
        reasons.append("heavy traffic on the route")
    elif traffic_level == "moderate":
        reasons.append("moderate traffic")

    # Step 4: Dwell-time overrun simulation (Edge Case 3)
    delay_minutes = 0
    if previous_job_delay:
        delay_minutes = rng.randint(12, 28)
        reasons.append("previous job running longer than expected")

    # Step 5: Total expected transit minutes
    total_minutes = travel_minutes + delay_minutes + PREP_BUFFER_MIN

    # Step 6: Dynamic uncertainty interval width expansion
    uncertainty_width = 10
    if traffic_level == "heavy":
        uncertainty_width += 8
    elif traffic_level == "moderate":
        uncertainty_width += 4
    if delay_minutes > 0:
        uncertainty_width += 10

    # Step 7: Lower and upper bound clamping
    eta_low = max(5, round(total_minutes - uncertainty_width / 2.0))
    eta_high = max(eta_low, round(total_minutes + uncertainty_width / 2.0))

    reason_text = "; ".join(reasons) if reasons else "normal traffic conditions"

    return {
        "eta_low": int(eta_low),
        "eta_high": int(eta_high),
        "traffic_level": traffic_level,
        "reason": reason_text,
        "distance_km": round(distance_km, 2),
    }


def random_coordinate(rng=None):
    """
    Generates a realistic simulated coordinate strictly within the metropolitan boundary grid.

    Parameters
    ----------
    rng : random.Random, optional
        Seeded pseudo-random number generator.

    Returns
    -------
    tuple of (float, float)
        (latitude, longitude) rounded to 4 decimal places (~11 meters precision).
    """
    rng = rng or random
    lat = round(rng.uniform(*CITY_LAT_RANGE), 4)
    lng = round(rng.uniform(*CITY_LNG_RANGE), 4)
    return lat, lng
