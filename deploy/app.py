"""
╔══════════════════════════════════════════════════════════════════╗
║        HIDU EWS — Clinical Early Warning System Dashboard        ║
║        Bệnh viện Trung ương Huế - Cơ sở 2                        ║
║        Module: Trực quan hoá Cận lâm sàng                        ║
╚══════════════════════════════════════════════════════════════════╝

Nguyên tắc thiết kế:
  1. Sinh lý học là động học → Trục thời gian
  2. Khoảng tham chiếu luôn từ PDF, không hardcode
  3. Phân tầng rủi ro → Giảm alarm fatigue
"""

import streamlit as st
import json
import io
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure modules are importable from app's directory
sys.path.insert(0, str(Path(__file__).parent))

from modules.pdf_parser import parse_lab_pdf_bytes
from modules.data_models import CATEGORY_LABELS, FLAG_LABELS
from modules.db import init_db, save_encounter, load_encounters_by_patient, load_all_patients, search_patients, delete_all_data, delete_patient
from modules.smart_alerts import run_all_alerts
from modules.clinical_summary import generate_clinical_summary, calculate_risk_score
from modules.qualitative_render import render_qualitative_value
from modules.trend_chart import render_trend_chart, build_obs_history, get_trendable_tests

# ─── Page Configuration ───────────────────────────────────────────────────────

st.set_page_config(
    page_title="HIDU EWS — Cận lâm sàng",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Initialize Database ──────────────────────────────────────────────────────

init_db()

# ─── Global CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ── Base Theme ── */
:root {
  --color-green-bg:  rgba(34, 197, 94,  0.18);
  --color-yellow-bg: rgba(234, 179, 8,  0.20);
  --color-orange-bg: rgba(249, 115, 22, 0.22);
  --color-red-bg:    rgba(239, 68,  68, 0.22);
  --color-gray-bg:   rgba(148, 163, 184, 0.12);

  --color-green-text:  #15803d;
  --color-yellow-text: #854d0e;
  --color-orange-text: #9a3412;
  --color-red-text:    #991b1b;
  --color-gray-text:   #475569;
}

/* ── Hide default Streamlit chrome ── */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display: none;}

/* ── Patient Header Card ── */
.patient-header {
  background: linear-gradient(135deg, #1e3a5f 0%, #1e5799 100%);
  border-radius: 12px;
  padding: 18px 24px;
  color: white;
  margin-bottom: 16px;
  box-shadow: 0 4px 15px rgba(30,87,153,0.25);
}
.patient-header h2 { margin: 0 0 4px 0; font-size: 1.4rem; font-weight: 700; }
.patient-header .meta { font-size: 0.88rem; opacity: 0.88; }
.patient-header .meta span { margin-right: 18px; }

/* ── Summary Stat Cards ── */
.stat-row { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.stat-card {
  flex: 1; min-width: 100px;
  border-radius: 10px;
  padding: 12px 16px;
  text-align: center;
  font-weight: 600;
}
.stat-card .count { font-size: 2rem; line-height: 1; }
.stat-card .label { font-size: 0.75rem; margin-top: 4px; opacity: 0.85; }
.stat-green  { background: var(--color-green-bg);  color: var(--color-green-text); }
.stat-yellow { background: var(--color-yellow-bg); color: var(--color-yellow-text); }
.stat-orange { background: var(--color-orange-bg); color: var(--color-orange-text); }
.stat-red    { background: var(--color-red-bg);    color: var(--color-red-text); }

/* ── Category Section Header ── */
.category-header {
  font-size: 0.9rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #1e3a5f;
  border-bottom: 2px solid #1e3a5f;
  padding-bottom: 5px;
  margin: 20px 0 8px 0;
}

/* ── Lab Table ── */
.lab-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
  margin-bottom: 6px;
}
.lab-table th {
  background: #1e3a5f;
  color: white;
  padding: 8px 12px;
  text-align: left;
  font-weight: 600;
  font-size: 0.8rem;
  letter-spacing: 0.03em;
  white-space: nowrap;
}
.lab-table th.center { text-align: center; }
.lab-table tr:hover { filter: brightness(0.96); }
.lab-table td {
  padding: 7px 12px;
  border-bottom: 1px solid rgba(0,0,0,0.05);
  vertical-align: middle;
}

/* ── Value Cell ── */
.val-cell {
  border-radius: 7px;
  padding: 6px 10px;
  text-align: center;
  font-weight: 700;
  font-size: 1rem;
  min-width: 70px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  white-space: nowrap;
}
.val-green  { background: var(--color-green-bg);  color: var(--color-green-text); }
.val-yellow { background: var(--color-yellow-bg); color: var(--color-yellow-text); border: 1px solid rgba(234,179,8,0.4); }
.val-orange { background: var(--color-orange-bg); color: var(--color-orange-text); border: 1px solid rgba(249,115,22,0.4); }
.val-red    { background: var(--color-red-bg);    color: var(--color-red-text);    border: 1px solid rgba(239,68,68,0.4); animation: pulse-red 2s infinite; }
.val-gray   { background: var(--color-gray-bg);   color: var(--color-gray-text); }

@keyframes pulse-red {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.0); }
  50%       { box-shadow: 0 0 0 4px rgba(239,68,68,0.2); }
}

/* ── Trend Indicator ── */
.trend-up   { color: #dc2626; font-weight: 700; }
.trend-down { color: #2563eb; font-weight: 700; }
.trend-flat { color: #64748b; }

/* ── Flag Badge ── */
.flag-badge {
  display: inline-block;
  border-radius: 4px;
  padding: 2px 7px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.flag-N { background: #dcfce7; color: #166534; }
.flag-H { background: #fef9c3; color: #854d0e; }
.flag-L { background: #dbeafe; color: #1d4ed8; }
.flag-A { background: #ffedd5; color: #9a3412; }
.flag-C { background: #fee2e2; color: #991b1b; }

/* ── Ref Range cell ── */
.ref-text { font-size: 0.78rem; color: #64748b; font-family: monospace; }

/* ── Upload zone ── */
.upload-card {
  border: 2px dashed #1e3a5f;
  border-radius: 14px;
  padding: 40px;
  text-align: center;
  background: rgba(30,87,153,0.04);
  margin: 20px 0;
}

/* ── Encounter timeline chip ── */
.enc-chip {
  display: inline-block;
  background: #1e3a5f;
  color: white;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.78rem;
  margin: 3px;
  cursor: pointer;
}
.enc-chip.active { background: #2563eb; }

/* ── Alert banner ── */
.alert-critical {
  background: var(--color-red-bg);
  border: 1px solid rgba(239,68,68,0.4);
  border-radius: 8px;
  padding: 10px 16px;
  color: var(--color-red-text);
  font-weight: 600;
  margin-bottom: 10px;
}
.alert-abnormal {
  background: var(--color-orange-bg);
  border: 1px solid rgba(249,115,22,0.35);
  border-radius: 8px;
  padding: 10px 16px;
  color: var(--color-orange-text);
  font-weight: 600;
  margin-bottom: 10px;
}

/* ── Machine chip ── */
.machine-chip {
  display: inline-block;
  background: #f1f5f9;
  color: #475569;
  padding: 1px 7px;
  border-radius: 4px;
  font-size: 0.72rem;
}

/* ── Sidebar ── */
.sidebar-section {
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
}

/* ── Qualitative Indicators ── */
.qualitative-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 8px;
  padding: 5px 14px;
  font-weight: 700;
  font-size: 0.88rem;
  white-space: nowrap;
}
.qual-negative {
  background: rgba(34,197,94,0.15);
  color: #15803d;
}
.qual-positive {
  background: rgba(239,68,68,0.2);
  color: #991b1b;
  animation: pulse-red 1.5s infinite;
}

/* ── Graded Bar ── */
.graded-bar-container {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.graded-dots {
  display: inline-flex;
  gap: 3px;
}
.graded-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.graded-label {
  font-weight: 700;
  font-size: 0.82rem;
}

/* ── Blood Type Chip ── */
.blood-type-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 8px;
  padding: 5px 14px;
  font-weight: 700;
  font-size: 0.9rem;
  white-space: nowrap;
}
.blood-chip-abo {
  background: #ede9fe;
  color: #6d28d9;
}
.blood-chip-rh-pos {
  background: #dcfce7;
  color: #166534;
}
.blood-chip-rh-neg {
  background: #fee2e2;
  color: #991b1b;
}

/* ── Clinical Summary Panel ── */
.clinical-summary {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 16px;
}
.clinical-summary h3 {
  font-size: 0.95rem;
  font-weight: 700;
  color: #1e3a5f;
  margin: 0 0 12px 0;
  border-bottom: 2px solid #1e3a5f;
  padding-bottom: 6px;
}
.summary-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(0,0,0,0.04);
  font-size: 0.85rem;
  line-height: 1.5;
}
.summary-item:last-child { border-bottom: none; }
.summary-icon { font-size: 1.1rem; flex-shrink: 0; margin-top: 1px; }
.summary-title { font-weight: 700; color: #1e3a5f; margin-right: 6px; }
.summary-text { color: #475569; }

/* ── Smart Alert Cards ── */
.smart-alert {
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 8px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 0.84rem;
  line-height: 1.45;
}
.smart-alert-red {
  background: rgba(239,68,68,0.12);
  border-left: 4px solid #ef4444;
  color: #7f1d1d;
}
.smart-alert-orange {
  background: rgba(249,115,22,0.12);
  border-left: 4px solid #f97316;
  color: #7c2d12;
}
.smart-alert-yellow {
  background: rgba(234,179,8,0.12);
  border-left: 4px solid #eab308;
  color: #713f12;
}
.alert-icon { font-size: 1.2rem; flex-shrink: 0; }
.alert-body { flex: 1; }
.alert-name { font-weight: 700; margin-bottom: 2px; }
.alert-msg { opacity: 0.9; }

/* ── Risk Score Gauge ── */
.risk-gauge-container {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 18px;
  margin-bottom: 16px;
}
.risk-score-number {
  font-size: 2.4rem;
  font-weight: 800;
  line-height: 1;
}
.risk-score-bar {
  flex: 1;
  height: 10px;
  background: #e2e8f0;
  border-radius: 5px;
  overflow: hidden;
}
.risk-score-fill {
  height: 100%;
  border-radius: 5px;
  transition: width 0.5s ease;
}
.risk-label {
  font-weight: 700;
  font-size: 0.85rem;
}
.risk-sublabel {
  font-size: 0.72rem;
  color: #94a3b8;
}

/* ── History Card ── */
.history-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: all 0.15s;
}
.history-card:hover {
  background: #eef2ff;
  border-color: #6366f1;
}
.history-name { font-weight: 600; color: #1e3a5f; font-size: 0.85rem; }
.history-meta { font-size: 0.72rem; color: #94a3b8; }

/* ── Previous Value & Delta Columns ── */
.prev-val {
  font-size: 0.78rem;
  color: #94a3b8;
  font-family: monospace;
  white-space: nowrap;
}
.delta-cell {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 0.76rem;
  font-weight: 700;
  white-space: nowrap;
}
.delta-up {
  background: rgba(239,68,68,0.1);
  color: #dc2626;
}
.delta-down {
  background: rgba(37,99,235,0.1);
  color: #2563eb;
}
.delta-flat {
  background: rgba(100,116,139,0.08);
  color: #64748b;
}
.delta-new {
  background: rgba(139,92,246,0.1);
  color: #7c3aed;
  font-weight: 600;
  font-size: 0.72rem;
}
.ts-subheader {
  font-size: 0.68rem;
  color: #94a3b8;
  font-weight: 400;
  display: block;
}

/* ── Mobile & Tablet Responsive Adjustments ── */
@media (max-width: 768px) {
  /* Reduce side padding on mobile */
  .block-container { padding-top: 1.5rem !important; padding-left: 0.8rem !important; padding-right: 0.8rem !important; }
  
  /* Patient Header compactness */
  .patient-header { padding: 12px 14px; margin-bottom: 12px; }
  .patient-header h2 { font-size: 1.15rem; }
  .patient-header .meta { line-height: 1.4; display: flex; flex-wrap: wrap; gap: 8px; }
  .patient-header .meta span { margin-right: 0; }
  
  /* Stats Cards */
  .stat-row { flex-wrap: wrap; gap: 8px; }
  .stat-card { flex: 1 1 45%; min-width: 45%; padding: 10px 8px; }
  .stat-card .count { font-size: 1.6rem; }
  
  /* Table Responsiveness - Enable horizontal scroll */
  .table-responsive {
    width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin-bottom: 12px;
    border-radius: 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }
  .lab-table { margin-bottom: 0; min-width: 600px; } /* Ensure minimum width to trigger scroll */
  .lab-table th, .lab-table td { padding: 6px 8px; font-size: 0.82rem; }
  .val-cell { min-width: 60px; font-size: 0.9rem; padding: 4px 6px; }
  
  /* Risk Gauge Stacking */
  .risk-gauge-container { flex-direction: column; align-items: flex-start; gap: 10px; padding: 12px; }
  
  /* Actionable UI touches */
  .enc-chip { padding: 6px 12px; font-size: 0.85rem; margin-bottom: 6px; display: inline-block; }
  button[kind="secondary"], button[kind="primary"] { min-height: 44px; } /* Better touch target */
}

/* ── Lab Card (Mobile Mode) ── */
.lab-card {
  background: white; border: 1px solid rgba(0,0,0,0.06); border-radius: 8px;
  padding: 10px 14px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.lab-card-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 6px; padding-bottom: 6px; border-bottom: 1px dashed rgba(0,0,0,0.08);
}
.lab-card-name { font-weight: 700; color: #1e3a5f; font-size: 0.9rem; }
.lab-card-machine { font-size: 0.72rem; color: #94a3b8; background: #f8fafc; padding: 1px 6px; border-radius: 4px; }
.lab-card-body { display: flex; justify-content: space-between; align-items: center; }
.lab-card-val { font-size: 1.1rem; }
.lab-card-meta { text-align: right; font-size: 0.75rem; color: #64748b; line-height: 1.4; }
</style>
""", unsafe_allow_html=True)


# ─── Helper: Color Rendering ──────────────────────────────────────────────────

COLOR_EMOJI = {
    "green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴", "gray": "⚪"
}

TREND_CLASS = {
    "↑": "trend-up", "↗": "trend-up",
    "↓": "trend-down", "↘": "trend-down",
    "→": "trend-flat",
}


def render_value_cell(obs) -> str:
    """Render colored value cell HTML, with qualitative rendering support."""
    # Try qualitative renderer first
    qual_html = render_qualitative_value(obs)
    if qual_html is not None:
        # Add trend if available
        if obs.trend:
            cls = TREND_CLASS.get(obs.trend, "trend-flat")
            qual_html += f' <span class="{cls}" title="Xu hướng">{obs.trend}</span>'
        return qual_html

    # Default numeric rendering
    color = obs.color_code
    val = obs.display_value()
    trend_html = ""
    if obs.trend:
        cls = TREND_CLASS.get(obs.trend, "trend-flat")
        trend_html = f'<span class="{cls}" title="Xu hướng">{obs.trend}</span>'
    return f'<span class="val-cell val-{color}">{val}{trend_html}</span>'


def render_flag_badge(flag: str) -> str:
    label = FLAG_LABELS.get(flag, flag)
    return f'<span class="flag-badge flag-{flag}">{label}</span>'


def render_ref_range(obs) -> str:
    ref = obs.reference_range
    text = ref.text if ref.text else "—"
    unit = f" {obs.unit}" if obs.unit else ""
    return f'<span class="ref-text">{text}{unit}</span>'


# ─── Dashboard Components ─────────────────────────────────────────────────────

def render_patient_header(encounter):
    """Render patient demographic header."""
    ts = encounter.clinical_timestamp
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ts_display = dt.strftime("%H:%M — %d/%m/%Y")
        except Exception:
            ts_display = ts
    else:
        ts_display = "N/A"

    gender_icon = "♀️" if encounter.gender == "Female" else "♂️"
    gender_label = "Nữ" if encounter.gender == "Female" else "Nam"

    html = f"""
<div class="patient-header">
<h2>🏥 {encounter.patient_name or "Không rõ tên"}</h2>
<div class="meta">
<span>{gender_icon} {gender_label}</span>
<span>📅 {encounter.dob or "N/A"}</span>
<span>🆔 BN {encounter.patient_id or "N/A"}</span>
<span>🕐 Lấy mẫu: {ts_display}</span>
<span>📋 SID: {encounter.encounter_id.replace("SID_", "")}</span>
</div>
{f'<div class="meta" style="margin-top:4px">👨‍⚕️ Chỉ định: {encounter.ordering_physician}</div>' if encounter.ordering_physician else ''}
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


def render_summary_stats(encounter):
    """Render summary stat cards."""
    counts = encounter.summary_counts()

    html = f"""
<div class="stat-row">
<div class="stat-card stat-green">
<div class="count">{counts["green"]}</div>
<div class="label">Bình thường</div>
</div>
<div class="stat-card stat-yellow">
<div class="count">{counts["yellow"]}</div>
<div class="label">Chú ý</div>
</div>
<div class="stat-card stat-orange">
<div class="count">{counts["orange"]}</div>
<div class="label">Bất thường</div>
</div>
<div class="stat-card stat-red">
<div class="count">{counts["red"]}</div>
<div class="label">🚨 Nguy hiểm</div>
</div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


def render_risk_gauge(encounter):
    """Render risk score gauge."""
    score, level_text, level_color = calculate_risk_score(encounter)
    fill_pct = score * 10

    html = f"""
<div class="risk-gauge-container">
<div>
<div class="risk-score-number" style="color:{level_color}">{score}</div>
<div class="risk-sublabel">/ 10</div>
</div>
<div style="flex:1">
<div class="risk-label" style="color:{level_color}">{level_text}</div>
<div class="risk-score-bar">
<div class="risk-score-fill" style="width:{fill_pct}%;background:{level_color}"></div>
</div>
<div class="risk-sublabel">Điểm cảnh báo sớm</div>
</div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


def render_vitals_section(encounter, encounters_list):
    """Render and handle vitals input for the encounter."""
    st.markdown("### 🫀 Sinh hiệu & Thể trạng")
    if not hasattr(encounter, "vitals"):
        encounter.vitals = {}
        
    vitals = encounter.vitals
    
    with st.expander("Chỉnh sửa/Nhập Sinh hiệu", expanded=not bool(vitals)):
        with st.form(f"vitals_form_{encounter.encounter_id}"):
            c1, c2, c3 = st.columns(3)
            with c1:
                sbp = st.number_input("Huyết áp tâm thu (mmHg)", min_value=0, max_value=300, value=int(vitals.get("sbp", 0)))
                dbp = st.number_input("Huyết áp tâm trương (mmHg)", min_value=0, max_value=200, value=int(vitals.get("dbp", 0)))
                hr = st.number_input("Mạch (lần/phút)", min_value=0, max_value=300, value=int(vitals.get("hr", 0)))
            with c2:
                temp = st.number_input("Nhiệt độ (°C)", min_value=30.0, max_value=45.0, value=float(vitals.get("temp", 37.0)), step=0.1)
                rr = st.number_input("Nhịp thở (lần/phút)", min_value=0, max_value=60, value=int(vitals.get("rr", 0)))
                spo2 = st.number_input("SpO2 (%)", min_value=0, max_value=100, value=int(vitals.get("spo2", 0)))
            with c3:
                weight = st.number_input("Cân nặng (kg)", min_value=0.0, max_value=200.0, value=float(vitals.get("weight", 0.0)), step=0.1)
                height = st.number_input("Chiều cao (cm)", min_value=0.0, max_value=250.0, value=float(vitals.get("height", 0.0)), step=1.0)
                pain = st.number_input("Điểm đau (VAS 0-10)", min_value=0, max_value=10, value=int(vitals.get("pain", 0)))

            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                submitted_single = st.form_submit_button("💾 Lưu cho mốc thời gian này")
            with c_btn2:
                submitted_all = st.form_submit_button("💾 Lưu chung cho TẤT CẢ các mốc")

            if submitted_single or submitted_all:
                new_vitals = {
                    "sbp": sbp, "dbp": dbp, "hr": hr, "temp": temp, "rr": rr,
                    "spo2": spo2, "weight": weight, "height": height, "pain": pain
                }
                if height > 0 and weight > 0:
                    new_vitals["bmi"] = round(weight / ((height/100.0)**2), 1)

                from modules.db import save_encounter
                
                if submitted_all and encounters_list:
                    for enc in encounters_list:
                        if not hasattr(enc, "vitals"):
                            enc.vitals = {}
                        enc.vitals.update(new_vitals)
                        save_encounter(enc)
                else:
                    encounter.vitals.update(new_vitals)
                    save_encounter(encounter)
                
                # Keep state updated across encounter changes in session state
                st.session_state["vitals_updated"] = True
                st.rerun()

    if vitals:
        # Display vitals summary
        vc1, vc2, vc3, vc4 = st.columns(4)
        vc1.metric("Huyết áp", f"{int(vitals.get('sbp', 0))} / {int(vitals.get('dbp', 0))}" if vitals.get('sbp') else "---")
        vc2.metric("Mạch / Nhịp thở", f"{int(vitals.get('hr', 0))} / {int(vitals.get('rr', 0))}" if vitals.get('hr') else "---")
        vc3.metric("Nhiệt độ / SpO2", f"{vitals.get('temp', 0)} °C / {int(vitals.get('spo2', 0))}%" if vitals.get('temp') else "---")
        bmi_str = f"BMI: {vitals.get('bmi')} " if vitals.get('bmi') else ""
        vc4.metric("Thể trạng", f"{vitals.get('weight', 0)} kg", delta=bmi_str, delta_color="off" if bmi_str else "normal")


def render_clinical_summary_panel(encounter):
    """Render the clinical summary panel."""
    summaries = generate_clinical_summary(encounter)
    if not summaries:
        return

    items_html = ""
    for s in summaries:
        items_html += f"""<div class="summary-item">
<span class="summary-icon">{s['icon']}</span>
<div>
<span class="summary-title">{s['title']}:</span>
<span class="summary-text">{s['text']}</span>
</div>
</div>"""

    html = f"""
<div class="clinical-summary">
<h3>📋 TÓM TẮT LÂM SÀNG</h3>
{items_html}
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


def render_smart_alerts(encounter, previous_encounter=None,
                        encounters_list=None, current_index=0):
    """Render smart alert cards."""
    alerts = run_all_alerts(
        encounter, previous_encounter,
        encounters_list, current_index,
    )
    if not alerts:
        return

    html = '<div style="margin-bottom:16px">'
    html += '<div style="font-size:0.85rem;font-weight:700;color:#1e3a5f;margin-bottom:8px">⚡ CẢNH BÁO THÔNG MINH</div>'
    for alert in alerts:
        level_class = f"smart-alert-{alert['level']}"
        html += f"""<div class="smart-alert {level_class}">
<span class="alert-icon">{alert['icon']}</span>
<div class="alert-body">
<div class="alert-name">{alert['name']}</div>
<div class="alert-msg">{alert['message']}</div>
</div>
</div>"""
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def _format_timestamp_short(ts: str) -> str:
    """Format ISO timestamp to short display: HH:MM dd/mm."""
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%H:%M %d/%m")
    except Exception:
        return ts[:10] if len(ts) >= 10 else ts


def _render_delta_cell(current_val, prev_val, unit: str) -> str:
    """Render delta between current and previous numeric values."""
    if current_val is None or prev_val is None:
        return ""
    delta = current_val - prev_val
    if abs(delta) < 0.001:
        return '<span class="delta-cell delta-flat">→ 0</span>'
    sign = "+" if delta > 0 else ""
    # Format: remove excessive decimals
    if abs(delta) >= 10:
        delta_str = f"{delta:.0f}"
    elif abs(delta) >= 1:
        delta_str = f"{delta:.1f}"
    else:
        delta_str = f"{delta:.2f}"
    arrow = "↑" if delta > 0 else "↓"
    css_class = "delta-up" if delta > 0 else "delta-down"
    return f'<span class="delta-cell {css_class}">{arrow} {sign}{delta_str}</span>'


def render_lab_table(observations, show_all: bool, ui_mode: str = "💻 Bảng lưới",
                     prev_encounter=None,
                     current_timestamp: str = "", prev_timestamp: str = ""):
    """Render the main heatmap table grouped by category.
    When prev_encounter is provided, adds columns for previous value and delta."""
    if not observations:
        st.info("Không có dữ liệu xét nghiệm.")
        return

    # Build previous values map
    has_prev = prev_encounter is not None and bool(prev_encounter.observations)
    prev_map = {}
    if has_prev:
        for obs in prev_encounter.observations:
            prev_map[obs.test_code] = obs

    # Format timestamps for column headers
    ts_current = _format_timestamp_short(current_timestamp)
    ts_prev = _format_timestamp_short(prev_timestamp)

    # Group by category
    groups = {}
    for obs in observations:
        cat = obs.category
        groups.setdefault(cat, []).append(obs)

    category_order = ["CBC", "COAG", "BLOOD_TYPE", "CHEMISTRY", "RAPID", "URINALYSIS", "OTHER"]

    for cat in category_order:
        if cat not in groups:
            continue

        obs_list = groups[cat]

        # Filter if not showing all
        if not show_all:
            obs_list = [o for o in obs_list if o.color_code not in ("green", "gray")]
            if not obs_list:
                continue

        label = CATEGORY_LABELS.get(cat, cat)
        st.markdown(f'<div class="category-header">{label}</div>', unsafe_allow_html=True)

        if ui_mode == "📱 Dạng thẻ":
            cards_html = ""
            for obs in obs_list:
                machine_span = f'<span class="lab-card-machine">{obs.machine}</span>' if obs.machine else ""
                val_html = render_value_cell(obs)
                flag_html = render_flag_badge(obs.interpretation_flag)
                ref_html = render_ref_range(obs)
                
                prev_delta_html = ""
                if has_prev:
                    prev_obs = prev_map.get(obs.test_code)
                    if prev_obs:
                        delta_html = _render_delta_cell(obs.value_numeric, prev_obs.value_numeric, obs.unit)
                        prev_delta_html = f'Lần trước: {prev_obs.display_value()} {delta_html}'
                    else:
                        prev_delta_html = '<span class="delta-new">— mới</span>'
                
                cards_html += f"""
                <div class="lab-card">
                  <div class="lab-card-header">
                    <div class="lab-card-name" style="display:flex;align-items:center;gap:6px;">{obs.test_name} {flag_html}</div>
                    {machine_span}
                  </div>
                  <div class="lab-card-body">
                    <div class="lab-card-val">{val_html}</div>
                    <div class="lab-card-meta">
                      {ref_html}<br>
                      {f'<span style="font-size:0.72rem">{prev_delta_html}</span>' if has_prev else ''}
                    </div>
                  </div>
                </div>
                """
            st.markdown(cards_html, unsafe_allow_html=True)
            continue

        rows_html = ""
        for obs in obs_list:
            machine_html = (
                f'<span class="machine-chip">{obs.machine}</span>'
                if obs.machine else ""
            )

            # Previous value and delta columns
            prev_html = ""
            delta_html = ""
            if has_prev:
                prev_obs = prev_map.get(obs.test_code)
                if prev_obs:
                    prev_display = prev_obs.display_value()
                    prev_color = prev_obs.color_code
                    prev_html = f'<span class="prev-val" title="Lần trước">{prev_display}</span>'
                    delta_html = _render_delta_cell(
                        obs.value_numeric, prev_obs.value_numeric, obs.unit
                    )
                else:
                    prev_html = '<span class="delta-new">— mới</span>'
                    delta_html = ""

            if has_prev:
                rows_html += f"""<tr>
<td>{obs.test_name}</td>
<td style="text-align:center">{render_value_cell(obs)}</td>
<td style="text-align:center">{prev_html}</td>
<td style="text-align:center">{delta_html}</td>
<td style="text-align:center">{render_ref_range(obs)}</td>
<td style="text-align:center">{render_flag_badge(obs.interpretation_flag)}</td>
<td style="text-align:center">{machine_html}</td>
</tr>"""
            else:
                rows_html += f"""<tr>
<td>{obs.test_name}</td>
<td style="text-align:center">{render_value_cell(obs)}</td>
<td style="text-align:center">{render_ref_range(obs)}</td>
<td style="text-align:center">{render_flag_badge(obs.interpretation_flag)}</td>
<td style="text-align:center">{machine_html}</td>
</tr>"""

        # Table header depends on whether we have previous data
        if has_prev:
            table_html = f"""
<div class="table-responsive">
<table class="lab-table">
<thead>
<tr>
<th>Tên xét nghiệm</th>
<th class="center">Kết quả<span class="ts-subheader">🕐 {ts_current}</span></th>
<th class="center">Lần trước<span class="ts-subheader">🕐 {ts_prev}</span></th>
<th class="center">Thay đổi</th>
<th class="center">Tham chiếu + Đơn vị</th>
<th class="center">Phân loại</th>
<th class="center">Máy XN</th>
</tr>
</thead>
<tbody>{rows_html}</tbody>
</table>
</div>
"""
        else:
            table_html = f"""
<div class="table-responsive">
<table class="lab-table">
<thead>
<tr>
<th>Tên xét nghiệm</th>
<th class="center">Kết quả{f'<span class="ts-subheader">🕐 {ts_current}</span>' if ts_current else ''}</th>
<th class="center">Tham chiếu + Đơn vị</th>
<th class="center">Phân loại</th>
<th class="center">Máy XN</th>
</tr>
</thead>
<tbody>{rows_html}</tbody>
</table>
</div>
"""
        st.markdown(table_html, unsafe_allow_html=True)


def render_imaging_section(encounter):
    """Render imaging reports (Ultrasound, X-Ray) inside an expander."""
    if not encounter or not getattr(encounter, "imaging_reports", None):
        return

    reports = encounter.imaging_reports
    if not reports:
        return

    with st.expander(f"📟 Chẩn đoán Hình ảnh ({len(reports)} kết quả) — Ấn để xem chỉ định", expanded=False):
        for rep in reports:
            st.markdown(f"**{rep['type']}**")
            st.info(rep['conclusion'], icon="📌")
            st.markdown("---")


def render_trend_section(encounters_list, selected_enc):
    """Render trend chart section for multi-encounter view."""
    if not encounters_list or len(encounters_list) < 2:
        return

    trendable = get_trendable_tests(encounters_list)
    if not trendable:
        return

    with st.expander("📈 Biểu đồ Xu hướng — Theo dõi chỉ số qua thời gian", expanded=False):
        # Test selection
        test_options = {t["test_code"]: f"{t['test_name']} ({t['count']} lần)" for t in trendable}
        selected_codes = st.multiselect(
            "Chọn chỉ số cần xem xu hướng:",
            options=list(test_options.keys()),
            format_func=lambda x: test_options[x],
            default=list(test_options.keys())[:3],  # Default show first 3
            key="trend_select",
        )

        if not selected_codes:
            st.info("Chọn ít nhất 1 chỉ số để xem biểu đồ xu hướng.")
            return

        # Render charts in 2-column grid
        cols = st.columns(2)
        for i, code in enumerate(selected_codes):
            history = build_obs_history(encounters_list, code)
            if len(history) < 2:
                continue
            info = next(t for t in trendable if t["test_code"] == code)
            ref_low = history[-1].get("ref_low")
            ref_high = history[-1].get("ref_high")

            fig = render_trend_chart(
                history, info["test_name"],
                ref_low=ref_low, ref_high=ref_high,
            )
            with cols[i % 2]:
                st.plotly_chart(fig, use_container_width=True, key=f"trend_{code}")


# ─── Sidebar ──────────────────────────────────────────────────────────────────

def render_sidebar(encounter=None):
    with st.sidebar:
        st.markdown("## 🏥 HIDU EWS")
        st.markdown("**Hệ thống Cảnh báo Sớm Lâm sàng**")
        st.markdown("---")

        # Upload section
        st.markdown("### 📂 Tải kết quả XN")
        uploaded = st.file_uploader(
            "Chọn file PDF kết quả xét nghiệm",
            type=["pdf"],
            help="Hỗ trợ định dạng PDF từ BVTW Huế và các BV tương thích",
            key="pdf_uploader",
        )

        st.markdown("---")

        # Patient history from database
        st.markdown("### 📁 Lịch sử bệnh nhân")
        patients = load_all_patients()
        if patients:
            search_query = st.text_input(
                "🔍 Tìm kiếm...",
                placeholder="Tên hoặc mã BN",
                key="patient_search",
            )
            if search_query:
                patients = search_patients(search_query)

            patient_options = {
                p["patient_id"]: f"{p['patient_name']} ({p['patient_id']}) — {p['encounter_count']} lần XN"
                for p in patients
            }
            if patient_options:
                selected_pid = st.selectbox(
                    "Chọn bệnh nhân:",
                    options=list(patient_options.keys()),
                    format_func=lambda x: patient_options[x],
                    key="patient_select",
                )
                if st.button("📂 Tải lịch sử", use_container_width=True, key="load_history"):
                    history_encounters = load_encounters_by_patient(selected_pid)
                    if history_encounters:
                        st.session_state["encounters_list"] = history_encounters
                        st.session_state["encounter"] = history_encounters[-1]
                        st.session_state["parse_error"] = None
                        st.rerun()
                
                # Delete options directly below
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Xoá BN này", use_container_width=True, help="Xoá toàn bộ lịch sử của bệnh nhân đang chọn"):
                        delete_patient(selected_pid)
                        if encounter and encounter.patient_id == selected_pid:
                            for key in ["encounter", "encounters_list", "last_file_key", "parse_error"]:
                                st.session_state.pop(key, None)
                        st.rerun()
                with col2:
                    if st.button("🚨 Xoá tất cả", use_container_width=True, type="primary", help="Xoá toàn bộ cơ sở dữ liệu bệnh nhân"):
                        delete_all_data()
                        for key in ["encounter", "encounters_list", "last_file_key", "parse_error"]:
                            st.session_state.pop(key, None)
                        st.rerun()
            else:
                st.caption("Không tìm thấy kết quả.")
        else:
            st.caption("Chưa có dữ liệu. Tải PDF để bắt đầu.")

        st.markdown("---")

        # Filter controls
        st.markdown("### 🔍 Bộ lọc hiển thị")
        show_all = st.toggle(
            "Hiện tất cả chỉ số",
            value=False,
            help="Tắt = chỉ hiện chỉ số bất thường (khuyến nghị)"
        )
        
        st.markdown("### 📱 Chế độ giao diện")
        ui_mode = st.radio(
            "Chọn kiểu xem:",
            ["💻 Bảng lưới", "📱 Dạng thẻ"],
            horizontal=True,
            label_visibility="collapsed",
            help="Dạng thẻ (Card view) tối ưu cho thao tác trên điện thoại di động."
        )

        if encounter:
            st.markdown("---")
            st.markdown("### 📊 Tổng kết")
            counts = encounter.summary_counts()
            cols = st.columns(2)
            with cols[0]:
                st.metric("🟢 Bình thường", counts["green"])
                st.metric("🟠 Bất thường", counts["orange"])
            with cols[1]:
                st.metric("🟡 Chú ý", counts["yellow"])
                st.metric("🔴 Nguy hiểm", counts["red"])

            st.markdown("---")
            st.markdown("### 💾 Xuất dữ liệu")

            # Export JSON
            json_str = json.dumps(encounter.to_fhir_json(), ensure_ascii=False, indent=2)
            st.download_button(
                label="📄 Tải JSON (FHIR)",
                data=json_str,
                file_name=f"lab_{encounter.encounter_id}_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True,
            )
            if st.button("🗑️ Xoá phiên hiện tại", use_container_width=True, type="secondary"):
                for key in ["encounter", "encounters_list", "last_file_key", "parse_error"]:
                    st.session_state.pop(key, None)
                st.rerun()

        st.markdown("---")
        st.markdown(
            '<div style="font-size:0.75rem;color:#94a3b8;text-align:center;">'
            'HIDU EWS v2.0<br>BVTW Huế Cơ sở 2<br>Sprint 1+2 — Nâng cấp</div>',
            unsafe_allow_html=True
        )

    return uploaded, show_all, ui_mode


# ─── Main Application ─────────────────────────────────────────────────────────

def main():
    # Session state
    if "encounter" not in st.session_state:
        st.session_state["encounter"] = None
    if "parse_error" not in st.session_state:
        st.session_state["parse_error"] = None

    # Render sidebar and get controls
    uploaded, show_all, ui_mode = render_sidebar(st.session_state["encounter"])

    # Process uploaded PDF
    if uploaded is not None:
        file_key = f"{uploaded.name}_{uploaded.size}"
        if st.session_state.get("last_file_key") != file_key:
            st.session_state["last_file_key"] = file_key
            with st.spinner("⏳ Đang đọc và phân tích kết quả xét nghiệm..."):
                try:
                    pdf_bytes = uploaded.read()
                    parsed_encounters = parse_lab_pdf_bytes(pdf_bytes)
                    if parsed_encounters:
                        # Save all encounters to database
                        for enc in parsed_encounters:
                            save_encounter(enc)
                            
                        # Set the most recent one as current
                        encounter = parsed_encounters[-1]
                        st.session_state["encounter"] = encounter
                        st.session_state["parse_error"] = None

                        # Manage encounters list (load from DB for this patient)
                        if encounter.patient_id:
                            enc_list = load_encounters_by_patient(encounter.patient_id)
                        else:
                            enc_list = st.session_state.get("encounters_list", [])
                            existing_ids = {e.encounter_id for e in enc_list}
                            for enc in parsed_encounters:
                                if enc.encounter_id not in existing_ids:
                                    enc_list.append(enc)
                                    existing_ids.add(enc.encounter_id)
                        
                        st.session_state["encounters_list"] = enc_list

                        total_obs = sum(len(e.observations) for e in parsed_encounters)
                        st.success(
                            f"✅ Phân tích thành công **{len(parsed_encounters)} lần khám** với tổng cộng **{total_obs} chỉ số** "
                            f"từ file **{uploaded.name}** và đã lưu vào cơ sở dữ liệu."
                        )
                    else:
                        st.session_state["parse_error"] = "Không tìm thấy dữ liệu xét nghiệm trong file PDF."
                except Exception as e:
                    import traceback
                    st.session_state["parse_error"] = f"Lỗi phân tích: {str(e)}\n{traceback.format_exc()}"

    encounter = st.session_state.get("encounter")
    parse_error = st.session_state.get("parse_error")

    # ── Main Content Area ──
    if parse_error:
        st.error(parse_error)

    if encounter is None:
        # Welcome / empty state
        st.markdown("""
<div style="text-align:center;padding:40px 0;">
<div style="font-size:4rem;">🏥</div>
<h1 style="color:#1e3a5f;margin:10px 0;">HIDU EWS</h1>
<p style="font-size:1.1rem;color:#475569;max-width:500px;margin:0 auto;">
Hệ thống Trực quan hoá & Cảnh báo Sớm Kết quả Cận lâm sàng
</p>
<hr style="border-color:#e2e8f0;max-width:400px;margin:24px auto;">
<p style="color:#64748b;">
← Tải file PDF kết quả xét nghiệm ở thanh bên trái để bắt đầu
</p>
</div>
""", unsafe_allow_html=True)

        # Feature overview
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            **📊 Heatmap thời gian thực**  
            Mã màu 4 cấp độ rủi ro  
            Phân tầng: Xanh / Vàng / Cam / Đỏ
            """)
        with col2:
            st.markdown("""
            **📈 Biểu đồ Xu hướng**  
            Theo dõi chỉ số qua thời gian  
            Phát hiện xu hướng xấu dần
            """)
        with col3:
            st.markdown("""
            **⚡ Cảnh báo Thông minh**  
            Phát hiện tổ hợp nguy hiểm  
            Tóm tắt lâm sàng tự động
            """)

        col4, col5, col6 = st.columns(3)
        with col4:
            st.markdown("""
            **🔍 Lọc thông minh**  
            Ẩn chỉ số bình thường  
            Chỉ hiện chỉ số bất thường
            """)
        with col5:
            st.markdown("""
            **💾 Lưu trữ dữ liệu**  
            SQLite persistence  
            Lịch sử bệnh nhân đầy đủ
            """)
        with col6:
            st.markdown("""
            **📋 Chuẩn FHIR**  
            Dữ liệu JSON xuất khẩu  
            Khoảng tham chiếu động
            """)
        return

    # ── Multi-Encounter Timeline ──
    encounters_list = st.session_state.get("encounters_list", [encounter])
    ids = [e.encounter_id for e in encounters_list]
    if encounter.encounter_id not in ids:
        encounters_list.append(encounter)
        st.session_state["encounters_list"] = encounters_list

    # Timeline selector (if multiple)
    selected_enc = encounter
    prev_enc = None
    current_index = len(encounters_list) - 1

    if len(encounters_list) > 1:
        st.markdown("**📅 Lịch sử xét nghiệm**")
        enc_labels = [
            f"T{i} — {e.clinical_timestamp[:10] if e.clinical_timestamp else 'N/A'}"
            for i, e in enumerate(encounters_list)
        ]
        sel_idx = st.radio(
            "Chọn mốc thời gian:",
            range(len(encounters_list)),
            format_func=lambda i: enc_labels[i],
            horizontal=True,
            index=len(encounters_list) - 1,
        )
        selected_enc = encounters_list[sel_idx]
        current_index = sel_idx
        prev_enc = encounters_list[sel_idx - 1] if sel_idx > 0 else None

        # Re-process with trend vs previous
        if prev_enc:
            from modules.rule_engine import process_encounter
            selected_enc = process_encounter(selected_enc, prev_enc)

    # ── Dashboard ──
    render_patient_header(selected_enc)
    render_summary_stats(selected_enc)
    render_vitals_section(selected_enc, encounters_list)
    render_risk_gauge(selected_enc)

    # Smart alerts
    render_smart_alerts(
        selected_enc,
        previous_encounter=prev_enc,
        encounters_list=encounters_list,
        current_index=current_index,
    )

    # Clinical summary
    render_clinical_summary_panel(selected_enc)

    # Filter toggle display
    if show_all:
        st.caption(f"📋 Hiển thị tất cả {len(selected_enc.observations)} chỉ số")
    else:
        abnormal = selected_enc.get_abnormal()
        if abnormal:
            st.caption(
                f"🔍 Đang lọc: hiển thị {len(abnormal)} / {len(selected_enc.observations)} chỉ số bất thường. "
                "Bật **'Hiện tất cả'** ở sidebar để xem đầy đủ."
            )
        else:
            st.success(
                "✅ Tất cả chỉ số trong giới hạn bình thường. "
                "Bật **'Hiện tất cả'** ở sidebar để xem bảng đầy đủ."
            )

    render_lab_table(
        selected_enc.observations, show_all, ui_mode=ui_mode,
        prev_encounter=prev_enc,
        current_timestamp=selected_enc.clinical_timestamp,
        prev_timestamp=prev_enc.clinical_timestamp if prev_enc else "",
    )

    # Imaging reports
    render_imaging_section(selected_enc)

    # Trend charts
    render_trend_section(encounters_list, selected_enc)

    # Footer
    st.markdown("""
<div style="margin-top:32px;padding:12px;text-align:center;
            color:#94a3b8;font-size:0.75rem;border-top:1px solid #e2e8f0;">
⚠️ Kết quả phân tích chỉ mang tính tham khảo. Quyết định lâm sàng thuộc thẩm quyền bác sĩ điều trị.
&nbsp;&nbsp;|&nbsp;&nbsp; HIDU EWS v2.0 — BVTW Huế Cơ sở 2
</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
