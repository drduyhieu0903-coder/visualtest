"""
HIDU EWS — Qualitative Result Renderer
Renders non-numeric lab results: binary (✅/❌), graded (1+/2+/3+),
blood type chips, and gauge displays.
"""

# ─── Type Detection ─────────────────────────────────────────────────────────

BINARY_TESTS = {
    "HIV", "HBSAG", "HCV", "ANTI_HCV", "ANTI_HIV", "VDRL", "RPR",
    "TPHA", "NITRITE", "HIV_AB", "HBS_AG",
}

GRADED_TESTS = {
    "PROTEIN", "HEMOGLOBIN", "GLUCOSE_NIỆU", "GLUCOSE_NIEU",
    "KETONE", "BILIRUBIN", "BẠCH_CẦU", "BACH_CAU",
    "HỒNG_CẦU", "HONG_CAU", "ERY", "LEU",
    "PROTEIN_NIỆU", "PROTEIN_NIEU",
}

BLOOD_TYPE_TESTS = {
    "ABO", "NHÓM_MÁU", "NHOM_MAU", "RH", "RH(D)", "BLOOD_TYPE",
}

NEGATIVE_KEYWORDS = {"âm tính", "am tinh", "negative", "(-)", "âmtính"}
POSITIVE_KEYWORDS = {"dương tính", "duong tinh", "positive", "(+)", "dươngtính"}

GRADED_SCALE = {
    "ÂM TÍNH": 0, "AM TINH": 0, "NEGATIVE": 0, "(-)": 0,
    "TRACE": 1, "VẾT": 1,
    "1+": 2, "2+": 3, "3+": 4, "4+": 5,
}


def detect_qualitative_type(test_code: str, category: str, value_string: str) -> str:
    """
    Detect what type of qualitative renderer to use.
    Returns: 'binary', 'graded', 'blood_type', or 'numeric' (default).
    """
    code_upper = test_code.upper().replace(" ", "_")

    # Blood type checks
    if code_upper in BLOOD_TYPE_TESTS or category == "BLOOD_TYPE":
        return "blood_type"

    # Binary (rapid tests, serology)
    if category == "RAPID" or code_upper in BINARY_TESTS:
        return "binary"

    # Check if value looks binary
    if value_string:
        val_lower = value_string.lower().strip().replace(" ", "")
        if val_lower in NEGATIVE_KEYWORDS or val_lower in POSITIVE_KEYWORDS:
            # Could be binary or graded depending on test
            if code_upper in GRADED_TESTS or category == "URINALYSIS":
                return "graded"
            return "binary"

    # Graded (urinalysis)
    if code_upper in GRADED_TESTS:
        return "graded"
    if value_string and value_string.strip().upper() in GRADED_SCALE:
        return "graded"

    return "numeric"


# ─── Binary Indicator (Âm tính / Dương tính) ────────────────────────────────

def render_binary_indicator(value_string: str, color_code: str) -> str:
    """Render ✅ / ❌ indicator for binary tests."""
    if not value_string:
        return '<span class="val-cell val-gray">N/A</span>'

    val_lower = value_string.lower().strip().replace(" ", "")
    is_negative = val_lower in NEGATIVE_KEYWORDS

    if is_negative:
        return (
            '<span class="qualitative-indicator qual-negative">'
            '✅ Âm tính</span>'
        )
    else:
        return (
            '<span class="qualitative-indicator qual-positive">'
            '❌ Dương tính</span>'
        )


# ─── Graded Bar (1+ / 2+ / 3+) ──────────────────────────────────────────────

def render_graded_bar(value_string: str, color_code: str) -> str:
    """Render graded indicator bar for semi-quantitative results."""
    if not value_string:
        return '<span class="val-cell val-gray">N/A</span>'

    val_upper = value_string.strip().upper()
    level = GRADED_SCALE.get(val_upper, -1)

    # If not in scale, check for keywords
    if level == -1:
        val_lower = value_string.lower().strip().replace(" ", "")
        if val_lower in NEGATIVE_KEYWORDS:
            level = 0
        elif val_lower in POSITIVE_KEYWORDS:
            level = 2  # Generic positive = mild
        else:
            # Unknown graded value, fallback
            return f'<span class="val-cell val-{color_code}">{value_string}</span>'

    # Build the graded dots
    level_colors = ["#22c55e", "#a3e635", "#eab308", "#f97316", "#ef4444", "#dc2626"]
    level_labels = ["Âm", "Vết", "1+", "2+", "3+", "4+"]
    dots = []
    for i in range(6):
        if i <= level:
            bg = level_colors[i]
            opacity = "1.0"
        else:
            bg = "#e2e8f0"
            opacity = "0.4"
        dots.append(
            f'<span class="graded-dot" style="background:{bg};opacity:{opacity}" '
            f'title="{level_labels[i]}"></span>'
        )

    label = value_string.strip()
    label_color = level_colors[min(level, 5)]

    return (
        f'<span class="graded-bar-container">'
        f'<span class="graded-dots">{"".join(dots)}</span>'
        f'<span class="graded-label" style="color:{label_color}">{label}</span>'
        f'</span>'
    )


# ─── Blood Type Chip ─────────────────────────────────────────────────────────

def render_blood_type_chip(value_string: str) -> str:
    """Render blood type as a styled chip tag."""
    if not value_string:
        return '<span class="val-cell val-gray">N/A</span>'

    val = value_string.strip()

    # Determine chip color based on content
    if "Rh" in val or "rh" in val.lower():
        if "dương" in val.lower() or "+" in val:
            chip_class = "blood-chip-rh-pos"
        else:
            chip_class = "blood-chip-rh-neg"
    else:
        chip_class = "blood-chip-abo"

    return (
        f'<span class="blood-type-chip {chip_class}">'
        f'🩸 {val}</span>'
    )


# ─── Main Router ─────────────────────────────────────────────────────────────

def render_qualitative_value(obs) -> str:
    """
    Main entry: decide which renderer to use based on observation type.
    Returns HTML string.
    """
    q_type = detect_qualitative_type(
        obs.test_code, obs.category,
        obs.value_string or ""
    )

    display = obs.value_string or obs.display_value()

    if q_type == "binary":
        return render_binary_indicator(display, obs.color_code)
    elif q_type == "graded":
        return render_graded_bar(display, obs.color_code)
    elif q_type == "blood_type":
        return render_blood_type_chip(display)
    else:
        return None  # Fallback to default numeric renderer
