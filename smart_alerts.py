"""
HIDU EWS — Smart Alerts Engine
Cảnh báo thông minh: Combination Rules, Delta Check, Trend Alert.
"""

from typing import List, Optional
from datetime import datetime


# ─── Combination Rules ───────────────────────────────────────────────────────

COMBINATION_RULES = [
    {
        "name": "Nghi ngờ Nhiễm khuẩn huyết",
        "icon": "🦠",
        "conditions": [
            ("WBC", lambda o: o.color_code in ("orange", "red")),
        ],
        "optional_conditions": [
            ("NEU%", lambda o: o.value_numeric is not None and o.value_numeric > 80),
            ("NEU", lambda o: o.value_numeric is not None and o.value_numeric > 80),
            ("NEUTROPHIL", lambda o: o.value_numeric is not None and o.value_numeric > 80),
        ],
        "alert_level": "red",
        "message": "WBC bất thường → Cần đánh giá nhiễm trùng. Kiểm tra cấy máu nếu lâm sàng nghi ngờ.",
    },
    {
        "name": "Nghi ngờ tổn thương gan cấp",
        "icon": "🫁",
        "conditions": [
            ("AST", lambda o: o.color_code in ("orange", "red")),
            ("ALT", lambda o: o.color_code in ("orange", "red")),
        ],
        "alert_level": "orange",
        "message": "AST và ALT đều tăng → Nghi ngờ tổn thương tế bào gan. Theo dõi men gan.",
    },
    {
        "name": "Nghi ngờ tắc mật",
        "icon": "🟤",
        "conditions": [
            ("UROBILINOGEN", lambda o: o.color_code == "red"),
        ],
        "optional_conditions": [
            ("BILIRUBIN", lambda o: o.color_code in ("orange", "red")),
        ],
        "alert_level": "red",
        "message": "Urobilinogen bất thường → Nghi ngờ tắc mật. Kiểm tra bilirubin máu và siêu âm ổ bụng.",
    },
    {
        "name": "Rối loạn thận cấp (AKI screening)",
        "icon": "🫘",
        "conditions": [
            ("CREATININ", lambda o: o.color_code in ("yellow", "orange", "red")),
        ],
        "optional_conditions": [
            ("URE", lambda o: o.color_code in ("orange", "red")),
        ],
        "alert_level": "orange",
        "message": "Creatinin tăng → Sàng lọc tổn thương thận cấp. Theo dõi chức năng thận và nước tiểu.",
    },
    {
        "name": "Thiếu máu",
        "icon": "🩸",
        "conditions": [
            ("HGB", lambda o: o.color_code in ("orange", "red") and o.interpretation_flag == "L"),
        ],
        "optional_conditions": [
            ("RBC", lambda o: o.color_code in ("yellow", "orange", "red") and o.interpretation_flag == "L"),
            ("HCT", lambda o: o.color_code in ("yellow", "orange", "red") and o.interpretation_flag == "L"),
        ],
        "alert_level": "orange",
        "message": "Hemoglobin giảm → Nghi ngờ thiếu máu. Đánh giá nguyên nhân và xem xét truyền máu.",
    },
    {
        "name": "Rối loạn đường huyết",
        "icon": "🍬",
        "conditions": [
            ("GLUCOSE", lambda o: o.color_code in ("orange", "red")),
        ],
        "alert_level": "yellow",
        "message": "Glucose bất thường → Theo dõi đường huyết. Xem xét HbA1c nếu chưa xét nghiệm.",
    },
]


def check_combination_rules(encounter) -> List[dict]:
    """Check all combination rules and return fired alerts."""
    obs_map = {}
    for o in encounter.observations:
        code = o.test_code.upper().replace(" ", "_")
        obs_map[code] = o
        # Also map by common short names
        name_upper = o.test_name.upper()
        for keyword in ["WBC", "RBC", "HGB", "HCT", "PLT", "AST", "ALT", "GGT",
                         "CREATININ", "URE", "GLUCOSE", "BILIRUBIN", "UROBILINOGEN"]:
            if keyword in name_upper or keyword in code:
                obs_map[keyword] = o

    fired = []
    for rule in COMBINATION_RULES:
        # All required conditions must match
        required_match = all(
            code in obs_map and cond(obs_map[code])
            for code, cond in rule["conditions"]
        )
        if not required_match:
            continue

        # Check optional conditions for extra detail
        optional_matches = []
        for code, cond in rule.get("optional_conditions", []):
            if code in obs_map and cond(obs_map[code]):
                optional_matches.append(code)

        fired.append({
            "name": rule["name"],
            "icon": rule["icon"],
            "level": rule["alert_level"],
            "message": rule["message"],
            "optional_matches": optional_matches,
        })

    return fired


# ─── Delta Check ──────────────────────────────────────────────────────────────

DELTA_RULES = {
    "HGB":       (20,  24, "g/L",    "chảy máu"),
    "PLT":       (50,  48, "G/L",    "DIC"),
    "CREATININ": (44,  48, "µmol/L", "AKI"),
    "WBC":       (4.0, 24, "G/L",    "nhiễm trùng"),
    "GLUCOSE":   (3.0, 6,  "mmol/L", "rối loạn đường huyết"),
}


def check_delta(encounter, previous_encounter) -> List[dict]:
    """Compare current vs previous encounter for sudden changes."""
    if not previous_encounter:
        return []

    # Build maps
    current_map = {}
    for o in encounter.observations:
        code = o.test_code.upper().replace(" ", "_")
        current_map[code] = o
        name_upper = o.test_name.upper()
        for keyword in DELTA_RULES:
            if keyword in name_upper or keyword in code:
                current_map[keyword] = o

    prev_map = {}
    for o in previous_encounter.observations:
        code = o.test_code.upper().replace(" ", "_")
        prev_map[code] = o
        name_upper = o.test_name.upper()
        for keyword in DELTA_RULES:
            if keyword in name_upper or keyword in code:
                prev_map[keyword] = o

    # Calculate time difference
    hours_between = _calc_hours_between(
        encounter.clinical_timestamp,
        previous_encounter.clinical_timestamp,
    )

    alerts = []
    for code, (max_delta, max_hours, unit, concern) in DELTA_RULES.items():
        if code not in current_map or code not in prev_map:
            continue
        curr = current_map[code]
        prev = prev_map[code]

        if curr.value_numeric is None or prev.value_numeric is None:
            continue

        # Check time window (skip if too far apart, unless we don't know)
        if hours_between is not None and hours_between > max_hours:
            continue

        delta = abs(curr.value_numeric - prev.value_numeric)
        if delta >= max_delta:
            direction = "↑ tăng" if curr.value_numeric > prev.value_numeric else "↓ giảm"
            time_str = f" trong {hours_between:.0f}h" if hours_between else ""
            alerts.append({
                "name": f"Delta Check: {curr.test_name}",
                "icon": "⚡",
                "level": "orange",
                "message": (
                    f"{curr.test_name} {direction} {delta:.1f} {unit}{time_str} "
                    f"(trước: {prev.display_value()}, nay: {curr.display_value()}) "
                    f"→ Cảnh báo {concern}"
                ),
            })

    return alerts


def _calc_hours_between(ts1: str, ts2: str) -> Optional[float]:
    """Calculate hours between two ISO timestamps."""
    try:
        dt1 = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(ts2.replace("Z", "+00:00"))
        return abs((dt1 - dt2).total_seconds()) / 3600
    except Exception:
        return None


# ─── Trend Alert (3 consecutive deterioration) ───────────────────────────────

def check_trend_alerts(encounters_list, current_index: int) -> List[dict]:
    """
    Check if any test shows 3 consecutive worsening values.
    Requires at least 3 encounters.
    """
    if len(encounters_list) < 3 or current_index < 2:
        return []

    # Take 3 most recent encounters up to current
    recent_3 = encounters_list[max(0, current_index - 2):current_index + 1]
    if len(recent_3) < 3:
        return []

    # Collect test series
    all_codes = set()
    for enc in recent_3:
        for obs in enc.observations:
            if obs.value_numeric is not None:
                all_codes.add(obs.test_code)

    alerts = []
    for code in all_codes:
        values = []
        test_name = code
        for enc in recent_3:
            for obs in enc.observations:
                if obs.test_code == code and obs.value_numeric is not None:
                    values.append(obs.value_numeric)
                    test_name = obs.test_name
                    break

        if len(values) < 3:
            continue

        # Decreasing 3 times
        if values[0] > values[1] > values[2]:
            total_drop_pct = (values[0] - values[2]) / values[0] * 100
            if total_drop_pct > 5:  # Only alert if significant
                alerts.append({
                    "name": f"Xu hướng giảm: {test_name}",
                    "icon": "📉",
                    "level": "yellow",
                    "message": (
                        f"{test_name} giảm liên tục 3 lần: "
                        f"{values[0]:.1f} → {values[1]:.1f} → {values[2]:.1f} "
                        f"(giảm tổng {total_drop_pct:.0f}%)"
                    ),
                })

        # Increasing 3 times
        if values[0] < values[1] < values[2]:
            total_rise_pct = (values[2] - values[0]) / max(values[0], 0.01) * 100
            if total_rise_pct > 5:
                alerts.append({
                    "name": f"Xu hướng tăng: {test_name}",
                    "icon": "📈",
                    "level": "yellow",
                    "message": (
                        f"{test_name} tăng liên tục 3 lần: "
                        f"{values[0]:.1f} → {values[1]:.1f} → {values[2]:.1f} "
                        f"(tăng tổng {total_rise_pct:.0f}%)"
                    ),
                })

    return alerts


def check_vitals_rules(encounter) -> List[dict]:
    """Check clinical rules combining Vitals and Lab results (e.g. SIRS)."""
    alerts = []
    vitals = getattr(encounter, "vitals", {})
    if not vitals:
        return alerts

    hr = float(vitals.get("hr", 0))
    rr = float(vitals.get("rr", 0))
    temp = float(vitals.get("temp", 37.0))

    # Fetch WBC from observations
    wbc_val = None
    for o in encounter.observations:
        if "WBC" in o.test_code.upper() or "WBC" in o.test_name.upper():
            wbc_val = o.value_numeric
            break

    # SIRS Criteria (Systemic Inflammatory Response Syndrome)
    # 2 or more of: Temp >38 or <36, HR >90, RR >20, WBC >12 or <4
    sirs_points = 0
    sirs_matches = []
    if temp > 38 or temp < 36:
        sirs_points += 1
        sirs_matches.append(f"Nhiệt độ {temp}°C")
    if hr > 90:
        sirs_points += 1
        sirs_matches.append(f"Mạch {int(hr)} l/p")
    if rr > 20:
        sirs_points += 1
        sirs_matches.append(f"Nhịp thở {int(rr)} l/p")
    if wbc_val is not None and (wbc_val > 12 or wbc_val < 4):
        sirs_points += 1
        sirs_matches.append(f"WBC {wbc_val}")

    if sirs_points >= 2:
        alerts.append({
            "name": "Nghi ngờ SIRS / Nhiễm khuẩn huyết",
            "icon": "⚠️",
            "level": "red",
            "message": (
                f"Thỏa mãn {sirs_points}/4 tiêu chuẩn SIRS ({', '.join(sirs_matches)}). "
                "Cảnh báo nguy cơ Hội chứng đáp ứng viêm toàn thân (ví dụ: Sepsis)."
            )
        })
        
    return alerts


# ─── Main Entry Point ────────────────────────────────────────────────────────

def run_all_alerts(encounter, previous_encounter=None,
                   encounters_list=None, current_index=0) -> List[dict]:
    """
    Run all alert checks and return combined, deduplicated list.
    Sorted by severity: red > orange > yellow.
    """
    alerts = []

    # Combination rules
    alerts.extend(check_combination_rules(encounter))
    
    # Vitals + Lab rules
    alerts.extend(check_vitals_rules(encounter))

    # Delta check (needs previous)
    if previous_encounter:
        alerts.extend(check_delta(encounter, previous_encounter))

    # Trend alerts (needs 3+ encounters)
    if encounters_list and len(encounters_list) >= 3:
        alerts.extend(check_trend_alerts(encounters_list, current_index))

    # Sort by severity
    severity_order = {"red": 0, "orange": 1, "yellow": 2}
    alerts.sort(key=lambda a: severity_order.get(a["level"], 3))

    return alerts
