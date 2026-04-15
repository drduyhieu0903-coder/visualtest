"""
HIDU EWS - Clinical Data Models
Inspired by HL7 FHIR standard for healthcare interoperability
"""

from dataclasses import dataclass, field
from typing import Optional, List
import json


@dataclass
class ReferenceRange:
    """Dynamic reference range - never hardcoded, always from source document"""
    low: Optional[float]
    high: Optional[float]
    text: str  # Original text preserved for audit trail

    def to_dict(self):
        return {"low": self.low, "high": self.high, "text": self.text}


@dataclass
class Observation:
    """
    Single lab observation - maps to FHIR Observation resource
    Flags: N=Normal, H=High, L=Low, A=Abnormal, C=Critical
    Colors: green, yellow, orange, red, gray (no reference)
    """
    test_code: str
    test_name: str
    value_numeric: Optional[float]
    value_string: Optional[str]
    unit: str
    reference_range: ReferenceRange
    interpretation_flag: str  # N / H / L / A / C
    color_code: str           # green / yellow / orange / red / gray
    category: str             # Lab group (CBC, Chemistry, Urinalysis...)
    machine: Optional[str] = None
    trend: Optional[str] = None  # ↑ ↓ → (compared to previous encounter)

    def display_value(self):
        """Return display string for the value"""
        if self.value_string and self.value_string not in ["", "None"]:
            return self.value_string
        if self.value_numeric is not None:
            # Format: remove trailing zeros
            v = self.value_numeric
            if v == int(v):
                return str(int(v))
            return f"{v:.4f}".rstrip('0').rstrip('.')
        return "N/A"

    def to_dict(self):
        return {
            "test_code": self.test_code,
            "test_name": self.test_name,
            "value_numeric": self.value_numeric,
            "value_string": self.value_string,
            "unit": self.unit,
            "reference_range": self.reference_range.to_dict(),
            "interpretation_flag": self.interpretation_flag,
            "color_code": self.color_code,
            "category": self.category,
            "machine": self.machine,
            "trend": self.trend,
        }


@dataclass
class LabEncounter:
    """
    Complete lab encounter - maps to FHIR Bundle/DiagnosticReport
    One encounter = one sample collection event
    """
    encounter_id: str
    patient_id: str
    patient_name: str
    gender: str
    dob: str
    clinical_timestamp: str  # ISO 8601 format
    ordering_physician: str = ""
    lab_technician: str = ""
    observations: List[Observation] = field(default_factory=list)
    imaging_reports: List[dict] = field(default_factory=list)
    vitals: dict = field(default_factory=dict)

    def get_by_category(self):
        """Return observations grouped by category"""
        groups = {}
        for obs in self.observations:
            cat = obs.category
            if cat not in groups:
                groups[cat] = []
            groups[cat].append(obs)
        return groups

    def get_abnormal(self):
        """Return only abnormal observations"""
        return [o for o in self.observations if o.color_code != "green" and o.color_code != "gray"]

    def summary_counts(self):
        """Return count per color code"""
        counts = {"green": 0, "yellow": 0, "orange": 0, "red": 0, "gray": 0}
        for obs in self.observations:
            counts[obs.color_code] = counts.get(obs.color_code, 0) + 1
        return counts

    def to_fhir_json(self):
        """Export to FHIR-inspired JSON structure"""
        return {
            "encounter_id": self.encounter_id,
            "patient": {
                "patient_id": self.patient_id,
                "name": self.patient_name,
                "gender": self.gender,
                "dob": self.dob,
            },
            "clinical_timestamp": self.clinical_timestamp,
            "ordering_physician": self.ordering_physician,
            "observations": [obs.to_dict() for obs in self.observations],
            "imaging_reports": self.imaging_reports,
            "vitals": self.vitals,
        }


# Category display names (Vietnamese medical terminology)
CATEGORY_LABELS = {
    "CBC": "🩸 Huyết học tế bào",
    "COAG": "🩹 Đông máu",
    "BLOOD_TYPE": "🏥 Truyền máu / Nhóm máu",
    "RAPID": "⚡ Test nhanh",
    "CHEMISTRY": "⚗️ Hóa sinh máu",
    "URINALYSIS": "🔬 Sinh hoá nước tiểu",
    "OTHER": "📋 Khác",
}

# Color to Vietnamese label
FLAG_LABELS = {
    "N": "Bình thường",
    "H": "Cao",
    "L": "Thấp",
    "A": "Bất thường",
    "C": "Nguy hiểm",
}
