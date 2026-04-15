"""
HIDU EWS — Trend Chart Module
Biểu đồ xu hướng Plotly cho các chỉ số xét nghiệm theo thời gian.
"""

from typing import List, Optional
from datetime import datetime

import plotly.graph_objects as go


# Marker colors matching the EWS color system
MARKER_COLORS = {
    "green":  "#22c55e",
    "yellow": "#eab308",
    "orange": "#f97316",
    "red":    "#ef4444",
    "gray":   "#94a3b8",
}


def build_obs_history(encounters_list, test_code: str) -> List[dict]:
    """
    Extract history of a single test across multiple encounters.

    Returns: [
        {"timestamp": "2026-03-13T08:00:00Z", "value": 132, "color": "green", "display": "132"},
        ...
    ]
    """
    history = []
    for enc in encounters_list:
        for obs in enc.observations:
            if obs.test_code == test_code and obs.value_numeric is not None:
                history.append({
                    "timestamp": enc.clinical_timestamp or "",
                    "value": obs.value_numeric,
                    "color": obs.color_code,
                    "display": obs.display_value(),
                    "unit": obs.unit,
                    "ref_low": obs.reference_range.low,
                    "ref_high": obs.reference_range.high,
                })
                break
    return history


def render_trend_chart(
    obs_history: List[dict],
    test_name: str,
    ref_low: Optional[float] = None,
    ref_high: Optional[float] = None,
    height: int = 260,
) -> go.Figure:
    """
    Render a Plotly trend chart for a single lab test across time points.

    Args:
        obs_history: list of dicts with timestamp, value, color
        test_name: display name for chart title
        ref_low: lower reference bound
        ref_high: upper reference bound
        height: chart height in px
    """
    fig = go.Figure()

    # --- Reference band (green background) ---
    if ref_low is not None and ref_high is not None:
        fig.add_hrect(
            y0=ref_low, y1=ref_high,
            fillcolor="rgba(34,197,94,0.07)",
            line_width=0,
            annotation_text="Bình thường",
            annotation_position="top right",
            annotation=dict(font_size=10, font_color="#15803d"),
        )
        fig.add_hline(
            y=ref_low, line_dash="dot",
            line_color="rgba(34,197,94,0.45)", line_width=1,
        )
        fig.add_hline(
            y=ref_high, line_dash="dot",
            line_color="rgba(34,197,94,0.45)", line_width=1,
        )
    elif ref_low is not None:
        fig.add_hline(
            y=ref_low, line_dash="dot",
            line_color="rgba(34,197,94,0.5)", line_width=1,
            annotation_text=f"Min: {ref_low}",
            annotation_position="top right",
        )
    elif ref_high is not None:
        fig.add_hline(
            y=ref_high, line_dash="dot",
            line_color="rgba(239,68,68,0.5)", line_width=1,
            annotation_text=f"Max: {ref_high}",
            annotation_position="top right",
        )

    # --- Parse timestamps for X-axis (Categorical to avoid gaps) ---
    x_labels = []
    hover_texts = []
    unit = obs_history[0].get("unit", "") if obs_history else ""

    for i, o in enumerate(obs_history):
        ts = o["timestamp"]
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ts_label = dt.strftime("%H:%M\n%d/%m")
            ts_hover = dt.strftime("%H:%M — %d/%m/%Y")
        except Exception:
            ts_label = ts[:10]
            ts_hover = ts
        
        x_labels.append(ts_label)
        hover_texts.append(
            f"<b>{o['display']} {unit}</b><br>"
            f"{ts_hover}"
        )

    values = [o["value"] for o in obs_history]
    colors = [o["color"] for o in obs_history]
    marker_colors = [MARKER_COLORS.get(c, "#94a3b8") for c in colors]

    # --- Dynamic Y-axis Range ---
    # Plotly's hrect forces the graph to include the entire reference band.
    # If the reference band is huge (e.g., 0 to 200) but values are small (3, 4), the line looks flat.
    min_val = min(values) if values else 0
    max_val = max(values) if values else 1
    val_range = max_val - min_val if max_val != min_val else (max_val * 0.2 if max_val > 0 else 1)
    
    # Target range
    y_min = min_val - val_range * 0.5
    y_max = max_val + val_range * 0.5
    
    # If reference range is somewhat close, include it, otherwise clamp it
    if ref_low is not None:
        y_min = min(y_min, max(ref_low - val_range * 0.2, 0))
    if ref_high is not None:
        if ref_high > max_val * 3:
            # Don't stretch the chart 3x just to show the ref_high bounds
            pass
        else:
            y_max = max(y_max, ref_high + val_range * 0.2)
            
    # --- Main trace ---
    fig.add_trace(go.Scatter(
        x=x_labels,  # Use strings for categorical axis
        y=values,
        mode="lines+markers+text",
        line=dict(color="#1e3a5f", width=2.5, shape="spline"),
        marker=dict(
            size=14,
            color=marker_colors,
            line=dict(width=2.5, color="white"),
            symbol="circle",
        ),
        text=[o["display"] for o in obs_history],
        textposition="top center",
        textfont=dict(size=11, color="#1e3a5f", family="Arial Black"),
        hovertext=hover_texts,
        hoverinfo="text",
        name=test_name,
    ))

    # --- Layout ---
    fig.update_layout(
        title=dict(
            text=f"📈 {test_name}",
            font=dict(size=14, color="#1e3a5f", family="Arial"),
            x=0.02,
        ),
        height=height,
        margin=dict(l=50, r=30, t=45, b=35),
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(
            type="category", # Force categorical axis so dates are perfectly spaced
            showgrid=False,
            tickfont=dict(size=10, color="#64748b"),
            linecolor="#e2e8f0",
        ),
        yaxis=dict(
            gridcolor="rgba(0,0,0,0.05)",
            tickfont=dict(size=10, color="#64748b"),
            linecolor="#e2e8f0",
            title=dict(text=unit, font=dict(size=10, color="#94a3b8")),
            zeroline=False,
            range=[y_min, y_max],
        ),
        showlegend=False,
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            bordercolor="#1e3a5f",
        ),
    )

    return fig


def get_trendable_tests(encounters_list) -> List[dict]:
    """
    Find all test codes that appear in 2+ encounters (can show trend).
    Returns list of {test_code, test_name, count, unit}.
    """
    from collections import Counter
    test_counts = Counter()
    test_info = {}

    for enc in encounters_list:
        seen_in_enc = set()
        for obs in enc.observations:
            if obs.value_numeric is not None and obs.test_code not in seen_in_enc:
                test_counts[obs.test_code] += 1
                seen_in_enc.add(obs.test_code)
                test_info[obs.test_code] = {
                    "test_name": obs.test_name,
                    "unit": obs.unit,
                }

    result = []
    for code, count in test_counts.items():
        if count >= 2:
            result.append({
                "test_code": code,
                "test_name": test_info[code]["test_name"],
                "unit": test_info[code]["unit"],
                "count": count,
            })

    return sorted(result, key=lambda x: x["test_name"])
