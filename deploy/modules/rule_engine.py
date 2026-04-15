"""
HIDU EWS - Rule Engine
Clinical color-coding algorithm based on deviation from reference range.
Algorithm is data-driven (reference ranges come from PDF, never hardcoded).
"""

import re
from typing import Optional, Tuple
from modules.data_models import ReferenceRange, Observation


# ─── Reference Range Parser ─────────────────────────────────────────────────

def parse_reference_range(ref_text: str) -> ReferenceRange:
    """
    Parse reference range text from lab PDF into structured low/high values.

    Handles formats:
      "4 - 10"      → low=4.0, high=10.0
      "< 2.7"       → low=None, high=2.7
      "> 0.5"       → low=0.5, high=None
      "ÂM TÍNH"     → low=None, high=None  (qualitative negative)
      "1.01 - 1.03" → low=1.01, high=1.03
      ""            → low=None, high=None
    """
    if not ref_text or not ref_text.strip():
        return ReferenceRange(None, None, "")

    text = ref_text.strip()
    text_upper = text.upper()

    # Qualitative references (negative/positive)
    NEGATIVE_REFS = {"ÂM TÍNH", "AM TINH", "NEGATIVE", "(-)", "ÂMTÍNH", "ÂM TÍNH"}
    if text_upper in NEGATIVE_REFS or text_upper.replace(" ", "") == "ÂMTÍNH":
        return ReferenceRange(None, None, text)

    # Range format: "4 - 10" or "4.1 - 5.9"
    range_match = re.match(
        r'^([0-9]+(?:[.,][0-9]+)?)\s*[-–]\s*([0-9]+(?:[.,][0-9]+)?)$', text
    )
    if range_match:
        low = _safe_float(range_match.group(1))
        high = _safe_float(range_match.group(2))
        return ReferenceRange(low, high, text)

    # Less-than format: "< 5" or "<5"
    lt_match = re.match(r'^[<≤]\s*([0-9]+(?:[.,][0-9]+)?)$', text)
    if lt_match:
        high = _safe_float(lt_match.group(1))
        return ReferenceRange(None, high, text)

    # Greater-than format: "> 0.5"
    gt_match = re.match(r'^[>≥]\s*([0-9]+(?:[.,][0-9]+)?)$', text)
    if gt_match:
        low = _safe_float(gt_match.group(1))
        return ReferenceRange(low, None, text)

    # Single number (treat as upper limit)
    single_match = re.match(r'^([0-9]+(?:[.,][0-9]+)?)$', text)
    if single_match:
        high = _safe_float(single_match.group(1))
        return ReferenceRange(None, high, text)

    # Urobilinogen special: "1.7 - 30" style already handled above
    return ReferenceRange(None, None, text)


def _safe_float(s: str) -> Optional[float]:
    """Convert string to float, handling comma decimal separator."""
    try:
        return float(s.replace(',', '.'))
    except (ValueError, AttributeError):
        return None


# ─── Value Sanitizer ─────────────────────────────────────────────────────────

NEGATIVE_VALUES = {"âm tính", "am tinh", "negative", "(-)", "âmtính"}
POSITIVE_VALUES = {"dương tính", "duong tinh", "positive", "(+)", "dươngtính"}


def sanitize_value(raw_value: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Convert raw string value from PDF into (numeric, string) pair.

    Returns:
        (value_numeric, value_string)
        - Numeric values: (8.55, None)
        - Negative: (0.0, "Âm tính")
        - Positive: (1.0, "Dương tính")
        - Text-only: (None, "AB")
    """
    if not raw_value or not raw_value.strip():
        return None, None

    cleaned = raw_value.strip()
    lower = cleaned.lower().replace(" ", "")

    # Qualitative negative
    if lower in NEGATIVE_VALUES or lower == "âmtính":
        return 0.0, cleaned

    # Qualitative positive
    if lower in POSITIVE_VALUES or lower == "dươngtính":
        return 1.0, cleaned

    # Try numeric (handle comma decimal)
    numeric_str = cleaned.replace(',', '.')
    # Remove any stray asterisks (some PDFs mark abnormal with *)
    numeric_str = numeric_str.replace('*', '').strip()

    try:
        return float(numeric_str), None
    except ValueError:
        # Pure text result (blood type, etc.)
        return None, cleaned


# ─── Color Coding Algorithm ───────────────────────────────────────────────────

def assign_clinical_color(
    value_numeric: Optional[float],
    value_string: Optional[str],
    ref: ReferenceRange,
) -> Tuple[str, str]:
    """
    Core Rule Engine: Assign (color_code, interpretation_flag) based on
    deviation from reference range.

    Risk stratification:
      green  / N  → Normal (within reference)
      yellow / H,L → Mild deviation (≤20% outside range)
      orange / A   → Abnormal (20%–50% outside range)
      red    / C   → Critical (>50% outside range)
      gray   / N   → No reference range available

    IMPORTANT: Thresholds (20%, 50%) should be adjusted by clinician.
    """
    is_negative_ref = (
        ref.low is None
        and ref.high is None
        and ref.text.upper().replace(" ", "") in {"ÂMTÍNH", "AMTINH", "NEGATIVE", "AM TINH"}
    )

    # ── Case 1: Qualitative test with NEGATIVE expected ──
    is_negative_ref_loose = any(kw in ref.text.upper() for kw in {"ÂM TÍNH", "AMTINH", "NEGATIVE", "AM TINH", "ÂMTÍNH"})
    if is_negative_ref_loose:
        if value_numeric is not None and value_numeric == 0:
            return "green", "N"  # Negative as expected
        elif value_numeric is None and value_string:
            lower = value_string.lower().replace(" ", "")
            if lower in NEGATIVE_VALUES or lower == "âmtính":
                return "green", "N"
        # If it's a number and not 0, or it's a positive string, it's abnormal!
        # A positive string will map to value_numeric=1.0 which is > 0, so it hits orange.
        # But wait, what if value_numeric is 15 (like Bilirubin 15 with Ref "Âm tính")?
        # That's clearly abnormal.
        if value_numeric is not None and value_numeric > 0:
            return "orange", "A"
        return "orange", "A"

    # ── Case 1.5: Explicit Qualitative Negative Result ──
    # If the test result literally says "Âm tính", it is almost universally a Normal result.
    # E.g., Urobilinogen: result "Âm tính", ref "1.7 - 30".
    is_negative_result = (
        value_numeric == 0.0 and 
        value_string and 
        value_string.lower().replace(" ", "") in {"âmtính", "amtinh", "negative", "(-)"}
    )
    if is_negative_result:
        # Check if reference actually EXPECTS positive
        if not any(kw in ref.text.upper() for kw in {"DƯƠNG TÍNH", "DUONG TINH", "POSITIVE"}):
            return "green", "N"

    # ── Case 2: No reference range ──
    if ref.low is None and ref.high is None:
        return "gray", "N"

    # ── Case 3: Numeric comparison ──
    if value_numeric is None:
        return "gray", "N"  # Text value with numeric ref — skip

    val = value_numeric
    ref_min = ref.low if ref.low is not None else float('-inf')
    ref_max = ref.high if ref.high is not None else float('inf')

    # Within normal range
    if ref_min <= val <= ref_max:
        return "green", "N"

    # Calculate deviation percentage
    if val > ref_max:
        if ref_max == 0:
            # Avoid division by zero
            return "red", "C"
        deviation = (val - ref_max) / ref_max
        flag = "H"
    else:  # val < ref_min
        if ref_min == 0:
            return "yellow", "L"
        deviation = (ref_min - val) / ref_min
        flag = "L"

    # Stratify by deviation
    if deviation <= 0.20:
        return "yellow", flag
    elif deviation <= 0.50:
        return "orange", "A"
    else:
        return "red", "C"


def calculate_trend(current: Optional[float], previous: Optional[float]) -> Optional[str]:
    """
    Compare current vs previous value for trend arrow.
    Returns: ↑ ↗ → ↘ ↓ or None
    """
    if current is None or previous is None:
        return None
    diff_pct = (current - previous) / (abs(previous) + 1e-9)
    if diff_pct > 0.10:
        return "↑"
    elif diff_pct > 0.03:
        return "↗"
    elif diff_pct < -0.10:
        return "↓"
    elif diff_pct < -0.03:
        return "↘"
    else:
        return "→"


# ─── Process Full Encounter ───────────────────────────────────────────────────

def process_encounter(encounter, previous_encounter=None):
    """
    Apply rule engine to all observations in an encounter.
    Optionally compare to previous encounter for trend calculation.
    """
    prev_map = {}
    if previous_encounter:
        for obs in previous_encounter.observations:
            prev_map[obs.test_code] = obs.value_numeric

    for obs in encounter.observations:
        color, flag = assign_clinical_color(
            obs.value_numeric,
            obs.value_string,
            obs.reference_range,
        )
        obs.color_code = color
        obs.interpretation_flag = flag

        # Trend vs previous
        if obs.test_code in prev_map:
            obs.trend = calculate_trend(obs.value_numeric, prev_map[obs.test_code])

    return encounter


def calculate_mews(vitals: dict) -> Tuple[int, str]:
    """
    Calculate Modified Early Warning Score (MEWS) based on Vitals.
    Returns: (score, hex_color)
    """
    if not vitals:
        return 0, "#94a3b8"  # Gray if no vitals
        
    score = 0
    
    # Systolic BP
    sbp = vitals.get("sbp", 0)
    if sbp > 0:
        if sbp <= 70: score += 3
        elif sbp <= 80: score += 2
        elif sbp <= 100: score += 1
        elif sbp >= 200: score += 2
        
    # Heart Rate (HR)
    hr = vitals.get("hr", 0)
    if hr > 0:
        if hr < 40: score += 2
        elif hr <= 50: score += 1
        elif hr >= 130: score += 3
        elif hr >= 111: score += 2
        elif hr >= 101: score += 1
        
    # Respiratory Rate (RR)
    rr = vitals.get("rr", 0)
    if rr > 0:
        if rr < 9: score += 2
        elif rr >= 30: score += 3
        elif rr >= 21: score += 2
        elif rr >= 15: score += 1
        
    # Temperature
    temp = vitals.get("temp", 0)
    if temp > 0:
        if temp < 35.0: score += 2
        elif temp >= 38.5: score += 2
        
    # Color coding based on risk
    if score >= 5: return score, "#ef4444"     # Red (Critical)
    elif score >= 3: return score, "#f97316"   # Orange (High Risk)
    elif score >= 1: return score, "#eab308"   # Yellow (Abnormal)
    return score, "#22c55e"                    # Green (Normal)
