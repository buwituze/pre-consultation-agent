"""
routing.py — Queue and department routing logic.

A rule engine that maps priority + suspected issue → department + queue position.
No ML required. Rules are explicit, auditable, and easy to update.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RoutingDecision:
    department:    str           # Where the patient should go
    queue:         str           # Which queue they join
    queue_number:  int           # Their position in that queue
    urgency_label: str           # Human-readable label for the patient
    location_hint: str           # Specific desk or waiting area


# ---------------------------------------------------------------------------
# Department rules
# Priority + suspected issue → department
# ---------------------------------------------------------------------------
_DEPARTMENT_RULES: dict[tuple, str] = {
    # HIGH priority always goes to Emergency regardless of issue
    ("HIGH",   "*"):                                    "Emergency",

    # MEDIUM by issue category
    ("MEDIUM", "cardiorespiratory-related complaint"):  "Emergency",
    ("MEDIUM", "neurological-related complaint"):       "General Medicine",
    ("MEDIUM", "gastrointestinal-related complaint"):   "General Medicine",
    ("MEDIUM", "musculoskeletal-related complaint"):    "Orthopaedics",
    ("MEDIUM", "dermatological-related complaint"):     "Dermatology",
    ("MEDIUM", "urological-related complaint"):         "Urology",
    ("MEDIUM", "ENT-related complaint"):                "ENT",
    ("MEDIUM", "general or systemic complaint"):        "General Medicine",
    ("MEDIUM", "mental health-related complaint"):      "Mental Health",
    ("MEDIUM", "obstetric or gynaecological complaint"):"Gynaecology",
    ("MEDIUM", "paediatric-related complaint"):         "Paediatrics",
    ("MEDIUM", "unclear or unclassifiable complaint"):  "General Medicine",

    # LOW by issue category (same mapping, different waiting area)
    ("LOW",    "cardiorespiratory-related complaint"):  "General Medicine",
    ("LOW",    "neurological-related complaint"):       "General Medicine",
    ("LOW",    "gastrointestinal-related complaint"):   "General Medicine",
    ("LOW",    "musculoskeletal-related complaint"):    "General Medicine",
    ("LOW",    "dermatological-related complaint"):     "Dermatology",
    ("LOW",    "urological-related complaint"):         "General Medicine",
    ("LOW",    "ENT-related complaint"):                "ENT",
    ("LOW",    "general or systemic complaint"):        "General Medicine",
    ("LOW",    "mental health-related complaint"):      "Mental Health",
    ("LOW",    "obstetric or gynaecological complaint"):"Gynaecology",
    ("LOW",    "paediatric-related complaint"):         "Paediatrics",
    ("LOW",    "unclear or unclassifiable complaint"):  "General Medicine",
}

# Department → queue name + waiting area description
_DEPARTMENT_CONFIG: dict[str, dict] = {
    "Emergency":      {"queue": "emergency",    "location": "Emergency Department — present to the desk immediately"},
    "General Medicine":{"queue": "general",     "location": "Waiting Area A — General Outpatient"},
    "Orthopaedics":   {"queue": "ortho",        "location": "Waiting Area B — Orthopaedics"},
    "Dermatology":    {"queue": "derm",         "location": "Waiting Area C — Dermatology"},
    "Urology":        {"queue": "urology",      "location": "Waiting Area D — Urology"},
    "ENT":            {"queue": "ent",           "location": "Waiting Area E — ENT"},
    "Mental Health":  {"queue": "mh",            "location": "Waiting Area F — Mental Health"},
    "Gynaecology":    {"queue": "gynae",         "location": "Waiting Area G — Gynaecology"},
    "Paediatrics":    {"queue": "paediatrics",   "location": "Waiting Area H — Paediatrics"},
}

_URGENCY_LABELS = {
    "HIGH":   "Urgent",
    "MEDIUM": "Standard",
    "LOW":    "Routine",
}

# In-memory queue counters — replace with DB-backed counters in production
_queue_counters: dict[str, int] = {config["queue"]: 0 for config in _DEPARTMENT_CONFIG.values()}


def _resolve_department(priority: str, suspected_issue: str) -> str:
    """Match priority + issue to a department using the rules table."""
    # Exact match first
    key = (priority, suspected_issue)
    if key in _DEPARTMENT_RULES:
        return _DEPARTMENT_RULES[key]
    # HIGH wildcard
    if priority == "HIGH":
        return _DEPARTMENT_RULES[("HIGH", "*")]
    # Default fallback
    return "General Medicine"


def _next_queue_number(queue_name: str) -> int:
    """Increment and return the next number for a given queue."""
    _queue_counters[queue_name] = _queue_counters.get(queue_name, 0) + 1
    return _queue_counters[queue_name]


def assign_routing(priority: str, suspected_issue: str) -> RoutingDecision:
    """
    Assign a department, queue, and position to a patient.

    Args:
        priority:        "HIGH" | "MEDIUM" | "LOW"
        suspected_issue: Issue category string from Model D.

    Returns:
        RoutingDecision with all routing details.
    """
    department = _resolve_department(priority, suspected_issue)
    config     = _DEPARTMENT_CONFIG.get(department, _DEPARTMENT_CONFIG["General Medicine"])
    queue_name = config["queue"]
    number     = _next_queue_number(queue_name)

    return RoutingDecision(
        department    = department,
        queue         = queue_name,
        queue_number  = number,
        urgency_label = _URGENCY_LABELS.get(priority, "Standard"),
        location_hint = config["location"],
    )


def get_queue_lengths() -> dict[str, int]:
    """Return current queue lengths for all departments."""
    return dict(_queue_counters)


def reset_queues() -> None:
    """Reset all queue counters (e.g. at start of day)."""
    for key in _queue_counters:
        _queue_counters[key] = 0
