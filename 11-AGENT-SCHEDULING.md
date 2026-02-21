# 11-AGENT-SCHEDULING.md â€” Stella (The Scheduling Agent)

> **Omnira** â€” AI-native operating system for practice-based businesses
> **Document:** Scheduling Agent Deep-Dive Specification
> **Codename:** Stella
> **Status:** Living specification
> **Depends on:** `00-MASTER-PRD.md`, `01-ARCHITECTURE-SYSTEM.md`, `02-ARCHITECTURE-MEMORY.md`, `03-ARCHITECTURE-DATABASE.md`, `04-ARCHITECTURE-SECURITY.md`, `10-AGENT-ORCHESTRATOR.md`
> **Referenced by:** `12-AGENT-BILLING.md`, `13-AGENT-COMMUNICATION.md`, `14-AGENT-CLINICAL.md`, `15-AGENT-OPERATIONS.md`, `23-UI-SCHEDULE.md`, `30-API-INTERNAL.md`

---

## Cross-Reference Map

| Document | Relationship |
|---|---|
| `00-MASTER-PRD.md` Â§7 | Agent overview â€” Stella is Agent 1, this file is the deep dive |
| `00-MASTER-PRD.md` Â§9 | Permission framework â€” defines Autonomous/Supervised/Escalated tiers for scheduling actions |
| `00-MASTER-PRD.md` Â§26 | Roadmap Phase 1 â€” Stella is the first agent built |
| `01-ARCHITECTURE-SYSTEM.md` Â§4 | Agent Runtime â€” Stella runs within the agent runtime, receives tasks from Core |
| `01-ARCHITECTURE-SYSTEM.md` Â§6 | Lane Queue â€” Stella has her own serial execution lane |
| `01-ARCHITECTURE-SYSTEM.md` Â§7 | Event Bus â€” Stella emits `appointment.*` and `schedule.*` events |
| `02-ARCHITECTURE-MEMORY.md` Â§6 | Memory scoping â€” Stella reads/writes scheduling-domain memory |
| `03-ARCHITECTURE-DATABASE.md` | Schema â€” Stella owns `appointments`, `provider_schedules`, `schedule_blocks`, `rooms`, `waitlist_entries`, `recall_schedule` tables |
| `04-ARCHITECTURE-SECURITY.md` Â§9 | Agent sandboxing â€” Stella's tool allowlist restricts her to scheduling-domain writes |
| `10-AGENT-ORCHESTRATOR.md` Â§5 | Routing â€” Core dispatches `scheduling.*` intents to Stella |
| `10-AGENT-ORCHESTRATOR.md` Â§18 | Cross-agent workflows â€” Stella participates in Cancellation Recovery, New Patient Intake, Provider Absence, Morning Briefing, Treatment Plan Presentation |
| `12-AGENT-BILLING.md` | Vera â€” Stella triggers insurance verification after booking, receives coverage gap alerts |
| `13-AGENT-COMMUNICATION.md` | Relay â€” Stella requests confirmation messages, reminder sequences, waitlist outreach |
| `14-AGENT-CLINICAL.md` | Aria â€” Stella receives clinical constraint flags (contraindications, required equipment) |
| `15-AGENT-OPERATIONS.md` | Otto â€” Stella provides schedule data for morning briefings and production forecasts |

---

## Table of Contents

1. [Purpose & Identity](#1-purpose--identity)
2. [Architectural Position](#2-architectural-position)
3. [The Scheduling Domain Model](#3-the-scheduling-domain-model)
4. [Constraint-Satisfaction Engine](#4-constraint-satisfaction-engine)
5. [Slot-Finding Algorithm](#5-slot-finding-algorithm)
6. [Appointment Lifecycle](#6-appointment-lifecycle)
7. [Provider & Resource Management](#7-provider--resource-management)
8. [Waitlist Management](#8-waitlist-management)
9. [Cancellation Recovery](#9-cancellation-recovery)
10. [Recall Scheduling](#10-recall-scheduling)
11. [No-Show Prediction & Management](#11-no-show-prediction--management)
12. [Schedule Optimization](#12-schedule-optimization)
13. [Emergency & Walk-In Handling](#13-emergency--walk-in-handling)
14. [Double-Booking Rules](#14-double-booking-rules)
15. [Buffer Time Logic](#15-buffer-time-logic)
16. [Patient Preference Learning](#16-patient-preference-learning)
17. [Confirmation Sequences](#17-confirmation-sequences)
18. [Tool Registry & API Dependencies](#18-tool-registry--api-dependencies)
19. [Memory Access Patterns](#19-memory-access-patterns)
20. [Event Emissions](#20-event-emissions)
21. [Error Handling & Recovery](#21-error-handling--recovery)
22. [Permission Configuration](#22-permission-configuration)
23. [Sample Interactions](#23-sample-interactions)
24. [Pseudocode â€” Key Workflows](#24-pseudocode--key-workflows)
25. [Performance Targets](#25-performance-targets)
26. [Edge Cases & Failure Scenarios](#26-edge-cases--failure-scenarios)

**Appendices:**
- [A. Procedure Duration Matrix](#appendix-a-procedure-duration-matrix)
- [B. Scheduling Configuration Reference](#appendix-b-scheduling-configuration-reference)
- [C. Recall Interval Taxonomy](#appendix-c-recall-interval-taxonomy)

---

## 1. Purpose & Identity

### What Is Stella?

Stella is the scheduling agent â€” the agent that owns the entire appointment calendar, every provider's time, every room assignment, every recall cycle, every waitlist entry, and every cancellation recovery attempt. She is the heartbeat of the practice. Every minute of provider time has direct revenue implications, and Stella's job is to maximize chair utilization while minimizing patient wait times, provider downtime, and scheduling friction.

Stella is not a calendar widget. She is a constraint-satisfaction engine wrapped in a natural language interface, powered by learned patterns about how the practice actually operates. When the front desk says "book Mrs. Johnson for a cleaning sometime next week," Stella doesn't just show open slots â€” she evaluates provider availability, room requirements, equipment dependencies, patient preferences, insurance authorization windows, buffer times between procedures, production balance across the day, and historical patterns (Mondays are always overbooked, this patient cancels 40% of the time, hygienist appointments run 10 minutes over on average) to suggest the genuinely best slot.

### Why Stella Matters

Scheduling is where dental practices hemorrhage money without realizing it. The numbers are stark:

- **Cancellations:** Industry average fill rate is 10â€“20%. Stella targets 80%+. For a practice doing $1.5M/year, that's $50â€“150K in saved revenue.
- **No-shows:** Average 5â€“15% across dental. Each no-show costs $200â€“800 in lost production. Stella predicts and mitigates.
- **Recall attrition:** Industry recall effectiveness is 50â€“60%. Stella targets 80â€“90%. A well-run recall system generates $200K+/year for a mid-size practice.
- **Schedule gaps:** Unoptimized schedules leave 15â€“25% of chair time unused. Stella compresses gaps and balances production across the day.
- **Staff burden:** The average front desk spends 2â€“3 hours daily on scheduling-related tasks (booking, confirming, rebooking, calling waitlist). Stella reduces this to oversight-only.

**Combined impact:** 15â€“25% increase in chair utilization, $50â€“150K in saved cancellation revenue annually.

### Design Principles (Stella-Specific)

**1. Deterministic engine, LLM interface.** The actual slot-finding logic is deterministic code â€” a constraint solver, not an LLM. You do not want a language model hallucinating that 3pm is available when it isn't. The LLM handles natural language understanding ("book Mrs. Johnson for a cleaning sometime next week") and response generation. The engine handles the math.

**2. Lowest latency of all agents.** Scheduling is real-time. When the front desk is on the phone with a patient, they need slot suggestions in milliseconds, not seconds. Stella's hot path â€” the constraint solver query â€” must execute in under 50ms against the local SQLite database.

**3. Learn, don't assume.** Stella starts with sensible defaults (30-min hygiene, 60-min crown) but learns actual durations from practice history. If Dr. Patel's crowns consistently take 75 minutes, Stella adjusts. If Monday mornings always overbook, Stella adds buffer. Patient preferences are observed and stored â€” not just asked for once and forgotten.

**4. Recover aggressively.** Cancellations are not losses â€” they are opportunities. The moment a slot opens, Stella launches recovery. She doesn't wait for staff to notice, doesn't wait for a convenient time, doesn't process one waitlist patient at a time. She texts 3â€“5 candidates simultaneously and books the first to confirm. The slot should be filled within 15 minutes of cancellation.

**5. Own the calendar, respect the boundaries.** Stella owns all scheduling reads and writes. No other agent directly modifies the schedule. But Stella does not own communication (Relay sends the texts), billing (Vera handles insurance), or clinical decisions (Aria flags contraindications). Stella requests these services through events and the Orchestrator.

---

## 2. Architectural Position

### Where Stella Sits in the System

```
                    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                    â”‚   OMNIRA CORE    â”‚
                    â”‚  (Orchestrator)  â”‚
                    â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â”‚
         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
         â”‚                   â”‚                   â”‚
         â–¼                   â–¼                   â–¼
  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
  â”‚   STELLA    â”‚    â”‚    VERA     â”‚    â”‚    RELAY    â”‚
  â”‚ (Scheduling)â”‚    â”‚  (Billing)  â”‚    â”‚   (Comms)   â”‚
  â”‚             â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â”‚Constraintâ”‚ â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â”‚ Solver  â”‚ â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â”‚ Recall  â”‚ â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â”‚ Engine  â”‚ â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â”‚No-Show  â”‚ â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â”‚Predictorâ”‚ â”‚    â”‚             â”‚    â”‚             â”‚
  â”‚ â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚    â”‚             â”‚    â”‚             â”‚
  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
    LOCAL SQLite
  â”Œâ”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”
  â”‚ appointmentsâ”‚
  â”‚ providers   â”‚
  â”‚ schedules   â”‚
  â”‚ rooms       â”‚
  â”‚ waitlist    â”‚
  â”‚ recall      â”‚
  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Input Sources

Stella receives work from four sources:

1. **Core dispatch (primary).** The Orchestrator classifies a `scheduling.*` intent and dispatches a task to Stella's lane queue. This is the normal flow for user-initiated scheduling requests.

2. **Event-triggered (reactive).** Stella subscribes to events that require scheduling responses:
   - `appointment.cancelled` â†’ trigger cancellation recovery
   - `appointment.no_show` â†’ trigger no-show management
   - `patient.intake_completed` â†’ check for pending scheduling needs
   - `insurance.coverage_gap` â†’ flag affected appointments
   - `clinical.contraindication_detected` â†’ flag or block affected appointments
   - `provider.absence_marked` â†’ trigger provider absence workflow

3. **Cron-triggered (proactive).** Scheduled background tasks:
   - Every morning at 6:00 AM: compile today's schedule summary for morning briefing
   - Every evening at 5:00 PM: optimize tomorrow's schedule (compress gaps, suggest moves)
   - Daily at midnight: scan for recall-eligible patients, update no-show risk scores
   - Weekly on Sunday: generate next-week production forecast

4. **Inter-agent requests.** Other agents requesting scheduling data:
   - Vera: "What appointments does this patient have upcoming?" (for insurance verification timing)
   - Otto: "What's today's scheduled production value?" (for morning briefing)
   - Relay: "What appointments need confirmation messages?" (for reminder campaigns)
   - Aria: "What procedures are scheduled for this patient?" (for treatment plan context)

### Output Channels

Stella produces output through:

1. **Direct response to Core.** Answer to a user query ("Here are 3 available slots for Mrs. Johnson next week").
2. **Event emissions.** `appointment.booked`, `appointment.rescheduled`, `schedule.optimized`, etc.
3. **Relay requests.** Emit events that trigger Relay to send patient communications (confirmations, reminders, waitlist offers).
4. **Data writes.** Insert/update `appointments`, `waitlist_entries`, `recall_schedule`, `provider_schedules`, `schedule_blocks` tables.
5. **Escalation tasks.** When scheduling requires human judgment (double-booking approval, provider schedule conflict, patient complaint about scheduling).

### Lane Queue Behavior

Stella's lane processes tasks serially. This is critical because scheduling operations can conflict â€” two simultaneous booking attempts for the same slot would create a double-booking. Serial execution within Stella's lane eliminates this race condition entirely.

Priority ordering within Stella's lane:

| Priority | Task Types | Rationale |
|---|---|---|
| **Critical** | Cancellation recovery, provider absence rescheduling | Time-sensitive revenue impact |
| **High** | New bookings (patient on phone), recall scheduling | Direct revenue, patient experience |
| **Normal** | Rescheduling, confirmation processing, waitlist updates | Important but not urgent |
| **Background** | Schedule optimization, no-show score recalculation, analytics | Can wait, no patient impact |

---

## 3. The Scheduling Domain Model

### Core Entities

Stella operates on a dependency graph of interrelated entities. Understanding this graph is essential to understanding why scheduling is a constraint-satisfaction problem, not a simple calendar lookup.

```
                    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                    â”‚   PRACTICE    â”‚
                    â”‚  (config,     â”‚
                    â”‚   hours,      â”‚
                    â”‚   settings)   â”‚
                    â””â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
                            â”‚
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â”‚               â”‚               â”‚
            â–¼               â–¼               â–¼
     â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
     â”‚  PROVIDERS  â”‚ â”‚    ROOMS    â”‚ â”‚  EQUIPMENT  â”‚
     â”‚ (dentists,  â”‚ â”‚ (operatory  â”‚ â”‚ (x-ray,     â”‚
     â”‚  hygienists,â”‚ â”‚  chairs,    â”‚ â”‚  laser,     â”‚
     â”‚  assistants)â”‚ â”‚  consult)   â”‚ â”‚  CBCT, etc) â”‚
     â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜
            â”‚               â”‚               â”‚
            â”‚    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”     â”‚
            â”‚    â”‚                     â”‚     â”‚
            â–¼    â–¼                     â–¼     â–¼
     â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
     â”‚              APPOINTMENT                 â”‚
     â”‚  (patient, provider, room, procedure,   â”‚
     â”‚   start_time, end_time, status)         â”‚
     â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                        â”‚
              â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚                   â”‚
              â–¼                   â–¼
       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
       â”‚   PATIENT   â”‚    â”‚  PROCEDURE  â”‚
       â”‚ (prefs,     â”‚    â”‚  TYPE       â”‚
       â”‚  history,   â”‚    â”‚ (CDT code,  â”‚
       â”‚  no-show    â”‚    â”‚  duration,  â”‚
       â”‚  score)     â”‚    â”‚  requires)  â”‚
       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Appointment States

Every appointment moves through a state machine. Stella is responsible for all transitions.

```
                                    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                                    â”‚   REQUESTED  â”‚
                                    â”‚  (pending    â”‚
                                    â”‚   approval)  â”‚
                                    â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
                                           â”‚ approve
                                           â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   book    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  confirm  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ WAITLIST â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–ºâ”‚  SCHEDULED   â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–ºâ”‚  CONFIRMED   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜           â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜           â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚                          â”‚
                    cancel    â”‚                 check_in â”‚
                              â–¼                          â–¼
                       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”          â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                       â”‚  CANCELLED   â”‚          â”‚  CHECKED_IN  â”‚
                       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜          â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
                                                        â”‚
                                               start    â”‚
                                                        â–¼
                                                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”          â”‚ IN_PROGRESS  â”‚
                       â”‚   NO_SHOW    â”‚          â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜
                       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                 â”‚
                              â–²               complete  â”‚
                              â”‚                         â–¼
                              â”‚                  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚  COMPLETED   â”‚
                                 (if patient     â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                  never arrived)

  Additional transitions:
  SCHEDULED/CONFIRMED â†’ RESCHEDULED â†’ SCHEDULED (new time)
  ANY â†’ BROKEN (system error, data corruption â€” requires manual fix)
```

**State definitions:**

| State | Meaning | Stella's Responsibility |
|---|---|---|
| `requested` | Online booking or phone request pending staff approval | Present for approval (Supervised permission) |
| `scheduled` | Booked but not yet confirmed by patient | Trigger confirmation sequence via Relay |
| `confirmed` | Patient responded to confirmation | Monitor for cancellation, prepare for visit |
| `checked_in` | Patient arrived at practice | Update schedule display, trigger insurance re-verify if needed |
| `in_progress` | Patient is in the chair | Track actual duration for future learning |
| `completed` | Visit finished | Record actual duration, schedule next recall if applicable |
| `cancelled` | Cancelled by patient or practice | Trigger cancellation recovery |
| `no_show` | Patient didn't arrive and didn't cancel | Trigger no-show management, update risk score |
| `rescheduled` | Moved to a new time (creates new appointment, links to old) | Update all references, notify patient |
| `broken` | Data integrity issue | Create escalation task for staff |

### Provider Schedule Model

Each provider has a weekly template schedule that defines their working hours, lunch breaks, and blocked time. This template is the foundation against which Stella calculates availability.

```
ProviderSchedule {
  provider_id: UUID
  day_of_week: 0-6            // 0=Sunday, 6=Saturday
  start_time: Time             // e.g., 08:00
  end_time: Time               // e.g., 17:00
  lunch_start: Time?           // e.g., 12:00
  lunch_end: Time?             // e.g., 13:00
  is_working: bool             // false for days off
  location_id: UUID?           // for multi-location practices
  effective_from: Date         // template versioning
  effective_until: Date?       // null = current template
}
```

**Schedule overrides** handle one-off changes (PTO, half days, conferences, emergencies):

```
ScheduleOverride {
  provider_id: UUID
  override_date: Date
  override_type: "absent" | "modified_hours" | "added_hours" | "location_change"
  start_time: Time?           // null for full-day absence
  end_time: Time?
  reason: String              // "PTO", "Conference", "Emergency"
  affects_appointments: bool  // true triggers the provider absence workflow
  created_by: UUID            // user who created the override
}
```

### Room Model

Rooms (operatories) have their own availability constraints:

```
Room {
  room_id: UUID
  name: String                 // "Op 1", "Hygiene Room A", "Consult Room"
  room_type: "operatory" | "hygiene" | "consult" | "imaging" | "surgical"
  equipment: [EquipmentType]   // what's permanently installed
  is_active: bool
  max_concurrent_patients: 1   // almost always 1 for dental
}
```

### Procedure Type Model

Every dental procedure maps to scheduling requirements:

```
ProcedureType {
  code: String                 // CDT code, e.g., "D0120"
  name: String                 // "Periodic oral evaluation"
  category: String             // "diagnostic", "preventive", "restorative", etc.
  default_duration_minutes: i32  // base duration
  setup_minutes: i32           // time to prepare room before patient
  cleanup_minutes: i32         // time to turn over room after
  requires_provider_types: [ProviderType]  // "dentist", "hygienist", etc.
  requires_room_types: [RoomType]          // "operatory", "hygiene", etc.
  requires_equipment: [EquipmentType]      // "x-ray", "laser", etc.
  can_overlap_with: [String]   // procedure codes that can share appointment time
  requires_assistant: bool     // does this need a dental assistant?
  production_value: Decimal    // typical fee for production calculations
  insurance_category: String   // for coverage lookup
}
```

---

## 4. Constraint-Satisfaction Engine

### Why Constraints, Not Calendar Lookups

A naive scheduling system checks: "Is the slot empty?" That's not enough for dental. A valid appointment slot must satisfy **all** of the following constraints simultaneously:

1. **Provider available.** The provider is working that day, during those hours, and not at lunch, in a meeting, or on PTO.
2. **Provider qualified.** The provider can perform this procedure (a hygienist can't do a root canal).
3. **Room available.** An appropriate room type is free during the entire appointment window (including setup/cleanup buffer).
4. **Equipment available.** Required equipment is available (if the one CBCT machine is in use, can't schedule a CBCT scan).
5. **No time overlap.** The provider doesn't have another appointment during this window.
6. **Duration fit.** The slot is long enough for the procedure's full duration (including setup and cleanup).
7. **Buffer respected.** Minimum buffer time between this appointment and the provider's adjacent appointments is met.
8. **Schedule block respected.** The slot doesn't fall within a schedule block (e.g., "emergency-only" block, "hygiene-only" block, "meetings" block).
9. **Patient constraint.** If the patient has stated preferences (morning only, specific provider, avoid Fridays), those are factored in (soft constraints â€” can be violated with disclosure).
10. **Insurance constraint.** If the procedure requires pre-authorization and it hasn't been obtained, the slot should be flagged (soft constraint).
11. **Clinical constraint.** If Aria has flagged a contraindication or required prerequisite (e.g., clearance letter needed before extraction), the appointment is booked but flagged.
12. **Double-booking rules.** Practice-specific rules about whether this slot can be double-booked and under what conditions.

### Constraint Categories

Constraints are classified into three tiers:

| Tier | Name | Behavior | Examples |
|---|---|---|---|
| **Hard** | Must satisfy | Slot rejected if violated | Provider hours, room availability, equipment, no overlap, duration fit |
| **Soft** | Should satisfy | Slot ranked lower if violated, patient informed | Patient preferences, production balance, buffer times, provider continuity |
| **Advisory** | Good to satisfy | Logged as observation, no ranking impact | Insurance pre-auth pending, recall timing, schedule density targets |

### Constraint Evaluation Order

For performance, constraints are evaluated in order of cheapest-to-check first, with early termination on hard constraint failure:

```
1. Provider is_working on this day?              [O(1) lookup, hard]
2. Time within provider's working hours?          [O(1) compare, hard]
3. Time outside lunch/blocked periods?            [O(n) blocks check, hard]
4. Provider qualified for procedure?              [O(1) lookup, hard]
5. Duration fits within available window?         [O(1) arithmetic, hard]
6. Room of required type free?                    [O(n) overlap query, hard]
7. No appointment overlap for provider?           [O(log n) index query, hard]
8. Required equipment available?                  [O(n) overlap query, hard]
9. Buffer time between adjacent appointments?     [O(1) compare, soft]
10. Patient preferences satisfied?                [O(1) compare, soft]
11. Production balance within targets?            [O(1) compare, soft]
12. Schedule block type compatible?               [O(1) compare, soft]
13. Insurance pre-auth status?                    [O(1) lookup, advisory]
14. Clinical flags?                               [O(1) lookup, advisory]
```

If any hard constraint fails at step N, steps N+1 through 14 are not evaluated. This keeps average evaluation time under 1ms per candidate slot.

---

## 5. Slot-Finding Algorithm

### Overview

When Stella receives a booking request, the slot-finding algorithm generates a ranked list of available time slots that satisfy all constraints. The algorithm has two modes:

- **Specific mode:** User requested a specific date/time â†’ validate that single slot, return yes/no with reasons.
- **Search mode:** User requested a date range â†’ scan the range, collect all valid slots, rank them, return top N.

### Search Mode Algorithm

```
FUNCTION find_available_slots(request: BookingRequest) -> RankedSlots:
  
  INPUT:
    request.procedure_code     // CDT code â†’ lookup ProcedureType
    request.patient_id         // â†’ lookup preferences, history
    request.preferred_provider // optional
    request.date_range         // start_date to end_date
    request.preferred_times    // optional: "morning", "afternoon", specific time
    request.max_results        // default 5
  
  STEP 1: Resolve procedure requirements
    procedure = lookup_procedure(request.procedure_code)
    duration = get_adjusted_duration(procedure, request.preferred_provider)
    // adjusted_duration uses learned actual durations, not just defaults
    total_window = procedure.setup_minutes + duration + procedure.cleanup_minutes
    required_room_types = procedure.requires_room_types
    required_equipment = procedure.requires_equipment
    required_provider_types = procedure.requires_provider_types
  
  STEP 2: Identify candidate providers
    IF request.preferred_provider:
      providers = [request.preferred_provider]
      // also include alternatives in case preferred has no availability
      alt_providers = get_qualified_providers(procedure) - preferred
    ELSE:
      providers = get_qualified_providers(procedure)
    // Filter to only providers working during the date range
    providers = filter_working_providers(providers, request.date_range)
  
  STEP 3: Generate candidate time slots
    candidates = []
    FOR EACH provider IN providers:
      FOR EACH day IN request.date_range:
        working_hours = get_working_hours(provider, day)
        IF working_hours is NONE: CONTINUE  // provider off this day
        
        // Get existing appointments for this provider on this day
        existing = get_appointments(provider, day)
        
        // Get schedule blocks for this day
        blocks = get_schedule_blocks(provider, day)
        
        // Generate potential start times in 10-minute increments
        // (configurable: some practices use 15-min increments)
        slot_start = working_hours.start
        WHILE slot_start + total_window <= working_hours.end:
          slot_end = slot_start + total_window
          
          candidate = CandidateSlot {
            provider, day, slot_start, slot_end, procedure
          }
          candidates.append(candidate)
          slot_start += increment  // 10 or 15 minutes
  
  STEP 4: Evaluate constraints (parallel per candidate)
    valid_candidates = []
    FOR EACH candidate IN candidates:
      result = evaluate_constraints(candidate, procedure, request.patient_id)
      IF result.all_hard_constraints_passed:
        candidate.score = calculate_score(result, request)
        candidate.soft_violations = result.soft_violations
        candidate.advisories = result.advisories
        valid_candidates.append(candidate)
  
  STEP 5: Rank and deduplicate
    // Sort by composite score (highest first)
    valid_candidates.sort_by(|c| c.score, descending)
    
    // Deduplicate: if same provider has adjacent valid slots, keep the highest-scored
    deduped = deduplicate_adjacent(valid_candidates)
    
    // Return top N
    RETURN deduped.take(request.max_results)
```

### Scoring Function

Each valid candidate slot receives a composite score from 0.0 to 1.0. The scoring function balances multiple factors:

```
FUNCTION calculate_score(constraint_result, request) -> f64:
  score = 1.0
  weights = get_practice_weights()  // configurable per practice
  
  // Patient preference alignment (weight: 0.25)
  IF request.preferred_provider AND slot.provider == request.preferred_provider:
    score += weights.preferred_provider * 0.25
  IF request.preferred_times AND slot_matches_preference(slot, request.preferred_times):
    score += weights.preferred_time * 0.25
  
  // Provider continuity â€” same provider patient has seen before (weight: 0.15)
  IF patient_has_history_with(request.patient_id, slot.provider):
    score += weights.provider_continuity * 0.15
  
  // Production balance â€” avoid stacking all complex procedures (weight: 0.15)
  daily_production = get_scheduled_production(slot.provider, slot.day)
  IF daily_production < production_target * 0.8:
    score += weights.production_balance * 0.15  // day needs more production
  ELSE IF daily_production > production_target * 1.2:
    score -= weights.production_balance * 0.10  // day is overloaded
  
  // Schedule density â€” prefer filling gaps over creating new ones (weight: 0.15)
  IF slot_fills_gap(slot):
    score += weights.gap_fill * 0.15
  ELIF slot_creates_gap(slot):
    score -= weights.gap_creation * 0.10
  
  // Buffer time satisfaction (weight: 0.10)
  IF buffer_time_satisfied(slot):
    score += weights.buffer * 0.10
  
  // Recency â€” prefer sooner appointments for urgent procedures (weight: 0.10)
  days_out = (slot.day - today).days
  IF procedure.is_urgent AND days_out <= 3:
    score += weights.urgency * 0.10
  
  // Time-of-day optimization (weight: 0.10)
  // Complex procedures score higher in the morning when provider is fresh
  IF procedure.complexity == "high" AND slot.is_morning:
    score += weights.complexity_timing * 0.10
  
  RETURN clamp(score, 0.0, 1.0)
```

### Specific Mode Validation

When validating a specific requested slot:

```
FUNCTION validate_specific_slot(provider, datetime, procedure, patient_id) -> ValidationResult:
  result = evaluate_constraints(
    CandidateSlot { provider, datetime, procedure },
    procedure,
    patient_id
  )
  
  IF result.all_hard_constraints_passed:
    RETURN ValidationResult::Available {
      soft_violations: result.soft_violations,
      advisories: result.advisories,
      score: calculate_score(result, request)
    }
  ELSE:
    // Explain WHY this slot doesn't work
    reasons = result.hard_violations.map(|v| v.human_readable_reason)
    
    // Suggest closest alternatives
    alternatives = find_nearest_available(provider, datetime, procedure, patient_id, count=3)
    
    RETURN ValidationResult::Unavailable {
      reasons,
      alternatives
    }
```

---

## 6. Appointment Lifecycle

### Creation Flow

When Core dispatches a `scheduling.book` task to Stella:

```
1. RECEIVE booking request from Core
   â”‚
2. RESOLVE patient entity
   â”‚ â””â”€â”€ fuzzy match patient name against DB
   â”‚ â””â”€â”€ if ambiguous, return clarification request to Core
   â”‚
3. RESOLVE procedure type
   â”‚ â””â”€â”€ map natural language or CDT code to ProcedureType
   â”‚ â””â”€â”€ if ambiguous ("cleaning" could be D1110 or D4910), check patient history
   â”‚
4. CHECK permission level
   â”‚ â””â”€â”€ booking_type â†’ permission config
   â”‚ â””â”€â”€ Autonomous: proceed
   â”‚ â””â”€â”€ Supervised: create approval request, wait
   â”‚ â””â”€â”€ Escalated: create escalation task, halt
   â”‚
5. FIND available slots
   â”‚ â””â”€â”€ run slot-finding algorithm (Â§5)
   â”‚ â””â”€â”€ if no slots found, suggest expanding date range or alternative providers
   â”‚
6. PRESENT options (if search mode) or VALIDATE (if specific mode)
   â”‚ â””â”€â”€ return ranked slots to Core for user presentation
   â”‚ â””â”€â”€ OR validate specific slot and return result
   â”‚
7. RECEIVE user selection (if search mode)
   â”‚
8. BOOK appointment
   â”‚ â””â”€â”€ INSERT into appointments table
   â”‚ â””â”€â”€ assign room (best available of required type)
   â”‚ â””â”€â”€ emit appointment.booked event
   â”‚
9. TRIGGER post-booking actions
   â”‚ â””â”€â”€ emit event for Relay to send confirmation
   â”‚ â””â”€â”€ emit event for Vera to check insurance status
   â”‚ â””â”€â”€ if recall appointment, update recall_schedule
   â”‚ â””â”€â”€ save observation to memory: "Patient X booked for Y on Z"
   â”‚
10. RETURN confirmation to Core
```

### Modification Flow (Reschedule)

```
1. RECEIVE reschedule request
   â”‚
2. LOAD existing appointment
   â”‚ â””â”€â”€ validate appointment exists and is in a modifiable state
   â”‚     (scheduled, confirmed â€” not completed, in_progress, or broken)
   â”‚
3. CHECK permission level for reschedule
   â”‚
4. FIND new slot (same process as creation)
   â”‚
5. USER selects new slot
   â”‚
6. EXECUTE reschedule
   â”‚ â””â”€â”€ UPDATE old appointment status â†’ "rescheduled"
   â”‚ â””â”€â”€ INSERT new appointment with link to old (rescheduled_from)
   â”‚ â””â”€â”€ emit appointment.rescheduled event
   â”‚
7. TRIGGER post-reschedule actions
   â”‚ â””â”€â”€ emit event for Relay to notify patient of change
   â”‚ â””â”€â”€ emit event for Vera to update any pre-auths affected by date change
   â”‚ â””â”€â”€ if the old slot is now open and desirable, add to available recovery slots
```

### Cancellation Flow

```
1. RECEIVE cancellation request (user-initiated or patient-initiated)
   â”‚
2. LOAD existing appointment
   â”‚
3. CHECK cancellation policy
   â”‚ â””â”€â”€ within cancellation window? (e.g., <24 hours notice)
   â”‚ â””â”€â”€ if short-notice, flag for cancellation fee consideration (Vera's domain)
   â”‚
4. EXECUTE cancellation
   â”‚ â””â”€â”€ UPDATE appointment status â†’ "cancelled"
   â”‚ â””â”€â”€ SET cancellation_reason, cancelled_by, cancelled_at
   â”‚ â””â”€â”€ emit appointment.cancelled event
   â”‚
5. TRIGGER cancellation recovery (Â§9)
   â”‚ â””â”€â”€ evaluate slot value (production, time of day, provider)
   â”‚ â””â”€â”€ if slot is valuable enough to recover, launch waitlist outreach
   â”‚
6. TRIGGER post-cancellation actions
   â”‚ â””â”€â”€ emit event for Relay to send cancellation acknowledgment
   â”‚ â””â”€â”€ emit event for Vera to cancel any billing prep
   â”‚ â””â”€â”€ if this was a recall appointment, update recall status to "needs_rescheduling"
```

---

## 7. Provider & Resource Management

### Provider Capability Matrix

Stella maintains a provider capability matrix that maps which providers can perform which procedures:

```
ProviderCapability {
  provider_id: UUID
  procedure_category: String    // "restorative", "endodontic", "surgical", etc.
  procedure_codes: [String]     // specific CDT codes within category
  proficiency: "primary" | "secondary" | "emergency_only"
  notes: String?                // "Prefers not to do pediatric extractions"
}
```

**Proficiency levels:**
- `primary` â€” Provider's regular scope. Default routing target.
- `secondary` â€” Provider can do this but it's not their main focus. Route here if primary is unavailable.
- `emergency_only` â€” Provider can do this in emergencies but should not be routinely scheduled for it.

### Provider Availability Computation

Stella computes real-time availability by layering:

```
Base template (weekly recurring hours)
  MINUS schedule overrides (PTO, modified hours)
  MINUS existing appointments (already booked)
  MINUS schedule blocks (meetings, admin time, emergency holds)
  MINUS buffer time between appointments
  = AVAILABLE WINDOWS
```

This computation runs against the local SQLite database and must complete in under 50ms for a single provider's single day. For a multi-provider, multi-day search, Stella parallelizes provider queries.

### Room Assignment Strategy

When booking an appointment, Stella assigns the best available room using this priority:

1. **Patient's last room** (if available) â€” continuity reduces anxiety for anxious patients.
2. **Provider's preferred room** (if configured) â€” some providers have equipment preferences or workflows tied to specific rooms.
3. **Closest match to room type requirements** â€” operatory for restorative, hygiene room for cleanings.
4. **Least-utilized room** â€” balance wear and equipment usage across rooms.

Room assignment happens at booking time, not at check-in. This allows the schedule display to show room utilization to staff.

### Equipment Tracking

For practices with shared equipment (e.g., one portable x-ray unit, one CBCT machine), Stella tracks equipment bookings alongside room bookings:

```
EquipmentBooking {
  equipment_id: UUID
  appointment_id: UUID
  start_time: DateTime
  end_time: DateTime
  booked_by: "stella_auto" | UUID  // agent or user who reserved it
}
```

Equipment is a hard constraint â€” if the CBCT machine is booked at 10am, another CBCT appointment cannot be scheduled at 10am regardless of room or provider availability.

---

## 8. Waitlist Management

### Waitlist Model

The waitlist is not a simple FIFO queue. It's a prioritized, constraint-aware list of patients who want earlier appointments or specific slots.

```
WaitlistEntry {
  waitlist_id: UUID
  patient_id: UUID
  procedure_code: String           // what they need
  preferred_provider_id: UUID?     // optional preference
  preferred_days: [DayOfWeek]?     // "Monday, Wednesday, Friday"
  preferred_time_range: TimeRange? // "morning" â†’ 08:00-12:00
  acceptable_providers: [UUID]?    // providers they'd accept (null = any qualified)
  max_notice_minutes: i32          // how quickly they can come in (e.g., 120 = 2 hours notice)
  priority: "urgent" | "standard" | "flexible"
  source: "patient_request" | "cancellation_recovery" | "recall_outreach"
  created_at: DateTime
  expires_at: DateTime?            // auto-remove if not matched within N days
  status: "active" | "offered" | "accepted" | "declined" | "expired"
  offered_count: i32               // how many times this patient has been offered a slot
  last_offered_at: DateTime?
  notes: String?
}
```

### Waitlist Matching Algorithm

When a slot opens (cancellation, new availability, schedule change), Stella runs the matching algorithm:

```
FUNCTION match_waitlist_to_slot(open_slot: OpenSlot) -> [WaitlistMatch]:
  
  // Step 1: Find all active waitlist entries that COULD fit this slot
  candidates = waitlist_entries
    .filter(|e| e.status == "active")
    .filter(|e| procedure_fits_in_slot(e.procedure_code, open_slot))
    .filter(|e| provider_acceptable(open_slot.provider, e))
    .filter(|e| day_acceptable(open_slot.day, e))
    .filter(|e| time_acceptable(open_slot.time, e))
    .filter(|e| notice_sufficient(open_slot.start - now(), e.max_notice_minutes))
  
  // Step 2: Score each candidate
  FOR EACH candidate IN candidates:
    candidate.match_score = calculate_waitlist_score(candidate, open_slot)
  
  // Step 3: Sort by score, return top N (typically 3-5)
  candidates.sort_by(|c| c.match_score, descending)
  RETURN candidates.take(practice_config.waitlist_outreach_count)  // default: 5
```

**Waitlist scoring factors:**

| Factor | Weight | Description |
|---|---|---|
| Priority | 0.30 | Urgent > standard > flexible |
| Wait duration | 0.20 | Longer wait = higher score |
| Preference match | 0.20 | Slot matches their stated preferences |
| Response history | 0.15 | Patients who respond quickly to offers score higher |
| Notice window fit | 0.15 | More comfortable notice margin = higher score |

### Waitlist Outreach Protocol

When a slot opens and matches are found:

```
1. SELECT top 3-5 waitlist candidates
2. UPDATE each candidate status â†’ "offered"
3. EMIT waitlist.slot_available event with candidate list
   â””â”€â”€ Relay sends SMS to ALL candidates simultaneously
   â””â”€â”€ Message: "[Practice] has an opening on [Day] at [Time] for [Procedure]. 
        Reply YES to book or NO to pass. First to confirm gets the slot!"
4. START countdown timer (configurable, default: 60 minutes)
5. LISTEN for patient responses
   â””â”€â”€ First "YES" â†’ BOOK appointment, notify others "slot filled, keeping you on waitlist"
   â””â”€â”€ All "NO" or timer expires â†’ slot remains open
   â””â”€â”€ If slot not filled after first batch, consider second batch or recall outreach (Â§10)
```

**Key rule: Simultaneous outreach, first-to-confirm wins.** This is what makes Stella's cancellation fill rate 80%+ versus the industry average of 10-20%. Calling patients one at a time and waiting for responses is the bottleneck that kills fill rates.

---

## 9. Cancellation Recovery

### Recovery Trigger

Cancellation recovery triggers automatically when `appointment.cancelled` fires. Stella evaluates whether to recover based on slot value:

```
FUNCTION should_recover_slot(cancelled_appointment) -> bool:
  // Always recover if more than 2 hours until the appointment
  IF time_until_appointment < 2_hours:
    RETURN false  // too late to fill reliably
  
  // Calculate slot value
  production_value = cancelled_appointment.procedure.production_value
  is_prime_time = is_prime_time_slot(cancelled_appointment.start_time)
  
  // Always recover high-value slots
  IF production_value >= practice_config.high_value_threshold:  // default $300
    RETURN true
  
  // Always recover prime-time slots (mornings, post-lunch)
  IF is_prime_time:
    RETURN true
  
  // Recover medium-value slots if waitlist has candidates
  IF production_value >= practice_config.medium_value_threshold:  // default $150
    matching_waitlist = count_matching_waitlist(cancelled_appointment)
    RETURN matching_waitlist > 0
  
  // Low-value slots: only recover if we have excellent matches
  matching_waitlist = count_matching_waitlist(cancelled_appointment)
  RETURN matching_waitlist >= 3
```

### Recovery Workflow

The full cancellation recovery workflow (as defined in `10-AGENT-ORCHESTRATOR.md` Â§18, Workflow Template 1):

```
CANCELLATION RECOVERY WORKFLOW
  Priority: Critical
  Target: Slot filled within 15 minutes
  
  Phase 1: Immediate (0-2 minutes)
    â”œâ”€â”€ Stella: Mark appointment cancelled
    â”œâ”€â”€ Stella: Evaluate slot value â†’ decide to recover
    â”œâ”€â”€ Stella: Match waitlist candidates (Â§8)
    â””â”€â”€ Stella: Calculate open slot details (provider, room, duration, compatible procedures)
  
  Phase 2: Outreach (2-5 minutes)
    â”œâ”€â”€ Relay: Send simultaneous SMS to top 3-5 waitlist candidates
    â”œâ”€â”€ Relay: Send "sorry to miss you" message to cancelling patient
    â””â”€â”€ Stella: Start response countdown timer
  
  Phase 3: Resolution (5-60 minutes)
    â”œâ”€â”€ WAIT for first patient confirmation
    â”‚   â”œâ”€â”€ ON confirmation:
    â”‚   â”‚   â”œâ”€â”€ Stella: Book confirming patient into slot
    â”‚   â”‚   â”œâ”€â”€ Stella: Update other candidates' status back to "active"
    â”‚   â”‚   â”œâ”€â”€ Relay: Send confirmation to new patient
    â”‚   â”‚   â”œâ”€â”€ Relay: Send "slot filled" to other candidates
    â”‚   â”‚   â”œâ”€â”€ Vera: Set up billing for new patient's procedure
    â”‚   â”‚   â””â”€â”€ Otto: Update production forecast (optional)
    â”‚   â”‚
    â”‚   â””â”€â”€ ON timeout (no confirmations within 60 min):
    â”‚       â”œâ”€â”€ Stella: Expand search to recall-eligible patients
    â”‚       â”œâ”€â”€ Relay: Send recall outreach to matching patients
    â”‚       â””â”€â”€ Stella: If still unfilled, mark slot as open on schedule
  
  Phase 4: Cleanup
    â”œâ”€â”€ Vera: Cancel original patient's billing prep (if any)
    â””â”€â”€ Stella: Save observation: recovery success/failure + time to fill
```

### Recovery Metrics

Stella tracks recovery performance to learn and improve:

| Metric | Target | Tracked Per |
|---|---|---|
| Fill rate | 80%+ | Practice, provider, day of week |
| Time to fill | <15 minutes | Practice |
| Outreach response rate | >40% | Per patient (influences future waitlist scoring) |
| Second-batch needed rate | <30% | Practice |
| Revenue recovered | Dollar amount per month | Practice |

---

## 10. Recall Scheduling

### What Is Recall?

Recall is the system of scheduling patients for recurring preventive care â€” primarily 6-month hygiene visits, but also perio maintenance (3-4 month intervals), annual exams, and other recurring appointments. Recall is one of the single biggest revenue drivers in a dental practice. A well-run recall system generates $200K+/year for a mid-size practice. Most practices operate at 50-60% recall effectiveness. Stella targets 80-90%.

### Recall Model

```
RecallSchedule {
  recall_id: UUID
  patient_id: UUID
  recall_type: "hygiene" | "perio_maintenance" | "annual_exam" | "ortho_check" | "custom"
  interval_months: i32          // 6 for standard hygiene, 3-4 for perio
  last_completed_date: Date?    // date of last completed recall visit
  next_due_date: Date           // calculated from last_completed + interval
  preferred_provider_id: UUID?  // patient's usual hygienist
  status: "scheduled" | "due" | "overdue" | "contacted" | "refused" | "inactive"
  outreach_stage: i32           // 0=not started, 1=link sent, 2=reminder, 3=personal, 4=escalated
  last_outreach_date: Date?
  notes: String?
}
```

### Recall Status Definitions

| Status | Meaning | Stella's Action |
|---|---|---|
| `scheduled` | Patient already has a recall appointment booked | Monitor for cancellation/no-show |
| `due` | Next due date is within the scheduling window (default: 30 days before due) | Begin outreach sequence |
| `overdue` | Past due date with no appointment scheduled | Escalate outreach intensity |
| `contacted` | Outreach in progress, waiting for response | Continue sequence, track stage |
| `refused` | Patient explicitly declined recall | Respect for configured period, then retry |
| `inactive` | Patient has not responded after full outreach sequence | Flag for staff review |

### Outreach Sequence

Stella drives the recall outreach through Relay, using a multi-stage escalation:

```
Stage 0: Patient has a recall due within 30 days
  â””â”€â”€ Stella checks if appointment already scheduled
  â””â”€â”€ If not, advances to Stage 1

Stage 1: Scheduling link (Day 0 of outreach)
  â””â”€â”€ Relay sends SMS/email: "Hi [Patient], it's time for your 
      [cleaning/checkup] at [Practice]. Book your visit: [scheduling_link]"
  â””â”€â”€ Scheduling link shows pre-filtered available slots with their hygienist
  â””â”€â”€ Wait 5 days for response

Stage 2: Reminder (Day 5)
  â””â”€â”€ IF no response to Stage 1:
  â””â”€â”€ Relay sends SMS: "Friendly reminder â€” your [cleaning] is due! 
      We have great availability this month: [scheduling_link]"
  â””â”€â”€ Wait 7 days

Stage 3: Personal message (Day 12)
  â””â”€â”€ IF no response to Stage 2:
  â””â”€â”€ Relay sends personalized message: "Hi [Patient], [Hygienist Name] 
      noticed you're due for your visit. She'd love to see you! 
      Here are her next available times: [specific_slots]"
  â””â”€â”€ Wait 7 days

Stage 4: Escalation (Day 19)
  â””â”€â”€ IF no response to Stage 3:
  â””â”€â”€ Stella flags patient as requiring staff attention
  â””â”€â”€ Creates task: "Patient [Name] has not responded to 3 recall attempts. 
      Consider phone call or update patient status."
  â””â”€â”€ Status â†’ "inactive" if no response after staff follow-up
```

### Recall Scan (Nightly Batch)

Every night at midnight, Stella runs a recall scan:

```
FUNCTION run_recall_scan():
  // Find all patients with recall due within 30 days
  upcoming_recalls = recall_schedule
    .filter(|r| r.status IN ["due", "overdue"])
    .filter(|r| r.next_due_date <= today + 30_days)
    .filter(|r| patient_is_active(r.patient_id))
  
  FOR EACH recall IN upcoming_recalls:
    // Check if appointment already scheduled
    IF has_scheduled_appointment(recall.patient_id, recall.recall_type):
      recall.status = "scheduled"
      CONTINUE
    
    // Check outreach stage and timing
    IF recall.outreach_stage == 0:
      // Start outreach
      advance_outreach(recall, stage=1)
    ELIF days_since_last_outreach(recall) >= stage_wait_days(recall.outreach_stage):
      // Advance to next stage
      advance_outreach(recall, recall.outreach_stage + 1)
    
    // Update overdue status
    IF recall.next_due_date < today AND recall.status != "overdue":
      recall.status = "overdue"
      save_observation("Patient {recall.patient_id} is overdue for {recall.recall_type}")
  
  // Emit summary event for Otto's tracking
  emit("recall.scan_completed", {
    total_due: upcoming_recalls.len(),
    already_scheduled: count_scheduled,
    outreach_started: count_new_outreach,
    overdue: count_overdue
  })
```

---

## 11. No-Show Prediction & Management

### No-Show Risk Scoring

Stella maintains a no-show risk score for every patient, updated after each appointment outcome. The score is a probability from 0.0 (never no-shows) to 1.0 (always no-shows).

```
FUNCTION calculate_no_show_risk(patient_id) -> f64:
  history = get_appointment_history(patient_id, last_24_months)
  
  IF history.len() == 0:
    RETURN practice_config.default_no_show_risk  // default: 0.10 (10%)
  
  // Base rate from patient's own history
  no_show_count = history.filter(|a| a.status == "no_show").len()
  late_cancel_count = history.filter(|a| a.status == "cancelled" AND a.was_late_cancel).len()
  total_appointments = history.len()
  
  base_rate = (no_show_count + late_cancel_count * 0.5) / total_appointments
  
  // Recency weighting â€” recent behavior matters more
  recent_history = history.filter(|a| a.date >= today - 6_months)
  IF recent_history.len() >= 3:
    recent_rate = recent_history.filter(|a| a.status == "no_show").len() / recent_history.len()
    base_rate = base_rate * 0.4 + recent_rate * 0.6  // weight recent more heavily
  
  // Confirmation status adjustment
  IF patient_typically_confirms:
    base_rate *= 0.7  // patients who confirm are less likely to no-show
  
  // Day-of-week adjustment (some patients no-show more on certain days)
  day_adjustment = get_day_of_week_adjustment(patient_id, appointment_day)
  
  // Time-of-day adjustment (early morning and late afternoon have higher no-show rates)
  time_adjustment = get_time_of_day_adjustment(appointment_time)
  
  final_risk = clamp(base_rate * day_adjustment * time_adjustment, 0.0, 1.0)
  RETURN final_risk
```

### No-Show Thresholds & Actions

| Risk Level | Score Range | Stella's Action |
|---|---|---|
| **Low** | 0.00 â€“ 0.10 | Standard confirmation sequence (7d, 48h, 24h) |
| **Medium** | 0.10 â€“ 0.25 | Enhanced confirmation (7d, 48h, 24h, 2h), flag for front desk |
| **High** | 0.25 â€“ 0.50 | Same-day confirmation required, suggest double-booking the slot |
| **Very High** | 0.50+ | Require deposit or pre-payment, consider shorter appointment window, flag for staff |

### No-Show Event Handling

When a patient no-shows (marked by staff at check-in time + grace period):

```
1. UPDATE appointment status â†’ "no_show"
2. UPDATE patient's no_show_risk score
3. EMIT appointment.no_show event
4. 
5. IMMEDIATE ACTIONS:
   â”œâ”€â”€ Relay: Send SMS "We missed you today! Need to reschedule? [link]"
   â”œâ”€â”€ Stella: Attempt to fill the now-open slot (same as cancellation recovery)
   â””â”€â”€ Stella: Save observation about no-show pattern
   
6. FOLLOW-UP (24 hours, if no response):
   â”œâ”€â”€ Relay: Send follow-up attempt (SMS or email)
   â””â”€â”€ Stella: Update recall status if this was a recall appointment

7. THRESHOLD CHECK:
   IF patient.total_no_shows >= 3:
   â”œâ”€â”€ Stella: Flag patient record with "requires_deposit" tag
   â”œâ”€â”€ Create staff task: "Patient [Name] has 3+ no-shows. Consider deposit policy."
   â””â”€â”€ Save observation: "Patient flagged for deposit requirement after 3 no-shows"
```

### Double-Booking Recommendations

When a slot has a high no-show risk patient, Stella may recommend double-booking:

```
FUNCTION recommend_double_book(appointment) -> DoubleBookRecommendation?:
  risk = calculate_no_show_risk(appointment.patient_id)
  
  IF risk < practice_config.double_book_threshold:  // default: 0.30
    RETURN None
  
  // Only recommend double-booking with short procedures
  IF appointment.duration > 30_minutes:
    RETURN None  // don't double-book complex procedures
  
  // Find a short procedure from waitlist that could fill this slot
  short_waitlist = waitlist_entries
    .filter(|e| e.procedure.duration <= 20_minutes)
    .filter(|e| provider_acceptable(appointment.provider, e))
  
  IF short_waitlist.is_empty():
    RETURN None
  
  RETURN DoubleBookRecommendation {
    original_appointment: appointment,
    risk_score: risk,
    suggested_overlay: short_waitlist.first(),
    reason: "Patient has {risk*100}% no-show probability. Consider scheduling 
             a short procedure ({short_waitlist.first().procedure.name}) as backup."
  }
```

---

## 12. Schedule Optimization

### Daily Optimization (Nightly Run)

Every evening at 5:00 PM, Stella analyzes tomorrow's schedule and suggests optimizations:

```
FUNCTION optimize_tomorrow():
  tomorrow = today + 1_day
  schedule = get_full_schedule(tomorrow)
  suggestions = []
  
  // 1. Gap detection â€” find unproductive gaps between appointments
  FOR EACH provider IN active_providers:
    appointments = schedule.for_provider(provider).sort_by_time()
    FOR i IN 0..appointments.len()-1:
      gap = appointments[i+1].start - appointments[i].end
      IF gap > 15_minutes AND gap < 60_minutes:
        // This is a "dead gap" â€” too short for a new appointment, too long to be buffer
        suggestions.push(GapSuggestion {
          provider, gap_start: appointments[i].end, gap_end: appointments[i+1].start,
          suggestion: "Move {appointments[i+1]} earlier to close {gap}min gap",
          savings: gap_minutes * provider.hourly_rate / 60
        })
  
  // 2. Production balance â€” check if any provider is under/over-loaded
  FOR EACH provider IN active_providers:
    production = calculate_scheduled_production(provider, tomorrow)
    target = provider.daily_production_target
    IF production < target * 0.7:
      suggestions.push(ProductionAlert {
        provider, production, target,
        suggestion: "Schedule is {(1 - production/target)*100}% below production target. 
                     Consider filling with waitlist patients."
      })
  
  // 3. Buffer time violations â€” appointments too close together
  FOR EACH provider IN active_providers:
    appointments = schedule.for_provider(provider).sort_by_time()
    FOR i IN 0..appointments.len()-1:
      buffer = appointments[i+1].start - appointments[i].end
      required_buffer = get_required_buffer(appointments[i].procedure, appointments[i+1].procedure)
      IF buffer < required_buffer:
        suggestions.push(BufferViolation {
          provider, between: (appointments[i], appointments[i+1]),
          actual_buffer: buffer, required_buffer,
          suggestion: "Insufficient buffer between {appointments[i].procedure} and 
                       {appointments[i+1].procedure}. Consider moving later appointment."
        })
  
  // 4. Room conflicts â€” double-booked rooms (should not happen but defensive check)
  room_conflicts = find_room_overlaps(tomorrow)
  FOR EACH conflict IN room_conflicts:
    suggestions.push(RoomConflict { ... })
  
  // Emit optimization results
  IF suggestions.len() > 0:
    emit("schedule.optimization_available", {
      date: tomorrow,
      suggestions: suggestions,
      total_potential_savings: sum(suggestions.map(|s| s.savings))
    })
  
  // Auto-apply safe optimizations if configured (Autonomous permission)
  safe_suggestions = suggestions.filter(|s| s.is_safe_to_auto_apply)
  IF practice_config.auto_optimize AND safe_suggestions.len() > 0:
    apply_optimizations(safe_suggestions)
```

### Production Tracking

Stella tracks scheduled production (expected revenue) for each day:

```
ScheduledProduction {
  date: Date
  provider_id: UUID
  scheduled_production: Decimal   // sum of production_value for all appointments
  completed_production: Decimal   // actual production from completed appointments
  lost_production: Decimal        // production from cancelled/no-show appointments
  production_target: Decimal      // daily goal
  utilization_pct: f64            // (booked_minutes / available_minutes) * 100
}
```

This data feeds into Otto's morning briefing and production dashboards.

---

## 13. Emergency & Walk-In Handling

### Emergency Slot Holds

Practices can configure Stella to hold one or more slots per day for emergencies:

```
EmergencySlotConfig {
  provider_id: UUID?               // null = any provider
  time_range: TimeRange            // e.g., 10:00-11:00
  duration_minutes: i32            // typically 30-60
  release_if_unused_by: Time       // e.g., by 2:00 PM, release for regular booking
  days_of_week: [DayOfWeek]        // which days to hold emergency slots
}
```

When a walk-in or emergency call arrives:

```
FUNCTION handle_emergency(patient, complaint):
  // 1. Check for held emergency slots today
  emergency_slots = get_emergency_slots(today)
    .filter(|s| s.status == "held" AND s.start_time > now())
  
  IF emergency_slots.is_not_empty():
    // Use the next available emergency slot
    slot = emergency_slots.first()
    RETURN offer_slot(patient, slot, priority="emergency")
  
  // 2. No held slots â€” find shortest wait by scanning today's schedule
  gaps = find_gaps(today, min_duration=20)  // minimum 20 min for emergency eval
  
  IF gaps.is_not_empty():
    best_gap = gaps.sort_by(|g| g.start_time).first()
    RETURN offer_slot(patient, best_gap, priority="emergency")
  
  // 3. No gaps â€” check if any appointments can be shifted
  moveable = find_moveable_appointments(today)
    .filter(|a| a.patient_flexibility == "confirmed_flexible")
  
  IF moveable.is_not_empty():
    // Supervised: propose moving a flexible appointment to create room
    RETURN create_approval_request(
      action: "Move {moveable.first().patient}'s appointment 30 min later to accommodate emergency",
      urgency: "high"
    )
  
  // 4. Last resort â€” schedule for next available slot
  next_available = find_available_slots(BookingRequest {
    procedure_code: "D0140",  // limited oral evaluation
    date_range: today..today+2_days,
    max_results: 3
  })
  RETURN offer_slots(patient, next_available, context: "Earliest available emergency slots")
```

### Walk-In Digital Intake

When a walk-in arrives:

```
1. Staff marks patient as walk-in in UI
2. Stella checks for available slots (same process as emergency)
3. If patient is new: emit event for Relay to send digital intake form to patient's phone
4. Stella books the slot and assigns room
5. If patient is existing: pull up their record, check for outstanding treatment
6. Emit appointment.booked event with source="walk_in"
```

---

## 14. Double-Booking Rules

### When Double-Booking Is Allowed

Double-booking (scheduling two patients in overlapping time for the same provider) is a common and legitimate dental practice strategy. Stella handles this through explicit rules:

```
DoubleBookingConfig {
  enabled: bool                          // practice-level toggle
  max_concurrent_patients: i32           // typically 2, rarely 3
  allowed_combinations: [ProcedurePair]  // which procedure combos can overlap
  requires_assistant: bool               // must have dental assistant available
  permission_level: "autonomous" | "supervised"  // auto or require approval
}
```

**Allowed double-booking scenarios (typical dental config):**

| Primary Procedure | Overlay Procedure | Rationale |
|---|---|---|
| Crown prep (D2740) | Hygiene check (D0120) | Provider starts crown, steps out for hygiene check while waiting for impression |
| Root canal (D3310) | X-ray review (D0220) | Provider reviews x-rays in another room during anesthesia wait |
| Surgical extraction | Post-op check | Quick check on recent surgery patient between extraction steps |
| Any complex procedure | Emergency eval (D0140) | Brief emergency assessment during a gap in the primary procedure |

**Never double-book:**
- Two complex procedures simultaneously
- Any procedure for the same patient
- When no dental assistant is available to monitor the second patient
- More than `max_concurrent_patients` at once

### Double-Booking Validation

```
FUNCTION validate_double_book(new_appointment, existing_overlap) -> ValidationResult:
  IF NOT practice_config.double_booking.enabled:
    RETURN Rejected("Double-booking is disabled for this practice")
  
  // Check if this combination is allowed
  pair = (existing_overlap.procedure, new_appointment.procedure)
  IF pair NOT IN practice_config.double_booking.allowed_combinations:
    RETURN Rejected("This procedure combination cannot be double-booked")
  
  // Check concurrent patient count
  concurrent = count_overlapping_appointments(new_appointment.provider, new_appointment.time_range)
  IF concurrent >= practice_config.double_booking.max_concurrent_patients:
    RETURN Rejected("Provider already has maximum concurrent patients")
  
  // Check assistant availability
  IF practice_config.double_booking.requires_assistant:
    IF NOT assistant_available(new_appointment.time_range):
      RETURN Rejected("No dental assistant available for double-booked patient")
  
  // Check room availability (each patient needs their own room)
  IF NOT room_available_for(new_appointment):
    RETURN Rejected("No available room for second patient")
  
  RETURN Approved(permission_level: practice_config.double_booking.permission_level)
```

---

## 15. Buffer Time Logic

### Buffer Types

Stella manages three types of buffer time:

**1. Procedure cleanup buffer.** Time after an appointment to clean and prepare the room for the next patient. Defined per procedure type in the `ProcedureType.cleanup_minutes` field. Typical: 5-15 minutes.

**2. Procedure setup buffer.** Time before an appointment to set up the room and instruments. Defined per procedure type in the `ProcedureType.setup_minutes` field. Typical: 5-10 minutes.

**3. Provider transition buffer.** Time between appointments for the provider to write notes, wash hands, and mentally transition. Defined per practice. Typical: 5-10 minutes. This is separate from room setup/cleanup â€” it accounts for the provider's time, not the room's time.

### Buffer Calculation

```
FUNCTION calculate_total_buffer(prev_procedure, next_procedure) -> BufferMinutes:
  cleanup = prev_procedure.cleanup_minutes      // e.g., 10 min
  setup = next_procedure.setup_minutes           // e.g., 5 min
  transition = practice_config.provider_transition_buffer  // e.g., 5 min
  
  // Cleanup and setup can overlap if a different room is used
  IF prev_appointment.room != next_appointment.room:
    // Parallel cleanup/setup â€” only count the longer one plus transition
    room_buffer = max(cleanup, setup)
    total = room_buffer + transition
  ELSE:
    // Same room â€” sequential cleanup then setup plus transition
    total = cleanup + setup + transition
  
  // Apply learned adjustment if this provider consistently runs over/under
  provider_adjustment = get_provider_timing_adjustment(provider_id)
  total = total * provider_adjustment  // e.g., 1.1 if provider typically runs 10% over
  
  RETURN total
```

### Buffer as Soft Constraint

Buffer time is a **soft constraint** in the slot-finding algorithm. Stella will schedule appointments with insufficient buffer if hard-pressed (no other slots available) but will:

1. Flag the appointment with a `tight_buffer` warning.
2. Note it in the schedule optimization suggestions.
3. Factor it into the slot's quality score (lower score).

---

## 16. Patient Preference Learning

### What Stella Learns

Stella observes patient behavior over time and stores learned preferences in semantic memory:

| Preference Type | How Learned | How Used |
|---|---|---|
| Preferred days | Booking history pattern | Soft constraint in slot scoring |
| Preferred times | Booking history + explicit request | Soft constraint in slot scoring |
| Preferred provider | Booking history + explicit request | Provider prioritization |
| Appointment punctuality | Check-in time patterns | No-show risk adjustment |
| Cancellation patterns | Cancellation history | No-show risk, confirmation aggressiveness |
| Communication preference | Response patterns | Relay channel selection |
| Scheduling lead time | How far in advance they typically book | Recall outreach timing |
| Rescheduling frequency | How often they change appointments | Buffer in confirmation messaging |

### Preference Storage

Preferences are stored as semantic memory observations:

```
// Example observations Stella saves:
save_observation("patient:{patient_id}", 
  "Patient prefers Tuesday or Thursday morning appointments, usually with Dr. Patel")

save_observation("patient:{patient_id}", 
  "Patient has cancelled 3 of last 8 appointments, always within 24 hours of appointment")

save_observation("patient:{patient_id}", 
  "Patient consistently arrives 10-15 minutes late to appointments")

save_observation("practice:scheduling", 
  "Monday 8-10am slots fill within 24 hours of opening. High-demand window.")

save_observation("practice:scheduling", 
  "Dr. Martinez's crown preps average 75 minutes, not 60. Adjust default duration.")
```

### Learning Feedback Loop

```
WHEN appointment.completed:
  // Learn actual duration vs. scheduled duration
  actual_duration = appointment.completed_at - appointment.started_at
  scheduled_duration = appointment.end_time - appointment.start_time
  
  IF abs(actual_duration - scheduled_duration) > 10_minutes:
    update_duration_model(appointment.provider, appointment.procedure, actual_duration)
    IF consistently_different(appointment.provider, appointment.procedure):
      save_observation("provider:{provider_id}",
        "Provider's {procedure.name} consistently takes {avg_actual}min, not {scheduled}min")

WHEN appointment.checked_in:
  // Learn arrival patterns
  scheduled_time = appointment.start_time
  arrival_time = now()
  early_minutes = (scheduled_time - arrival_time).minutes
  
  update_arrival_model(appointment.patient_id, early_minutes)
```

---

## 17. Confirmation Sequences

### Default Sequence

Stella drives confirmation sequences through Relay. The sequence is configurable per practice but follows a sensible default:

```
ConfirmationSequence {
  appointment_id: UUID
  stages: [
    { trigger: appointment_time - 7_days,  channel: "sms",   message: "confirmation_7d" },
    { trigger: appointment_time - 48_hours, channel: "sms",   message: "confirmation_48h" },
    { trigger: appointment_time - 24_hours, channel: "sms",   message: "confirmation_24h" },
  ]
  enhanced_stages: [  // added for medium/high no-show risk patients
    { trigger: appointment_time - 2_hours,  channel: "sms",   message: "confirmation_2h" },
  ]
  status: "pending" | "confirmed" | "unconfirmed" | "cancelled_by_patient"
}
```

### Confirmation Logic

```
WHEN confirmation stage triggers:
  IF appointment.status IN ["cancelled", "rescheduled", "completed"]:
    SKIP  // appointment no longer needs confirmation
  
  IF appointment.confirmation_status == "confirmed":
    SKIP  // already confirmed
  
  // Request Relay to send confirmation message
  emit("scheduling.confirmation_needed", {
    appointment_id,
    patient_id,
    stage: current_stage,
    message_template: stage.message,
    channel: stage.channel,
    appointment_details: { date, time, provider, procedure, location }
  })

WHEN patient responds to confirmation:
  IF response == "confirmed" (YES, CONFIRM, thumbs up, etc.):
    appointment.confirmation_status = "confirmed"
    emit("appointment.confirmed", { appointment_id })
  
  ELIF response == "cancel" (CANCEL, NO, can't make it, etc.):
    appointment.status = "cancelled"
    appointment.cancellation_reason = "patient_cancelled_via_confirmation"
    emit("appointment.cancelled", { appointment_id, source: "confirmation_response" })
    // This triggers cancellation recovery (Â§9)
  
  ELIF response == "reschedule" (RESCHEDULE, different time, etc.):
    // Send scheduling link
    emit("scheduling.reschedule_requested", {
      appointment_id, patient_id,
      send_scheduling_link: true
    })

WHEN appointment_time - 24_hours AND confirmation_status != "confirmed":
  // Flag as unconfirmed
  appointment.confirmation_status = "unconfirmed"
  emit("appointment.unconfirmed", { appointment_id })
  // Create task for front desk: "Patient [Name] has not confirmed tomorrow's appointment"
  
  // If high no-show risk, begin waitlist contingency
  IF no_show_risk(appointment.patient_id) > 0.30:
    pre_stage_waitlist_search(appointment)  // find potential replacements just in case
```

---

## 18. Tool Registry & API Dependencies

### Stella's Tool Allowlist

Stella can only call tools from her approved list. This is enforced by the Gateway's sandboxing layer.

**Read Tools (Data Access):**

| Tool | Purpose | Returns |
|---|---|---|
| `get_patient` | Lookup patient record | Patient demographics, preferences, history summary |
| `search_patients` | Fuzzy search patients by name, DOB, phone | List of matching patients |
| `get_appointment` | Lookup specific appointment | Full appointment record |
| `list_appointments` | Query appointments by date, provider, patient, status | Filtered appointment list |
| `get_provider_schedule` | Get provider's working hours and overrides | Schedule template + overrides |
| `get_provider_availability` | Computed available windows for a provider/date | List of available time ranges |
| `list_rooms` | Get all rooms with type and equipment | Room list |
| `get_room_availability` | Check room bookings for a date | Booked and free time ranges |
| `get_waitlist` | Query waitlist entries | Filtered waitlist entries |
| `get_recall_status` | Get recall schedule for a patient | Recall records |
| `get_procedure_type` | Lookup procedure by CDT code or name | Procedure requirements |
| `get_practice_config` | Get scheduling configuration | Config object |
| `get_no_show_risk` | Calculate patient's no-show risk score | Risk score + factors |
| `query_semantic_memory` | Search scheduling-domain observations | Relevant observations |
| `get_production_summary` | Get scheduled/actual production for date range | Production metrics |

**Write Tools (State Changes):**

| Tool | Purpose | Permission Level |
|---|---|---|
| `create_appointment` | Book a new appointment | Autonomous (standard) or Supervised (complex/override) |
| `update_appointment` | Modify appointment details (time, provider, room, status) | Autonomous (minor changes) or Supervised (reschedule) |
| `cancel_appointment` | Cancel an appointment | Autonomous (patient-requested) or Supervised (practice-initiated) |
| `check_in_patient` | Mark patient as arrived | Autonomous |
| `start_appointment` | Mark appointment as in-progress | Autonomous |
| `complete_appointment` | Mark appointment as completed, record actual duration | Autonomous |
| `mark_no_show` | Mark patient as no-show | Autonomous |
| `add_to_waitlist` | Create waitlist entry | Autonomous |
| `update_waitlist_entry` | Modify waitlist entry status | Autonomous |
| `remove_from_waitlist` | Delete waitlist entry | Autonomous |
| `update_recall_schedule` | Modify recall settings for a patient | Autonomous |
| `create_schedule_block` | Block time on provider's schedule | Supervised |
| `create_schedule_override` | Add PTO, modified hours, etc. | Supervised |
| `save_observation` | Save learned pattern to semantic memory | Autonomous |
| `create_escalation` | Escalate to human | Autonomous |
| `create_approval_request` | Request staff approval for supervised action | Autonomous |

### External Dependencies

Stella has **no direct external API dependencies**. All her data is in the local SQLite database. Communication with patients goes through Relay (which uses Twilio/SendGrid). Insurance checks go through Vera (which uses Stedi). This isolation is intentional â€” Stella should work perfectly even if the internet is down.

**Indirect dependencies (via event bus):**
- Relay: for sending confirmation messages, waitlist outreach, recall messages
- Vera: for insurance status checks that affect scheduling decisions
- Aria: for clinical constraint flags
- Otto: for production targets and morning briefing data requests

---

## 19. Memory Access Patterns

### Read Access

| Memory Scope | What Stella Reads | Example |
|---|---|---|
| `patient:{id}` | Scheduling preferences, history observations | "Patient prefers morning appointments with Dr. Patel" |
| `provider:{id}` | Timing patterns, capability observations | "Dr. Martinez's crowns average 75 minutes" |
| `practice:scheduling` | Practice-wide scheduling patterns | "Monday mornings are highest demand" |
| `practice:config` | Configuration values | "Buffer time is 10 minutes" |

### Write Access

| Memory Scope | What Stella Writes | Example |
|---|---|---|
| `patient:{id}` | Booking patterns, no-show patterns, preference observations | "Patient cancelled 3 of last 5 Friday appointments" |
| `provider:{id}` | Duration patterns, utilization observations | "Provider averages 82% utilization on Tuesdays" |
| `practice:scheduling` | Scheduling trends, optimization observations | "Cancellation recovery fill rate is 78% this month" |

### Memory Isolation

Stella **cannot read** and does not request:
- Clinical notes or treatment details (Aria's domain)
- Financial details â€” balances, payment history, insurance plan specifics (Vera's domain)
- Communication content â€” message bodies, call transcripts (Relay's domain)

Stella **can read** from shared patient context:
- Patient name, demographics, contact info
- Insurance status (active/inactive, plan name â€” not financial details)
- Active treatment plan existence (for scheduling treatment appointments â€” not the clinical details)

---

## 20. Event Emissions

### Events Stella Emits

| Event | Payload | Trigger | Consumers |
|---|---|---|---|
| `appointment.booked` | appointment_id, patient_id, provider_id, procedure, datetime | New appointment created | Vera (insurance check), Relay (confirmation), Otto (production) |
| `appointment.rescheduled` | appointment_id, old_datetime, new_datetime, reason | Appointment moved | Relay (notify patient), Vera (update pre-auths) |
| `appointment.cancelled` | appointment_id, patient_id, reason, cancelled_by | Appointment cancelled | Stella (recovery), Relay (notify), Vera (cancel billing prep) |
| `appointment.confirmed` | appointment_id, confirmed_via | Patient confirmed | Otto (schedule confidence), UI (status update) |
| `appointment.unconfirmed` | appointment_id, attempts_made | Patient did not confirm after all attempts | Staff task creation, UI (warning flag) |
| `appointment.checked_in` | appointment_id, arrival_time, early_minutes | Patient arrived | UI (status update), Vera (final insurance check) |
| `appointment.started` | appointment_id, actual_start_time | Procedure began | UI (status update) |
| `appointment.completed` | appointment_id, actual_duration, actual_end_time | Procedure finished | Vera (billing), Stella (duration learning), Otto (production) |
| `appointment.no_show` | appointment_id, patient_id | Patient didn't arrive | Stella (recovery), Relay (follow-up), risk score update |
| `schedule.block_created` | block_id, provider_id, date, type | Time blocked on schedule | UI (display update) |
| `schedule.optimization_available` | date, suggestions[], potential_savings | Nightly optimization found improvements | Staff notification, UI (suggestion display) |
| `schedule.optimized` | date, changes_applied[] | Auto-optimization applied | UI (display update), audit log |
| `waitlist.entry_created` | waitlist_id, patient_id, procedure | Patient added to waitlist | UI (waitlist display) |
| `waitlist.slot_offered` | waitlist_id, patient_id, slot_details | Slot offered to waitlist patient | Relay (send offer) |
| `waitlist.slot_filled` | waitlist_id, appointment_id | Waitlist patient booked | Relay (confirm), UI (waitlist update) |
| `recall.due` | recall_id, patient_id, recall_type, due_date | Patient recall is coming due | Relay (outreach), Otto (recall metrics) |
| `recall.overdue` | recall_id, patient_id, days_overdue | Patient is past recall due date | Staff notification, Relay (escalated outreach) |
| `recall.scan_completed` | total_due, scheduled, outreach_started, overdue | Nightly scan results | Otto (dashboard metrics) |
| `provider.availability_changed` | provider_id, date, change_type | Schedule override created | UI (calendar update), affected appointment checks |

### Events Stella Subscribes To

| Event | Source | Stella's Response |
|---|---|---|
| `appointment.cancelled` | Self/UI | Trigger cancellation recovery |
| `appointment.no_show` | Staff/UI | Trigger no-show management, slot recovery |
| `insurance.coverage_gap` | Vera | Flag affected upcoming appointments |
| `insurance.verified` | Vera | Update appointment record with verification status |
| `clinical.contraindication_detected` | Aria | Flag/block affected appointment, create staff alert |
| `patient.intake_completed` | Relay/UI | Check for pending scheduling needs |
| `provider.absence_marked` | Staff/UI | Trigger provider absence workflow |
| `provider.schedule_updated` | Staff/UI | Recalculate availability, check for conflicts |

---

## 21. Error Handling & Recovery

### Error Taxonomy

| Error | Severity | Recovery |
|---|---|---|
| `SlotNoLongerAvailable` | Medium | Another booking took the slot during processing. Re-run slot finder, present alternatives. |
| `PatientNotFound` | Low | Fuzzy search returned no matches. Ask for clarification (full name, DOB, phone). |
| `PatientAmbiguous` | Low | Multiple patients match. Present options with disambiguating info (DOB, last visit). |
| `ProviderUnavailable` | Medium | Provider has no availability in requested range. Suggest alternative providers or expanded date range. |
| `RoomConflict` | High | Room double-booked (should not happen â€” indicates data corruption). Create escalation, attempt auto-reassign. |
| `ProcedureNotFound` | Low | CDT code or procedure name not recognized. Ask for clarification, suggest common matches. |
| `ScheduleBlockConflict` | Medium | Requested time falls in a blocked period. Explain the block, suggest adjacent times. |
| `RecallScanFailed` | Medium | Nightly recall scan encountered errors. Log details, retry in 1 hour, alert if persistent. |
| `WaitlistMatchFailed` | Low | No waitlist candidates match an open slot. Log, leave slot open on schedule. |
| `ConfirmationDeliveryFailed` | Medium | Relay reports message delivery failure. Flag appointment as "confirmation_undeliverable", create staff task. |
| `DatabaseWriteFailed` | Critical | SQLite write failed. Retry once, if persistent, queue the operation and create immediate staff alert. |
| `StaleDataDetected` | Medium | Concurrent modification detected (appointment changed since read). Re-read, re-evaluate, retry. |

### Graceful Degradation

If Stella's LLM interface is unavailable (all providers down), she operates in deterministic-only mode:

**Available in deterministic mode:**
- Slot validation (specific date/time check)
- Schedule display (return raw appointment data)
- Appointment status updates (check-in, complete, no-show)
- Waitlist matching (algorithmic, no NL needed)
- Recall scan (batch process, no NL needed)
- Confirmation sequences (template-based via Relay)

**Unavailable without LLM:**
- Natural language booking requests ("book Mrs. Johnson for a cleaning next week")
- Ambiguous request interpretation
- Intelligent response generation
- Complex optimization suggestions with natural language explanations

Staff can still use the UI directly for all scheduling operations when the LLM is down.

---

## 22. Permission Configuration

### Default Permission Levels for Scheduling Actions

| Action | Default Permission | Rationale |
|---|---|---|
| Book standard appointment | Autonomous | Core workflow, well-constrained |
| Book complex procedure (>90 min) | Supervised | Higher revenue impact, staff should confirm |
| Cancel appointment (patient request) | Autonomous | Patient's right, clear intent |
| Cancel appointment (practice-initiated) | Supervised | Affects patient, staff should approve |
| Reschedule within same week | Autonomous | Minor change, low risk |
| Reschedule to different week | Supervised | Larger change, patient may not realize impact |
| Add to waitlist | Autonomous | No schedule modification, patient benefit |
| Fill from waitlist (cancellation recovery) | Autonomous | Time-sensitive, high value |
| Double-book slot | Supervised | Complex, requires judgment |
| Create schedule block | Supervised | Affects provider availability |
| Create schedule override (PTO) | Supervised | Major impact on schedule |
| Auto-optimize tomorrow's schedule | Supervised (default) or Autonomous (if configured) | Moving appointments is sensitive |
| Mark no-show | Autonomous | Factual observation |
| Flag patient for deposit requirement | Supervised | Policy change for specific patient |
| Send recall outreach | Autonomous | Standard workflow, patient benefit |

All permission levels are configurable per practice in `practice_config.agent_permissions.stella`.

---

## 23. Sample Interactions

### Interaction 1: Simple Booking

**User (Front Desk):** "Book Sarah Davis for a cleaning next Tuesday with her usual hygienist."

**Stella's internal process:**
```
1. Classify: scheduling.book (deterministic match, confidence 0.97)
2. Resolve patient: "Sarah Davis" â†’ fuzzy match â†’ Patient #4821 (Sarah M. Davis)
3. Resolve procedure: "cleaning" â†’ check patient history â†’ 
   last visit was D1110 (adult prophylaxis), perio status normal â†’ D1110
4. Resolve provider: "usual hygienist" â†’ check booking history â†’ 
   last 4 cleanings with Jennifer Wilson (Hygienist) â†’ provider confirmed
5. Resolve date: "next Tuesday" â†’ February 10, 2026
6. Find slots: Jennifer Wilson, Feb 10, D1110 (45 min with setup/cleanup)
   â†’ 3 available slots: 9:00 AM (score 0.91), 10:30 AM (score 0.87), 2:00 PM (score 0.82)
7. Present: "Sarah's usual hygienist Jennifer has availability next Tuesday.
   Best options: 9:00 AM, 10:30 AM, or 2:00 PM. Which works best?"
```

**User:** "9 AM."

**Stella:**
```
8. Book: Create appointment â€” Sarah Davis, D1110, Jennifer Wilson, Feb 10 9:00 AM, Hygiene Room A
9. Events: appointment.booked â†’ Relay sends confirmation, Vera checks insurance
10. Response: "Done! Sarah Davis is booked for a cleaning with Jennifer on 
    Tuesday, February 10th at 9:00 AM. Confirmation text is on its way."
```

### Interaction 2: Complex Multi-Constraint Booking

**User (Office Manager):** "Mrs. Chen needs a crown on tooth 14. She can only do mornings, prefers Dr. Martinez, and her Delta Dental needs to pre-authorize it first."

**Stella's internal process:**
```
1. Classify: scheduling.book (with insurance constraint)
2. Resolve: Patient "Mrs. Chen" â†’ Patient #2109 (Linda Chen)
3. Resolve procedure: "crown on tooth 14" â†’ D2740 (porcelain/ceramic crown)
   Duration: 90 min (Dr. Martinez's learned average: 95 min â†’ use 95 min)
   Requires: operatory room, x-ray equipment
4. Resolve provider: "Dr. Martinez" â†’ confirmed, has D2740 capability (primary)
5. Constraints:
   - Morning only (patient preference, soft)
   - Dr. Martinez (patient preference, soft)
   - Pre-auth required (advisory â€” can book but flag)
6. Find morning slots for Dr. Martinez with operatory + x-ray, 95+ min window
   â†’ Results: Feb 12 8:00 AM (score 0.94), Feb 14 8:30 AM (score 0.88), 
              Feb 19 9:00 AM (score 0.85)
7. Insurance note: Pre-auth not yet obtained
```

**Stella's response:** "Dr. Martinez has morning availability for Mrs. Chen's crown on tooth 14. Best options: Wednesday Feb 12 at 8:00 AM, Friday Feb 14 at 8:30 AM, or Wednesday Feb 19 at 9:00 AM. Note: Delta Dental pre-authorization hasn't been submitted yet â€” I'll flag Vera to start that process. We can book now and the pre-auth should come through before the appointment."

**Events emitted:**
- `appointment.booked` (once user selects slot)
- `insurance.preauth_needed` (triggers Vera to submit pre-authorization)

### Interaction 3: Cancellation Recovery (Autonomous)

**Trigger:** `appointment.cancelled` event â€” Dr. Patel's 2:30 PM patient cancelled a crown prep (D2750, production value $950).

**Stella's autonomous process:**
```
1. Evaluate slot: $950 production, prime afternoon slot â†’ RECOVER
2. Match waitlist:
   - Maria Gonzalez: needs crown (D2740), any provider, flexible schedule, 30-min notice OK â†’ score 0.92
   - James Park: needs crown (D2740), prefers mornings but "any time" acceptable â†’ score 0.78
   - Lisa Thompson: needs filling (D2150), any provider, 1-hour notice â†’ score 0.71
   - Robert Kim: needs extraction (D7140), Dr. Patel only â†’ score 0.65
   - Amy Chen: needs crown (D2740), afternoons preferred â†’ score 0.88
3. Select top 5 candidates, ordered: Maria, Amy, James, Lisa, Robert
4. Emit waitlist.slot_offered for all 5 simultaneously
5. Relay sends SMS to all 5: "Dr. Patel has a 2:30 PM opening today. Reply YES to book!"
```

**60 seconds later:** Amy Chen replies "YES"

```
6. Book Amy Chen for 2:30 PM with Dr. Patel, crown D2740
7. Update other waitlist entries back to "active"
8. Relay: Send confirmation to Amy, "slot filled" to others
9. Vera: Set up billing for Amy's crown, cancel original patient billing prep
10. Proactive notification to staff: "I filled Dr. Patel's 2:30 PM cancellation â€” 
    Amy Chen confirmed for a crown. $950 in production recovered."
```

### Interaction 4: Schedule Query

**User:** "What does Dr. Patel's schedule look like tomorrow?"

**Stella's process:**
```
1. Classify: scheduling.query (deterministic, 0.95)
2. Resolve: "Dr. Patel" â†’ Provider #12 (Dr. Ravi Patel, DDS)
3. Resolve: "tomorrow" â†’ February 6, 2026
4. Fetch: All appointments for Dr. Patel on Feb 6, sorted by time
5. Calculate: utilization %, production total, gap analysis
```

**Stella's response:** "Dr. Patel's schedule for tomorrow, Thursday Feb 6:

8:00 AM â€” Sarah Johnson (D2740, Crown prep) â€” CONFIRMED
9:30 AM â€” Michael Brown (D0120, Periodic exam) â€” UNCONFIRMED âš ï¸
10:00 AM â€” [30 min gap]
10:30 AM â€” Jennifer Lee (D3310, Root canal) â€” CONFIRMED
12:00 PM â€” Lunch
1:00 PM â€” David Wilson (D2150, Filling) â€” CONFIRMED
2:00 PM â€” [60 min gap]
3:00 PM â€” Karen Martinez (D7140, Extraction) â€” CONFIRMED
4:00 PM â€” [open until 5:00 PM]

Utilization: 72% (target: 85%). Two gaps totaling 90 minutes. Michael Brown hasn't confirmed â€” want me to send another reminder? I also have 3 waitlist patients who could fill the 2:00 PM gap."

### Interaction 5: Recall Overdue Query

**User:** "How many patients are overdue for their cleaning?"

**Stella's process:**
```
1. Classify: scheduling.recall_query
2. Query recall_schedule where status = "overdue"
3. Aggregate by overdue duration buckets
```

**Stella's response:** "You have 47 patients overdue for hygiene recall:

12 patients â€” 1-2 months overdue (outreach in progress)
18 patients â€” 2-4 months overdue (escalated outreach)
11 patients â€” 4-6 months overdue (flagged for staff follow-up)
6 patients â€” 6+ months overdue (at risk of becoming inactive)

The recall outreach sequence has contacted all 47. 23 have received all 3 automated messages without response â€” those are the ones flagged for your team. Want me to pull up that list?"

---

## 24. Pseudocode â€” Key Workflows

### Stella's Main Task Handler

```
FUNCTION handle_task(task: AgentTask):
  MATCH task.action:
    "scheduling.book" => handle_booking(task)
    "scheduling.reschedule" => handle_reschedule(task)
    "scheduling.cancel" => handle_cancellation(task)
    "scheduling.query" => handle_query(task)
    "scheduling.find_slots" => handle_find_slots(task)
    "scheduling.waitlist_add" => handle_waitlist_add(task)
    "scheduling.waitlist_query" => handle_waitlist_query(task)
    "scheduling.recall_query" => handle_recall_query(task)
    "scheduling.check_in" => handle_check_in(task)
    "scheduling.complete" => handle_complete(task)
    "scheduling.no_show" => handle_no_show(task)
    "scheduling.provider_schedule" => handle_provider_schedule_query(task)
    "scheduling.optimize" => handle_optimization(task)
    _ => {
      log_error("Unknown scheduling action: {task.action}")
      RETURN TaskResult::error("I don't know how to handle that scheduling request.")
    }

FUNCTION handle_booking(task: AgentTask):
  // 1. Extract entities from task payload (patient, procedure, provider, date)
  patient = resolve_patient(task.payload.patient_identifier)
  IF patient.is_ambiguous:
    RETURN TaskResult::clarification_needed(patient.options)
  
  procedure = resolve_procedure(task.payload.procedure_identifier, patient)
  IF procedure.is_ambiguous:
    RETURN TaskResult::clarification_needed(procedure.options)
  
  provider = resolve_provider(task.payload.provider_identifier, procedure)
  date_range = resolve_date_range(task.payload.date_expression)
  
  // 2. Check permission
  permission = check_permission("scheduling.book", {
    procedure_complexity: procedure.complexity,
    is_new_patient: patient.is_new,
    override_required: task.payload.requires_override
  })
  IF permission == "Escalated":
    RETURN TaskResult::escalated(reason: permission.reason)
  IF permission == "Supervised":
    create_approval_request(task, patient, procedure, provider)
    RETURN TaskResult::awaiting_approval()
  
  // 3. Find slots
  IF task.payload.specific_datetime:
    result = validate_specific_slot(provider, task.payload.specific_datetime, procedure, patient.id)
    IF result.is_available:
      // Book directly if user requested a specific time
      appointment = create_appointment(patient, procedure, provider, task.payload.specific_datetime)
      emit_post_booking_events(appointment)
      RETURN TaskResult::success(format_booking_confirmation(appointment))
    ELSE:
      RETURN TaskResult::alternatives(result.reasons, result.alternatives)
  ELSE:
    slots = find_available_slots(BookingRequest {
      procedure_code: procedure.code,
      patient_id: patient.id,
      preferred_provider: provider,
      date_range: date_range,
      preferred_times: task.payload.time_preference,
      max_results: 5
    })
    IF slots.is_empty():
      RETURN TaskResult::no_availability(suggest_expanding_search(date_range, provider))
    RETURN TaskResult::options(format_slot_options(slots))

FUNCTION handle_cancellation_recovery(cancelled_appointment):
  IF NOT should_recover_slot(cancelled_appointment):
    log("Slot not valuable enough to recover: {cancelled_appointment.id}")
    RETURN
  
  // Find waitlist matches
  matches = match_waitlist_to_slot(OpenSlot::from(cancelled_appointment))
  
  IF matches.is_empty():
    // Try recall-eligible patients
    recall_matches = find_recall_matches(cancelled_appointment)
    IF recall_matches.is_empty():
      log("No candidates to fill slot: {cancelled_appointment.id}")
      RETURN
    matches = recall_matches
  
  // Initiate simultaneous outreach
  FOR EACH match IN matches:
    match.waitlist_entry.status = "offered"
    match.waitlist_entry.offered_count += 1
    match.waitlist_entry.last_offered_at = now()
  
  emit("waitlist.slot_available", {
    open_slot: OpenSlot::from(cancelled_appointment),
    candidates: matches,
    response_deadline: now() + 60_minutes
  })
  
  // Set up response handler
  schedule_timeout(60_minutes, || {
    check_recovery_status(cancelled_appointment.id)
  })
```

### Recall Scan Pseudocode

```
FUNCTION run_nightly_recall_scan():
  log("Starting nightly recall scan")
  
  active_patients = get_active_patients()
  stats = { due: 0, scheduled: 0, outreach: 0, overdue: 0 }
  
  FOR EACH patient IN active_patients:
    recalls = get_recall_schedules(patient.id)
    
    FOR EACH recall IN recalls:
      // Update due date if last visit completed
      IF recall.last_completed_date:
        recall.next_due_date = recall.last_completed_date + recall.interval_months
      
      // Check current status
      IF has_future_appointment(patient.id, recall.recall_type):
        recall.status = "scheduled"
        stats.scheduled += 1
        CONTINUE
      
      days_until_due = (recall.next_due_date - today).days
      
      IF days_until_due <= 30 AND days_until_due > 0:
        recall.status = "due"
        stats.due += 1
        advance_outreach_if_ready(recall)
      
      ELIF days_until_due <= 0:
        recall.status = "overdue"
        stats.overdue += 1
        advance_outreach_if_ready(recall)
      
      save(recall)
  
  emit("recall.scan_completed", stats)
  save_observation("practice:scheduling", 
    "Recall scan: {stats.due} due, {stats.scheduled} scheduled, {stats.overdue} overdue")
  log("Recall scan complete: {stats}")
```

---

## 25. Performance Targets

| Operation | Target | Measurement |
|---|---|---|
| Slot validation (specific time) | <10ms | Time from request to yes/no response |
| Slot search (5-day range, single provider) | <50ms | Time to return ranked slot list |
| Slot search (5-day range, all providers) | <200ms | Time to return ranked slot list |
| Appointment creation (DB write) | <20ms | SQLite insert + index update |
| Waitlist matching | <30ms | Time to find and score matching candidates |
| Recall scan (full practice, 2000 patients) | <10s | Nightly batch processing |
| Schedule optimization (single day) | <500ms | Nightly gap/production analysis |
| No-show risk calculation | <5ms | Per-patient score computation |
| Cancellation recovery launch | <2s | From cancellation event to outreach emission |
| End-to-end booking (simple) | <3s | From user request to confirmation (includes LLM) |
| End-to-end booking (complex/multi-constraint) | <5s | Includes LLM + extended search |
| Provider availability computation | <50ms | Single provider, single day |
| Room assignment | <10ms | Best available room selection |
| Memory footprint (idle) | <20MB | Stella's runtime allocation |
| Memory footprint (active, 3 concurrent tasks) | <40MB | Peak during parallel processing |

### Accuracy Targets

| Metric | Target |
|---|---|
| Slot availability accuracy | 100% (no false positives â€” never show a slot that's actually booked) |
| Constraint satisfaction | 100% for hard constraints, >90% for soft constraints |
| Duration prediction accuracy | Within 10 minutes of actual for >80% of appointments |
| No-show prediction accuracy | >70% AUC (area under ROC curve) |
| Recall scan coverage | 100% of active patients scanned nightly |
| Waitlist match relevance | >80% of offered slots accepted by the first batch of candidates |

---

## 26. Edge Cases & Failure Scenarios

### Edge Case 1: Race Condition â€” Two Users Booking Same Slot

**Scenario:** Front desk user A and online booking patient B both try to book the same 10:00 AM slot simultaneously.

**Resolution:** Stella's lane queue processes tasks serially. The first task to arrive books the slot. The second task finds the slot occupied, re-runs the slot finder, and presents alternatives. No double-booking occurs.

### Edge Case 2: Provider Schedule Change After Appointments Booked

**Scenario:** Dr. Patel has 8 appointments on Thursday. Office manager marks him absent for that day.

**Resolution:** Stella's provider absence workflow:
1. Identify all 8 affected appointments.
2. For each: check if another qualified provider is available at the same time.
   - If yes and patient is flexible â†’ create supervised reschedule proposal.
   - If no â†’ mark for cancellation with priority rebooking.
3. Present the full impact to the office manager for approval before executing any changes.
4. After approval, execute changes and trigger Relay to notify all patients.

### Edge Case 3: Patient With Active Treatment Plan Requests Booking

**Scenario:** Patient calls to book "the next step" of their treatment. They have a treatment plan with 3 remaining procedures in a specific sequence.

**Resolution:** Stella checks the patient's treatment plan, identifies the next procedure in sequence (e.g., D2950 core buildup must come before D2740 crown). Books for the correct procedure, not just what the patient described. If the patient requests an out-of-sequence procedure, Stella flags it and suggests the correct order.

### Edge Case 4: Midnight Boundary â€” Appointment Spanning End of Business

**Scenario:** Request to book a 90-minute procedure starting at 4:00 PM when the practice closes at 5:00 PM.

**Resolution:** Hard constraint â€” duration doesn't fit within working hours. Stella rejects and suggests: "That procedure needs 90 minutes, but the office closes at 5:00 PM. Would an earlier time work? I have 2:30 PM or 3:00 PM available, or we could look at another day."

### Edge Case 5: Recall Due But Patient Has Outstanding Balance

**Scenario:** Patient is due for 6-month recall, but Vera's records show a $500 outstanding balance.

**Resolution:** Stella does not check financial records (domain isolation). She proceeds with recall outreach normally. If the practice has configured a "hold recall for outstanding balance" policy, Vera flags the patient and Stella receives a `patient.billing_hold` event that pauses outreach until resolved.

### Edge Case 6: Waitlist Patient Responds After Slot Already Filled

**Scenario:** 3 patients are offered a cancellation slot. Patient A responds "YES" first and is booked. 5 minutes later, Patient B also responds "YES."

**Resolution:** Patient B's response arrives after the slot is filled. Stella:
1. Checks that the appointment is already booked.
2. Responds via Relay: "Thanks for your quick response! That slot was just filled. You're still on our waitlist â€” we'll text you the next time a matching slot opens."
3. Updates Patient B's waitlist score positively (they respond quickly).

### Edge Case 7: Circular Reschedule Dependency

**Scenario:** Patient A wants to move to Patient B's slot. Patient B wants to move to Patient C's slot. Patient C wants to move to Patient A's slot.

**Resolution:** Stella detects circular dependencies in reschedule requests. She presents the entire swap as a single supervised operation: "I can do a three-way swap: move A to B's time, B to C's time, and C to A's time. All three patients would need to agree. Want me to reach out to them?"

### Edge Case 8: Equipment Maintenance During Booked Appointments

**Scenario:** The CBCT machine breaks down. 3 appointments today require CBCT imaging.

**Resolution:** Staff marks equipment as "out_of_service." Stella:
1. Identifies all appointments requiring that equipment (today and future).
2. For today's appointments: checks if the procedure can proceed without CBCT or with alternative imaging.
3. If not: creates supervised reschedule proposals.
4. For future appointments: checks when equipment is expected back, flags if appointments need moving.

---

## Appendix A: Procedure Duration Matrix

Default durations for common dental procedures. These are starting values â€” Stella learns actual practice-specific durations over time.

| CDT Code | Procedure | Default Duration | Setup | Cleanup | Provider Type |
|---|---|---|---|---|---|
| D0120 | Periodic oral evaluation | 15 min | 5 min | 5 min | Dentist |
| D0140 | Limited oral evaluation (emergency) | 20 min | 5 min | 5 min | Dentist |
| D0150 | Comprehensive oral evaluation (new patient) | 30 min | 5 min | 5 min | Dentist |
| D0210 | Full mouth x-rays | 20 min | 5 min | 5 min | Hygienist/Assistant |
| D0220 | Periapical x-ray | 10 min | 3 min | 3 min | Hygienist/Assistant |
| D0274 | Bitewing x-rays (4 films) | 15 min | 3 min | 3 min | Hygienist/Assistant |
| D0330 | Panoramic x-ray | 15 min | 5 min | 5 min | Hygienist/Assistant |
| D1110 | Adult prophylaxis (cleaning) | 45 min | 5 min | 10 min | Hygienist |
| D1120 | Child prophylaxis | 30 min | 5 min | 10 min | Hygienist |
| D1206 | Fluoride varnish | 5 min | 2 min | 3 min | Hygienist |
| D1351 | Sealant (per tooth) | 10 min | 3 min | 3 min | Hygienist/Dentist |
| D2140 | Amalgam filling (1 surface) | 30 min | 5 min | 10 min | Dentist |
| D2150 | Amalgam filling (2 surfaces) | 40 min | 5 min | 10 min | Dentist |
| D2330 | Composite filling (1 surface, anterior) | 30 min | 5 min | 10 min | Dentist |
| D2331 | Composite filling (2 surfaces, anterior) | 40 min | 5 min | 10 min | Dentist |
| D2391 | Composite filling (1 surface, posterior) | 35 min | 5 min | 10 min | Dentist |
| D2740 | Porcelain/ceramic crown | 90 min | 10 min | 15 min | Dentist |
| D2750 | Porcelain fused to metal crown | 90 min | 10 min | 15 min | Dentist |
| D2950 | Core buildup | 30 min | 5 min | 10 min | Dentist |
| D3310 | Root canal (anterior) | 60 min | 10 min | 15 min | Dentist/Endodontist |
| D3320 | Root canal (bicuspid) | 75 min | 10 min | 15 min | Dentist/Endodontist |
| D3330 | Root canal (molar) | 90 min | 10 min | 15 min | Dentist/Endodontist |
| D4341 | Scaling & root planing (per quadrant) | 60 min | 5 min | 10 min | Hygienist |
| D4910 | Periodontal maintenance | 50 min | 5 min | 10 min | Hygienist |
| D5110 | Complete upper denture | 45 min | 10 min | 10 min | Dentist |
| D5120 | Complete lower denture | 45 min | 10 min | 10 min | Dentist |
| D6010 | Implant (endosseous) | 120 min | 15 min | 15 min | Dentist/Surgeon |
| D7140 | Extraction (simple) | 30 min | 5 min | 10 min | Dentist |
| D7210 | Extraction (surgical) | 45 min | 10 min | 15 min | Dentist/Surgeon |
| D7240 | Impacted tooth extraction | 60 min | 10 min | 15 min | Surgeon |
| D9110 | Emergency palliative treatment | 20 min | 5 min | 5 min | Dentist |
| D9230 | Nitrous oxide | 0 min | 5 min | 10 min | Dentist (concurrent) |
| D9310 | Consultation | 30 min | 5 min | 5 min | Dentist |

---

## Appendix B: Scheduling Configuration Reference

Complete configuration schema for Stella:

```json
{
  "scheduling": {
    "slot_increment_minutes": 10,
    "default_search_range_days": 14,
    "max_search_range_days": 90,
    "max_results_per_search": 10,
    
    "buffer_time": {
      "provider_transition_minutes": 5,
      "default_setup_minutes": 5,
      "default_cleanup_minutes": 10,
      "enforce_as": "soft"
    },
    
    "production_targets": {
      "default_daily_target": 3500,
      "high_production_threshold": 300,
      "medium_production_threshold": 150
    },
    
    "waitlist": {
      "outreach_count": 5,
      "response_timeout_minutes": 60,
      "max_offered_count": 5,
      "entry_expiry_days": 90,
      "simultaneous_outreach": true
    },
    
    "cancellation_recovery": {
      "enabled": true,
      "min_hours_before_slot": 2,
      "high_value_threshold": 300,
      "medium_value_threshold": 150,
      "expand_to_recall_after_minutes": 120
    },
    
    "no_show": {
      "default_risk": 0.10,
      "double_book_threshold": 0.30,
      "deposit_required_threshold": 3,
      "grace_period_minutes": 15
    },
    
    "recall": {
      "scheduling_window_days": 30,
      "outreach_stages": [
        { "stage": 1, "wait_days": 0, "channel": "sms", "template": "recall_link" },
        { "stage": 2, "wait_days": 5, "channel": "sms", "template": "recall_reminder" },
        { "stage": 3, "wait_days": 7, "channel": "sms", "template": "recall_personal" },
        { "stage": 4, "wait_days": 7, "channel": "staff_task", "template": "recall_escalation" }
      ],
      "refused_retry_months": 6,
      "inactive_after_stages": 4
    },
    
    "confirmation": {
      "stages": [
        { "hours_before": 168, "channel": "sms", "template": "confirm_7d" },
        { "hours_before": 48, "channel": "sms", "template": "confirm_48h" },
        { "hours_before": 24, "channel": "sms", "template": "confirm_24h" }
      ],
      "enhanced_stages": [
        { "hours_before": 2, "channel": "sms", "template": "confirm_2h" }
      ],
      "enhanced_risk_threshold": 0.15
    },
    
    "double_booking": {
      "enabled": false,
      "max_concurrent_patients": 2,
      "requires_assistant": true,
      "permission_level": "supervised",
      "allowed_combinations": []
    },
    
    "emergency_slots": {
      "enabled": true,
      "slots_per_day": 1,
      "default_duration_minutes": 30,
      "release_time": "14:00",
      "days_of_week": [1, 2, 3, 4, 5]
    },
    
    "optimization": {
      "nightly_run_time": "17:00",
      "auto_apply_safe_changes": false,
      "min_gap_minutes_to_flag": 15,
      "utilization_target_pct": 85
    },
    
    "scoring_weights": {
      "preferred_provider": 1.0,
      "preferred_time": 0.9,
      "provider_continuity": 0.7,
      "production_balance": 0.6,
      "gap_fill": 0.8,
      "gap_creation_penalty": 0.5,
      "buffer_satisfaction": 0.4,
      "urgency": 0.9,
      "complexity_timing": 0.3
    }
  }
}
```

---

## Appendix C: Recall Interval Taxonomy

Standard recall intervals for dental procedures. Practices can customize these during onboarding.

| Recall Type | Default Interval | Typical CDT Code | Patient Criteria |
|---|---|---|---|
| Standard hygiene | 6 months | D1110 | Healthy periodontium, no active disease |
| Perio maintenance | 3 months | D4910 | History of periodontal disease, post-SRP |
| Perio maintenance (moderate) | 4 months | D4910 | Stable but elevated periodontal risk |
| Child prophylaxis | 6 months | D1120 | Pediatric patients |
| Annual comprehensive exam | 12 months | D0150 | All patients (in addition to periodic exams) |
| Periodic evaluation | 6 months | D0120 | All patients at hygiene visits |
| Fluoride treatment (child) | 6 months | D1206 | Patients under 18 |
| Fluoride treatment (high risk adult) | 6 months | D1206 | High caries risk adults |
| Panoramic x-ray | 36-60 months | D0330 | Per ADA guidelines, varies by risk |
| Full mouth x-rays | 36-60 months | D0210 | Per ADA guidelines, varies by risk |
| Bitewing x-rays | 6-12 months | D0274 | At hygiene visits, frequency per risk level |
| Orthodontic check | 4-8 weeks | D8670 | Active orthodontic patients |
| Post-surgical follow-up | 1-2 weeks | D0170 | After surgical procedures |
| Implant maintenance | 6 months | D6080 | Patients with implants |
| Night guard check | 12 months | â€” | Patients with bruxism/TMJ |
| Denture adjustment | 12 months | D5410/D5411 | Denture patients |

---

*End of 11-AGENT-SCHEDULING.md*

*Stella is the first agent built (Phase 1, Months 1â€“3). Her core slot-finding engine and appointment CRUD are the foundation on which all other scheduling features are built. Start with smart booking and basic recall, then layer cancellation recovery, no-show prediction, and optimization as the product matures.*
