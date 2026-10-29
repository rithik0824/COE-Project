# Failure-Mode Analysis & Robustness Assessment
## Live ETA Communication and Technician Assignment System

---

### Executive Summary
A critical requirement of field-service dispatch engineering is that the system must not fail catastrophically when confronted with real-world exceptions. Conventional dispatch platforms present brittle single-point estimates that crumble under traffic spikes, technician breakdowns, and unscheduled service overruns.

This document presents a rigorous **Failure-Mode and Effects Analysis (FMEA)** of the Live ETA Communication System, evaluating five realistic failure modes, contrasting the naive baseline behavior against the proposed dynamic architecture, and documenting **why the chosen approach is appropriate**.

---

## 1. Summary FMEA Risk Priority Matrix

| ID | Failure Mode | Severity | Probability | Baseline Impact | Proposed Mitigation | Risk Priority |
| :---: | :--- | :---: | :---: | :--- | :--- | :---: |
| **FM-01** | Peak-Hour Traffic Surge & Gridlock | High | High | Late arrival by 25+ min; zero notice; angry customer WISMO calls | Dynamic 1.7x multiplier + uncertainty band expands by +8 min; automated SMS alert | **Mitigated** |
| **FM-02** | Sudden Technician Unavailability / Breakdown | Critical | Medium | Zombie assignment; customer waits for a technician who will never arrive | Clean state transition; auto-reassignment to nearest free specialist or graceful unassign; audit log | **Mitigated** |
| **FM-03** | On-Site Dwell Time Overrun (Prior Job Delay) | High | High | Downstream appointments blindly missed; cascading customer rage | Cascading delay propagation (+12–28m); window widens (+10m); proactive customer SMS | **Mitigated** |
| **FM-04** | Specialist Skill Mismatch During Emergency | Medium | Low | Hard system refusal or unmonitored dangerous skill violation | Controlled Dispatcher Manual Override; warning flag; mandatory justification; immutable audit log | **Mitigated** |
| **FM-05** | GPS Telemetry Blackout / Dead Zones | Medium | Medium | False "zero distance" or application crash due to stale data | Fallback to time-of-day corridor velocity; window widens (+15m) to signal epistemic uncertainty | **Mitigated** |

---

## 2. In-Depth Failure Mode Analysis

### Failure Mode 1: Peak-Hour Route Congestion & Bottlenecks (FM-01)

#### 1. Real-World Industrial Context
Urban field technicians navigate arterial corridors subject to extreme stochastic congestion during peak commute hours (08:00–10:00 and 17:00–19:30). A 6-kilometer trip that takes 15 minutes at noon can require 45 minutes during evening gridlock.

#### 2. Detection Mechanism
- The system evaluates the appointment timestamp against calibrated time-of-day traffic distributions:
  ```python
  if hour in (8, 9, 17, 18, 19):
      return rng.choices(["heavy", "heavy", "moderate"])
  ```
- In real-time mode, dispatchers can trigger a city-wide or corridor traffic shift (`POST /events/traffic-shift`), instantly adjusting all active in-transit jobs.

#### 3. Naive Baseline vs. Proposed Dynamic Model
- **Naive Baseline**: Promises a fixed 35-minute arrival time regardless of road conditions. In heavy traffic, arrival takes 52 minutes. The 17-minute breach breaks customer trust and prompts customer support status inquiries.
- **Proposed Dynamic Model**:
  1. Applies a `1.7x` heavy traffic travel multiplier:
     $$\text{Travel Minutes} = \left(\frac{\text{Distance}}{24 \text{ km/h}} \times 60\right) \times 1.7$$
  2. Expands the uncertainty band by $+8\text{ minutes}$ (total width 18 minutes), shifting the promised window to **[42–60 minutes]**.
  3. Dispatches automated SMS and Push alerts:
     > *"Fieldline: Arun Kumar is on the way! Honest ETA: 42–60 mins (heavy traffic on route). Track: /track/1"*

#### 4. Why the Chosen Approach is Appropriate
Communicating an honest, wider window rather than an exact single timestamp respects the physics of urban transit. Customers are not inconvenienced by waiting if they know the true arrival window in advance; they are only angered by false certainty that is subsequently breached.

---

### Failure Mode 2: Sudden Technician Unavailability / In-Field Breakdown (FM-02)

#### 1. Real-World Industrial Context
A technician experiences a flat tire, vehicle collision, equipment malfunction, or medical emergency midway through their daily schedule.

#### 2. Detection Mechanism
- Dispatcher receives technician phone call or telematics alert and toggles status to `unavailable` in the console (`POST /technicians/<id>/toggle`).

#### 3. Naive Baseline vs. Proposed Dynamic Model
- **Naive Baseline**: The database retains the assigned technician ID. The system continues reporting "Technician arriving soon", leaving the customer stranded.
- **Proposed Dynamic Model**:
  1. The event listener `handle_technician_availability_change()` executes immediately:
  2. For all active jobs assigned to the disabled technician:
     - Queries the roster for the nearest available technician possessing the required skill.
     - If a candidate is found: automatically reassigns the job, recalculates the new travel ETA, logs `auto_assigned` in `assignment_history`, and texts the customer:
       > *"Fieldline Alert: Your appointment has been transferred to technician Priya Sharma due to vehicle breakdown. Updated ETA window: 28–38 mins."*
     - If no matching specialist is available: cleanly sets status to `unassigned`, resets ETA, logs reason to `assignment_history`, and alerts both customer and dispatch queue.

#### 4. Why the Chosen Approach is Appropriate
The system prioritizes **graceful degradation** over blind continuation. An explicit `unassigned` state with clean logging enables dispatchers to escalate or sub-contract immediately, rather than discovering a missed appointment hours later.

---

### Failure Mode 3: On-Site Dwell Time Overruns (Cascading Delays) (FM-03)

#### 1. Real-World Industrial Context
A technician servicing an electrical breaker panel at Customer A finds burnt sub-wiring and corrosion. A 40-minute job expands to 75 minutes. Customer B, scheduled for the subsequent appointment, is left waiting.

#### 2. Detection Mechanism
- Technician reports an on-site delay via the mobile trigger (`POST /jobs/<id>/report-delay`).
- The simulation engine samples dwell times with a lognormal tail, triggering an overrun alert whenever dwell exceeds scheduled limits by $>15\text{ minutes}$.

#### 3. Naive Baseline vs. Proposed Dynamic Model
- **Naive Baseline**: Assumes each job is an independent event. Downstream appointments receive zero communication. When the technician fails to arrive on time, Customer B calls dispatch in frustration.
- **Proposed Dynamic Model**:
  1. Propagates a $+15\text{ to }+25\text{ minute}$ delay to downstream appointments on the technician's sequence.
  2. Widens the uncertainty band by $+10\text{ minutes}$ to reflect downstream schedule volatility.
  3. Automatically pushes transparent delay notifications:
     > *"Fieldline Alert: Tech Suresh Babu is delayed (+15m) due to extended prior job. New ETA window: 38–52 mins. Track: /track/3"*

#### 4. Why the Chosen Approach is Appropriate
Field-service routing is fundamentally sequential. Modeling the cascading dependency structure prevents the *"silent delay"* syndrome that causes 88% of field-service customer complaints.

---

### Failure Mode 4: Specialist Skill Mismatch During Emergency Overrides (FM-04)

#### 1. Real-World Industrial Context
A critical plumbing emergency occurs (burst pipe flooding an apartment). All certified Plumbing technicians are currently committed on jobs across town. A General Maintenance technician is 3 blocks away.

#### 2. Detection Mechanism
- Automated skill-matching blocks the assignment because the available technician lacks `Plumbing` certification.
- Dispatcher assesses the emergency and decides to dispatch the General Maintenance technician to shut off the main water valve immediately.

#### 3. Naive Baseline vs. Proposed Dynamic Model
- **Naive Baseline**: Either strictly forbids the assignment (blocking emergency mitigation) or allows silent assignment without tracking that an uncertified worker was dispatched.
- **Proposed Dynamic Model**:
  1. Dispatcher initiates manual override via `/jobs/<id>/override`.
  2. The console detects the skill mismatch and issues an explicit warning banner:
     > *"WARNING: Priya Sharma does not possess required skill 'Plumbing'. Certified skills: General Maintenance, Appliance Repair."*
  3. Requires dispatcher to input an explicit justification reason.
  4. Immutably records the action in `assignment_history` with action `manual_override`, recording technician ID, dispatcher reason, and timestamp.
  5. Alerts the customer with tailored transparency.

#### 4. Why the Chosen Approach is Appropriate
Preserves operational flexibility for high-stakes emergencies while maintaining **100% regulatory auditability** and legal traceability. Management can later review all override events in `assignment_history` to identify where hiring more specialists is required.

---

### Failure Mode 5: GPS Telemetry Blackout & Dead Zones (FM-05)

#### 1. Real-World Industrial Context
Technicians driving through highway tunnels, underground parking garages, or rural fringe sectors experience cellular dead-zones where live GPS coordinates fail to update.

#### 2. Detection Mechanism
- Time-delta check between current system time and the vehicle's last recorded telemetry timestamp:
  $$\Delta t_{\text{telemetry}} = t_{\text{current}} - t_{\text{last\_ping}} > 10\text{ minutes}$$

#### 3. Naive Baseline vs. Proposed Dynamic Model
- **Naive Baseline**: Throws `NullPointerException` or computes distance using obsolete coordinates, showing a static "arriving in 2 minutes" indicator that remains frozen.
- **Proposed Dynamic Model**:
  1. Detects stale telemetry and triggers fallback dead-reckoning based on scheduled route corridor and base velocity ($24\text{ km/h}$).
  2. Expands the uncertainty band by $+15\text{ minutes}$ to visually and mathematically signal higher epistemic uncertainty.
  3. Displays a prominent advisory badge on the customer tracking portal:
     > *"Signal Temporarily Weak · ETA Window Estimated from Last Known Checkpoint"*

#### 4. Why the Chosen Approach is Appropriate
The principle of honest uncertainty dictates that when data quality degrades, **the system must communicate greater uncertainty rather than projecting false confidence**. This preserves customer credibility even during network outages.

---

## 3. Summary of Architectural Safeguards

```
+-------------------------------------------------------------------------------------------------+
|                                 ARCHITECTURAL SAFETY RECOVERY MAP                               |
+-------------------------------------------------------------------------------------------------+
| EXCEPTION EVENT             | DETECTION POINT             | AUTOMATED RECOVERY MECHANISM        |
+-----------------------------+-----------------------------+-------------------------------------+
| Traffic Congestion Surge    | Time-of-Day Traffic Engine  | Scale travel time 1.7x; widen band  |
|                             | or POST /events/traffic-shift| +8m; dispatch route traffic SMS.   |
+-----------------------------+-----------------------------+-------------------------------------+
| Sudden Tech Unavailable     | POST /technicians/<id>/toggle| Auto-migrate active jobs to nearest |
|                             |                             | free specialist; unassign cleanly.  |
+-----------------------------+-----------------------------+-------------------------------------+
| Prior Job Dwell Overrun     | POST /jobs/<id>/report-delay| Propagate +15m cascade; widen band  |
|                             | or lognormal tail sample    | +10m; alert downstream customer.    |
+-----------------------------+-----------------------------+-------------------------------------+
| Skill Mismatch Emergency    | POST /jobs/<id>/override    | Prompt reason; enforce audit log    |
|                             |                             | in assignment_history with warning. |
+-----------------------------+-----------------------------+-------------------------------------+
| Telemetry Signal Loss       | Stale Timestamp Check       | Dead-reckoning corridor velocity;   |
|                             | (delta > 10 min)            | widen uncertainty window by +15m.   |
+-------------------------------------------------------------------------------------------------+
```

---
