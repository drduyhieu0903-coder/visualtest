"""
HIDU EWS — Clinical Summary Generator
Sinh tóm tắt lâm sàng tự động (rule-based) và tính Risk Score.
"""

from typing import List, Tuple


# ─── Rule-Based Clinical Summary ──────────────────────────────────────────────

def generate_clinical_summary(encounter) -> List[dict]:
    """
    Generate clinical summary grouped by lab category.
    Returns list of {icon, title, text, level}.
    """
    by_cat = encounter.get_by_category()
    summaries = []

    # ── CBC (Huyết học) ──
    if "CBC" in by_cat:
        cbc_obs = by_cat["CBC"]
        cbc_abnormal = [o for o in cbc_obs if o.color_code not in ("green", "gray")]
        if not cbc_abnormal:
            summaries.append({
                "icon": "🟢",
                "title": "Huyết học",
                "text": "Công thức máu trong giới hạn bình thường. "
                        "Không có dấu hiệu thiếu máu hay nhiễm trùng.",
                "level": "normal",
            })
        else:
            items = []
            for o in cbc_abnormal:
                direction = _describe_direction(o)
                items.append(f"{o.test_name} {o.display_value()} {o.unit} ({direction})")
            text = "; ".join(items)

            # Check severity
            has_red = any(o.color_code == "red" for o in cbc_abnormal)
            has_orange = any(o.color_code == "orange" for o in cbc_abnormal)

            if has_red:
                summaries.append({
                    "icon": "🔴",
                    "title": "Huyết học — NGUY HIỂM",
                    "text": f"Bất thường: {text}. Cần đánh giá lâm sàng khẩn.",
                    "level": "critical",
                })
            elif has_orange:
                summaries.append({
                    "icon": "🟠",
                    "title": "Huyết học — Bất thường",
                    "text": f"Bất thường: {text}. Cần theo dõi.",
                    "level": "abnormal",
                })
            else:
                summaries.append({
                    "icon": "🟡",
                    "title": "Huyết học — Chú ý",
                    "text": f"Nhẹ bất thường: {text}.",
                    "level": "caution",
                })

    # ── COAG (Đông máu) ──
    if "COAG" in by_cat:
        coag_obs = by_cat["COAG"]
        coag_abnormal = [o for o in coag_obs if o.color_code not in ("green", "gray")]
        if not coag_abnormal:
            summaries.append({
                "icon": "🟢",
                "title": "Đông máu",
                "text": "Các chỉ số đông máu bình thường.",
                "level": "normal",
            })
        else:
            items = [f"{o.test_name} {o.display_value()} {o.unit}" for o in coag_abnormal]
            summaries.append({
                "icon": "🟠",
                "title": "Đông máu — Bất thường",
                "text": f"Bất thường: {'; '.join(items)}. Đánh giá rối loạn đông máu.",
                "level": "abnormal",
            })

    # ── CHEMISTRY (Hoá sinh) ──
    if "CHEMISTRY" in by_cat:
        chem_obs = by_cat["CHEMISTRY"]
        chem_abnormal = [o for o in chem_obs if o.color_code not in ("green", "gray")]

        if not chem_abnormal:
            summaries.append({
                "icon": "🟢",
                "title": "Hoá sinh máu",
                "text": "Tất cả chỉ số sinh hoá trong giới hạn bình thường.",
                "level": "normal",
            })
        else:
            # Sub-group analysis
            liver_tests = []
            kidney_tests = []
            glucose_tests = []
            other_tests = []

            for o in chem_abnormal:
                name_upper = o.test_name.upper()
                if any(k in name_upper for k in ["AST", "ALT", "GGT", "BILIRUBIN"]):
                    liver_tests.append(o)
                elif any(k in name_upper for k in ["CREATININ", "URE", "UREA"]):
                    kidney_tests.append(o)
                elif "GLUCOSE" in name_upper:
                    glucose_tests.append(o)
                else:
                    other_tests.append(o)

            if liver_tests:
                items = [f"{o.test_name} {_describe_direction(o)} {o.display_value()} {o.unit}" for o in liver_tests]
                pct_texts = []
                for o in liver_tests:
                    pct = _calc_deviation_pct(o)
                    if pct:
                        pct_texts.append(f"{o.test_name} vượt {pct}%")
                extra = f" ({', '.join(pct_texts)})" if pct_texts else ""
                summaries.append({
                    "icon": "🟡" if all(o.color_code == "yellow" for o in liver_tests) else "🟠",
                    "title": "Chức năng gan",
                    "text": f"{'; '.join(items)}{extra}. Chú ý chức năng gan.",
                    "level": "caution" if all(o.color_code == "yellow" for o in liver_tests) else "abnormal",
                })

            if kidney_tests:
                items = [f"{o.test_name} {o.display_value()} {o.unit}" for o in kidney_tests]
                summaries.append({
                    "icon": "🟠",
                    "title": "Chức năng thận",
                    "text": f"{'; '.join(items)}. Theo dõi chức năng thận.",
                    "level": "abnormal",
                })

            if glucose_tests:
                for o in glucose_tests:
                    direction = _describe_direction(o)
                    pct = _calc_deviation_pct(o)
                    pct_text = f" (vượt {pct}% giới hạn)" if pct else ""
                    summaries.append({
                        "icon": "🟡",
                        "title": "Đường huyết",
                        "text": f"Glucose máu {o.display_value()} {o.unit} — {direction}{pct_text}. Theo dõi sau ăn.",
                        "level": "caution",
                    })

            if other_tests:
                items = [f"{o.test_name} {o.display_value()} {o.unit}" for o in other_tests]
                summaries.append({
                    "icon": "🟡",
                    "title": "Sinh hoá khác",
                    "text": f"Bất thường: {'; '.join(items)}.",
                    "level": "caution",
                })

    # ── URINALYSIS (Nước tiểu) ──
    if "URINALYSIS" in by_cat:
        uri_obs = by_cat["URINALYSIS"]
        uri_abnormal = [o for o in uri_obs if o.color_code not in ("green", "gray")]
        if not uri_abnormal:
            summaries.append({
                "icon": "🟢",
                "title": "Nước tiểu",
                "text": "Tổng phân tích nước tiểu bình thường.",
                "level": "normal",
            })
        else:
            items = []
            for o in uri_abnormal:
                val_display = o.value_string or o.display_value()
                items.append(f"{o.test_name}: {val_display}")
            has_red = any(o.color_code == "red" for o in uri_abnormal)
            summaries.append({
                "icon": "🔴" if has_red else "🟠",
                "title": "Nước tiểu — Bất thường",
                "text": f"{'; '.join(items)}.",
                "level": "critical" if has_red else "abnormal",
            })

    # ── RAPID (Test nhanh) ──
    if "RAPID" in by_cat:
        rapid_obs = by_cat["RAPID"]
        rapid_abnormal = [o for o in rapid_obs if o.color_code not in ("green", "gray")]
        if not rapid_abnormal:
            summaries.append({
                "icon": "🟢",
                "title": "Test nhanh",
                "text": "Tất cả test nhanh âm tính.",
                "level": "normal",
            })
        else:
            items = [f"{o.test_name}: {o.value_string or o.display_value()}" for o in rapid_abnormal]
            summaries.append({
                "icon": "🔴",
                "title": "Test nhanh — DƯƠNG TÍNH",
                "text": f"{'; '.join(items)}. Cần xác nhận bằng xét nghiệm khẳng định.",
                "level": "critical",
            })

    return summaries


# ─── Risk Score ───────────────────────────────────────────────────────────────

def calculate_risk_score(encounter) -> Tuple[int, str, str]:
    """
    Calculate a simple early warning risk score (0-10).
    Returns (score, level_text, level_color).

    Scoring:
      - Each yellow:  +1
      - Each orange:  +2
      - Each red:     +3
      - Max: 10
    """
    counts = encounter.summary_counts()
    raw_score = (counts["yellow"] * 1) + (counts["orange"] * 2) + (counts["red"] * 3)
    score = min(raw_score, 10)

    if score == 0:
        return score, "Bình thường", "#22c55e"
    elif score <= 3:
        return score, "Theo dõi", "#eab308"
    elif score <= 6:
        return score, "Cần chú ý", "#f97316"
    else:
        return score, "Nguy hiểm", "#ef4444"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _describe_direction(obs) -> str:
    """Describe if a value is high or low in Vietnamese."""
    if obs.interpretation_flag == "H":
        return "cao"
    elif obs.interpretation_flag == "L":
        return "thấp"
    elif obs.interpretation_flag == "C":
        return "nguy hiểm"
    elif obs.interpretation_flag == "A":
        return "bất thường"
    return ""


def _calc_deviation_pct(obs) -> str:
    """Calculate percent deviation from reference, return as string."""
    if obs.value_numeric is None:
        return ""
    ref = obs.reference_range
    if obs.interpretation_flag in ("H", "C") and ref.high:
        pct = (obs.value_numeric - ref.high) / ref.high * 100
        return f"{pct:.0f}"
    elif obs.interpretation_flag == "L" and ref.low:
        pct = (ref.low - obs.value_numeric) / ref.low * 100
        return f"{pct:.0f}"
    return ""
