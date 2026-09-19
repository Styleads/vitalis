"""
engine/types.py
===============
Enums, dataclasses and named types for the MedFlow simulation engine.
All types are defined from spec §4.  No logic lives here.

ResourceType is a str-enum so it serialises as a plain string key in JSON
(C and D need this) and can still be used as a Python enum member.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ResourceType(str, Enum):
    """Spec §4: resource kinds.  AMBULANCE exists but has no default v1 bundle."""
    BED       = "BED"
    ICU_BED   = "ICU_BED"
    OR        = "OR"
    DOCTOR    = "DOCTOR"
    NURSE     = "NURSE"
    AMBULANCE = "AMBULANCE"


class UnitStatus(str, Enum):
    FREE     = "FREE"
    OCCUPIED = "OCCUPIED"
    FAILED   = "FAILED"
    OFF      = "OFF"


class PatientStatus(str, Enum):
    WAITING      = "WAITING"
    IN_TREATMENT = "IN_TREATMENT"
    DISCHARGED   = "DISCHARGED"


class ArrivalMode(str, Enum):
    WALK_IN   = "WALK_IN"
    AMBULANCE = "AMBULANCE"


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------

@dataclass
class Unit:
    """A single allocatable resource unit.  Spec §4."""
    id:          int
    type:        ResourceType
    status:      str            # UnitStatus value; kept str for JSON friendliness
    owner:       Optional[int]  # patient id, non-None iff OCCUPIED
    pending_off: bool = False   # only ever True on an OCCUPIED unit


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------

@dataclass
class Patient:
    """Full mutable patient record owned by the engine.  Spec §4."""
    id:                    int
    arrival_time:          int
    urgency:               int                          # 1 (critical) .. 5 (non-urgent)
    required:              dict[ResourceType, int]      # resource bundle
    service_time:          int                          # simulation truth (seconds)
    remaining_service:     int                          # seconds left
    predicted_service_time: Optional[int]              # ML hook output; engine never uses for timing
    arrival_mode:          str                          # ArrivalMode value
    department:            str
    features:              dict                         # free-form for ML
    status:                str                          # PatientStatus value
    start_time:            Optional[int]               # first treatment start
    end_time:              Optional[int]
    assigned:              list[int]                   # unit ids; empty unless IN_TREATMENT
    interruptions:         int
    segment_start:         Optional[int]               # current segment start (for P-FAIL)
    token:                 int                         # bumped on every assign/interrupt


# ---------------------------------------------------------------------------
# PatientView — frozen read-only projection passed to strategies
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatientView:
    """
    Spec §4: what strategies see for each patient.
    wait_s = now - arrival_time - (service_time - remaining_service)
    """
    id:                    int
    urgency:               int
    arrival_time:          int
    wait_s:                int
    required:              dict           # not typed with ResourceType so it's JSON-safe
    predicted_service_time: Optional[int]
    remaining_service:     int
    arrival_mode:          str
    department:            str
    interruptions:         int


# ---------------------------------------------------------------------------
# StateView — frozen read-only engine state passed to strategies
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StateView:
    """
    Spec §4 (literal field names, locked — B imports these).
    free:  mapping ResourceType → count of FREE units
    total: mapping ResourceType → count of active (not FAILED/OFF) units
    """
    clock:        int
    free:         dict          # ResourceType → int
    total:        dict          # ResourceType → int (active = FREE + OCCUPIED)
    waiting:      tuple         # tuple[PatientView, ...]
    in_treatment: int
    flags:        dict          # e.g. {"arrival_multiplier": 1.0}


# ---------------------------------------------------------------------------
# Event — internal heap element
# ---------------------------------------------------------------------------

@dataclass(order=True)
class Event:
    """
    Spec §5: heap element ordered by (time, kind_rank, seq).
    kind and payload are excluded from ordering via field(compare=False).
    """
    time:      int
    kind_rank: int
    seq:       int
    kind:      str  = field(compare=False)
    payload:   tuple = field(compare=False)
