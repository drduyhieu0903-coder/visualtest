# HIDU EWS — Lộ trình Phát triển Tính năng
> **Phiên bản tài liệu:** 1.1  
> **Trạng thái:** Bản đặc tả kỹ thuật — Dành cho đội phát triển  
> **Nguyên tắc xuyên suốt:** Mọi tính năng phải giảm thời gian ra quyết định lâm sàng, không tăng thêm gánh nặng nhận thức cho bác sĩ.

---

## MỤC LỤC

1. [Biểu đồ xu hướng theo thời gian](#1-biểu-đồ-xu-hướng-theo-thời-gian)
2. [Trực quan hoá chỉ số định tính](#2-trực-quan-hoá-chỉ-số-định-tính)
3. [Bảng tóm tắt lâm sàng tự động](#3-bảng-tóm-tắt-lâm-sàng-tự-động)
4. [So sánh đa bệnh nhân](#4-so-sánh-đa-bệnh-nhân)
5. [Hệ thống cảnh báo thông minh](#5-hệ-thống-cảnh-báo-thông-minh)
6. [Dashboard quản lý khoa phòng](#6-dashboard-quản-lý-khoa-phòng)
7. [Tích hợp AI phân tích](#7-tích-hợp-ai-phân-tích)
8. [Xuất báo cáo PDF lâm sàng](#8-xuất-báo-cáo-pdf-lâm-sàng)
9. [Lộ trình Sprint](#9-lộ-trình-sprint)

---

## 1. Biểu đồ Xu hướng Theo thời gian

### 1.1 Biểu đồ đường (Line Chart) đa mốc thời gian

Đây là tính năng **quan trọng nhất** trong hệ thống EWS — sinh lý học là động học, giá trị tại một thời điểm không bằng xu hướng thay đổi.

**Giao diện mục tiêu:**

```
Hemoglobin (HGB)   [120 – 160 g/L]
                                              ref_max ─────────────── 160
  ┤                          ●               
  ┤              ●          /                ref_normal 
  ┤     ●───────            ↑ tăng          
  ┤────                     trend: ↗         ref_min ─────────────── 120
  ┼──────────────────────────
   T0           T1           T2
 13/03        28/03        13/04
```

**Đặc tả kỹ thuật:**

```python
# Thư viện khuyến nghị: Plotly (tương tác) hoặc Altair (khai báo)
import plotly.graph_objects as go

def render_trend_chart(obs_history: list[dict], test_name: str, ref_low, ref_high):
    """
    obs_history: [
        {"timestamp": "2026-03-13T08:00:00Z", "value": 132, "color": "green"},
        {"timestamp": "2026-03-28T09:30:00Z", "value": 121, "color": "yellow"},
        {"timestamp": "2026-04-13T08:58:00Z", "value": 136, "color": "green"},
    ]
    """
    fig = go.Figure()

    # Dải tham chiếu (Reference Band) — nền xanh nhạt
    if ref_low and ref_high:
        fig.add_hrect(
            y0=ref_low, y1=ref_high,
            fillcolor="rgba(34,197,94,0.08)",
            line_width=0,
            annotation_text="Bình thường",
            annotation_position="right",
        )
        # Đường tham chiếu min/max
        fig.add_hline(y=ref_low,  line_dash="dot", line_color="rgba(34,197,94,0.5)")
        fig.add_hline(y=ref_high, line_dash="dot", line_color="rgba(34,197,94,0.5)")

    # Đường xu hướng chính
    timestamps = [o["timestamp"] for o in obs_history]
    values     = [o["value"]     for o in obs_history]
    colors     = [o["color"]     for o in obs_history]

    # Map color_code → marker color
    MARKER_COLORS = {
        "green":  "#22c55e", "yellow": "#eab308",
        "orange": "#f97316", "red":    "#ef4444", "gray": "#94a3b8"
    }
    marker_colors = [MARKER_COLORS.get(c, "#94a3b8") for c in colors]

    fig.add_trace(go.Scatter(
        x=timestamps, y=values,
        mode="lines+markers",
        line=dict(color="#1e3a5f", width=2.5),
        marker=dict(size=12, color=marker_colors, line=dict(width=2, color="white")),
        hovertemplate="<b>%{y}</b><br>%{x}<extra></extra>",
        name=test_name,
    ))

    # Vùng nguy hiểm nếu có Critical threshold
    # (ví dụ: HGB < 70 = nguy hiểm → tô đỏ nền dưới 70)

    fig.update_layout(
        title=dict(text=test_name, font=dict(size=14, color="#1e3a5f")),
        height=220,
        margin=dict(l=40, r=60, t=40, b=30),
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(showgrid=False, tickformat="%d/%m"),
        yaxis=dict(gridcolor="rgba(0,0,0,0.06)"),
        showlegend=False,
    )
    return fig
```

**UX Flow:**
1. Bác sĩ click vào **ô giá trị** trên bảng heatmap → chart popup xuất hiện
2. Hoặc có nút `[📈 Xem xu hướng]` ở đầu mỗi nhóm xét nghiệm
3. Có thể chọn nhiều chỉ số cùng lúc để so sánh trên 1 chart (ví dụ: AST + ALT)

---

### 1.2 Mini Sparkline trong bảng heatmap

Thay vì chỉ hiện con số, mỗi ô có thêm một **sparkline nhỏ** ngay trong ô:

```
┌────────────────────────────────────────────┐
│ ALT         │ 49.87 ↑  │ /──/  │ 🟠 A      │
│             │  (cao)   │ trend │           │
└────────────────────────────────────────────┘
```

```python
# Dùng Plotly với height=40 để vẽ sparkline cực nhỏ
def render_sparkline(values: list[float], colors: list[str]) -> str:
    """Trả về base64 PNG nhúng vào HTML, hoặc dùng SVG inline."""
    # Cách đơn giản nhất: dùng Unicode block characters
    # ▁▂▃▄▅▆▇█  → ánh xạ giá trị sang chiều cao ký tự
    if len(values) < 2:
        return "—"
    blocks = "▁▂▃▄▅▆▇█"
    v_min, v_max = min(values), max(values)
    if v_max == v_min:
        return "─" * len(values)
    normalized = [(v - v_min) / (v_max - v_min) for v in values]
    return "".join(blocks[int(n * 7)] for n in normalized)
    # Kết quả ví dụ: "▃▄▅▇" → hiện trong ô nhỏ
```

---

## 2. Trực quan hoá Chỉ số Định tính

Đây là thách thức đặc thù của y học — nhiều chỉ số **không có đơn vị số**. Giải pháp thiết kế:

### 2.1 Nhóm phân loại & cách render

| Loại kết quả | Ví dụ | Chiến lược hiển thị |
|---|---|---|
| **Nhị phân** (Âm/Dương) | HIV, HBsAg, Nitrite | Icon ✅/❌ + badge màu |
| **Bán định lượng** (`< ngưỡng`) | Glucose niệu < 2.7, ERY < 5 | Thước đo ngang (gauge) |
| **Thứ bậc** (1+, 2+, 3+) | Protein niệu, Hb niệu | Thanh phân cấp màu sắc |
| **Định danh** | Nhóm máu AB, Rh(D)+ | Chip tag, không cảnh báo |
| **Khoảng mục tiêu** | pH 5–6 | Gauge với vùng xanh ở giữa |

---

### 2.2 Binary Indicator (Âm tính / Dương tính)

```
Thiết kế ô "Test nhanh":

  HIV Ab     ✅ ÂM TÍNH    ←  nền xanh nhạt, icon check lớn
  HBsAg      ✅ ÂM TÍNH    
  (Nếu Dương tính:)
  HIV Ab     ❌ DƯƠNG TÍNH  ←  nền đỏ, pulsing animation, chuông rung

HTML/CSS:
  .qualitative-negative {
    background: rgba(34,197,94,0.15);
    color: #15803d;
    border-radius: 8px;
    padding: 4px 12px;
    font-weight: 700;
  }
  .qualitative-positive {
    background: rgba(239,68,68,0.2);
    color: #991b1b;
    animation: pulse-red 1.5s infinite;
  }
```

---

### 2.3 Gauge / Thước đo cho `< ngưỡng`

Khi kết quả là **"Âm tính"** với tham chiếu **"< 2.7 mmol/L"**:

```
Glucose Niệu  [< 2.7 mmol/L]

  0 ──────────[●]──────────── 2.7 ──────── 5.4
              ↑ Âm tính                    
         (giá trị ước tính ~ 0)           
  [████████████████░░░░░░░░░░░░░░░░░░░░░░]
   Bình thường ←──────────────→ Vượt ngưỡng

Python (Plotly Indicator):
  fig = go.Figure(go.Indicator(
      mode="gauge+number",
      value=0,            # Âm tính → 0
      title={"text": "Glucose Niệu"},
      gauge={
          "axis": {"range": [0, ref_max * 2]},
          "bar":  {"color": "#22c55e"},
          "steps": [
              {"range": [0, ref_max],         "color": "rgba(34,197,94,0.1)"},
              {"range": [ref_max, ref_max*2],  "color": "rgba(239,68,68,0.1)"},
          ],
          "threshold": {
              "line": {"color": "#ef4444", "width": 3},
              "value": ref_max,
          },
      },
      number={"suffix": " mmol/L", "valueformat": ".1f"},
  ))
```

**Quy tắc chuyển đổi định tính → số:**

```python
QUALITATIVE_VALUE_MAP = {
    # Kết quả âm tính → giá trị số = 0 (hoặc ngưỡng * 0.1)
    "âm tính":    lambda ref_max, ref_min: 0.0,
    "negative":   lambda ref_max, ref_min: 0.0,
    # Nếu ngưỡng là "> ref_min" thì âm tính nghĩa là dưới min
    # → ước tính = ref_min * 0.5
    
    # Kết quả dương tính → giá trị ước tính = ngưỡng * 1.5 (rõ ràng vượt)
    "dương tính":  lambda ref_max, ref_min: ref_max * 1.5 if ref_max else 1.0,
    "positive":    lambda ref_max, ref_min: ref_max * 1.5 if ref_max else 1.0,
}
```

---

### 2.4 Thanh phân cấp (Graded Bar) cho kết quả thứ bậc

```
Protein niệu:  ─●──────────────────
                Âm   1+   2+   3+   4+
               [🟢] [🟡] [🟠] [🔴] [🔴]

Hb niệu:       ─────────●──────────
                Âm   Vết  1+   2+   3+
               [🟢] [🟡] [🟠] [🔴] [🔴]
```

```python
GRADED_SCALE = {
    "ÂM TÍNH": 0, "TRACE": 1, "VẾT": 1,
    "1+": 2, "2+": 3, "3+": 4, "4+": 5,
}

def render_graded_bar(value_str: str, scale: dict) -> str:
    level = scale.get(value_str.upper(), 0)
    colors = ["🟢", "🟡", "🟡", "🟠", "🔴", "🔴"]
    bar = "".join(
        f'<span style="opacity:{1.0 if i<=level else 0.2}">{colors[i]}</span>'
        for i in range(6)
    )
    return f'<div>{bar} <b>{value_str}</b></div>'
```

---

### 2.5 Polar Chart — Tổng quan định tính toàn bộ nước tiểu

Khi có đủ kết quả tổng phân tích nước tiểu, vẽ một **radar chart** nhỏ:

```
         Protein
            |
  Bilirubin─┼─Glucose
           /|\
     Ketone  Bạch cầu
            |
         Nitrite

  ● = Âm tính (bình thường)
  ■ = Dương tính (bất thường)
  Diện tích lấp đầy = mức độ bất thường
```

---

## 3. Bảng Tóm tắt Lâm sàng Tự động

### 3.1 Clinical Summary Panel

Một panel tóm tắt ở đầu trang, **viết bằng ngôn ngữ lâm sàng** thay vì con số:

```
╔══════════════════════════════════════════════════════╗
║  TÓM TẮT LÂM SÀNG — LÝ THỊ HỒNG HUỆ — 13/04/2026  ║
╠══════════════════════════════════════════════════════╣
║  🟢 HUYẾT HỌC: Công thức máu trong giới hạn bình    ║
║     thường. Không có dấu hiệu thiếu máu, nhiễm trùng║
║     hay rối loạn đông máu.                           ║
║                                                      ║
║  🟡 HOÁ SINH: Glucose máu 5.96 mmol/L — cao nhẹ     ║
║     so với ngưỡng 5.9. Theo dõi sau ăn.              ║
║     ALT 49.87 U/L — vượt 21% trên giới hạn trên.    ║
║     Chú ý chức năng gan.                             ║
║                                                      ║
║  🔴 NƯỚC TIỂU: Urobilinogen âm tính — cần loại trừ  ║
║     tắc mật. Bilirubin (+) trong nước tiểu. Ketone   ║
║     (+) có thể do nhịn ăn trước phẫu thuật.          ║
╚══════════════════════════════════════════════════════╝
```

**Kỹ thuật sinh tóm tắt:**

```python
def generate_clinical_summary(encounter: LabEncounter) -> str:
    """
    Sinh tóm tắt lâm sàng theo nhóm xét nghiệm.
    Dùng rule-based template cho v1.
    Sau nâng cấp: gọi LLM (Claude API) để sinh văn bản tự nhiên hơn.
    """
    summaries = []
    by_cat = encounter.get_by_category()

    # CBC rules
    if "CBC" in by_cat:
        cbc_abnormal = [o for o in by_cat["CBC"] if o.color_code != "green"]
        if not cbc_abnormal:
            summaries.append("🟢 **Huyết học:** Công thức máu trong giới hạn bình thường.")
        else:
            items = "; ".join(
                f"{o.test_name} {o.display_value()} {o.unit}" for o in cbc_abnormal
            )
            summaries.append(f"⚠️ **Huyết học:** Bất thường: {items}")

    # Chemistry rules
    if "CHEMISTRY" in by_cat:
        liver = [o for o in by_cat["CHEMISTRY"]
                 if o.test_code in ("AST", "ALT", "GGT") and o.color_code != "green"]
        if liver:
            summaries.append(
                f"🟡 **Chức năng gan:** "
                + ", ".join(f"{o.test_name} ↑{o.display_value()} U/L" for o in liver)
            )

    return "\n\n".join(summaries)
```

---

### 3.2 Risk Score Card (NEWS2 / qSOFA mini)

Tính điểm cảnh báo sớm đơn giản từ các thông số có sẵn:

```
EARLY WARNING INDICATORS
━━━━━━━━━━━━━━━━━━━━━━
  Glucose cao nhẹ    ⚡ +1 điểm
  ALT tăng           ⚡ +1 điểm  
  Bilirubin niệu (+) ⚡ +2 điểm
  Urobilinogen (-)   ⚡ +2 điểm
━━━━━━━━━━━━━━━━━━━━━━
  TỔNG: 6/10    [CẦN THEO DÕI]
```

---

## 4. So sánh Đa bệnh nhân

### 4.1 Ward Overview (Tổng quan khoa phòng)

Dashboard cấp khoa — bác sĩ trưởng khoa nhìn thấy tất cả bệnh nhân:

```
KHOA LIÊN KHOA RHM-TMH — 13/04/2026 14:00
┌─────────────────────────────────────────────────────────┐
│ BN          │ WBC │ HGB │ PLT │ Glucose │ ALT │ CẢNH BÁO│
├─────────────┼─────┼─────┼─────┼─────────┼─────┼─────────┤
│ Lý T. H. H. │ 🟢  │ 🟢  │ 🟢  │  🟡     │ 🟠  │ ⚠️ Gan  │
│ Nguyễn V. A.│ 🟢  │ 🔴  │ 🟡  │  🟢     │ 🟢  │ 🚨 HGB  │
│ Trần T. B.  │ 🟠  │ 🟢  │ 🟢  │  🟢     │ 🟢  │ ⚠️ BC   │
└─────────────────────────────────────────────────────────┘
```

**Kỹ thuật:**

```python
# Lưu trữ nhiều encounter trong st.session_state["ward_data"]
# Key: patient_id, Value: list of LabEncounter
ward_data: dict[str, list[LabEncounter]] = {}

# Render mini heatmap cell cho mỗi BN × chỉ số
def render_ward_cell(value: Optional[float], color: str) -> str:
    icons = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴", "gray": "⚪"}
    return icons.get(color, "⚪")
```

---

### 4.2 Multi-Series Trend (So sánh cùng chỉ số nhiều BN)

```
ALT theo thời gian — So sánh 3 bệnh nhân

  U/L
   80 ┤               ╱── Trần V.A. (đang tăng ⬆)
   60 ┤         ╱────╱
   41 ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  (ngưỡng trên)
   40 ┤────────╲──── Lý T.H.H. (ổn định)
   20 ┤              ╲─── Nguyễn B.C. (đang giảm ⬇)
      └──────────────────────────
       T0           T1           T2
```

---

## 5. Hệ thống Cảnh báo Thông minh

### 5.1 Delta Check — Cảnh báo Thay đổi Đột ngột

Khi một chỉ số thay đổi **> ngưỡng delta** trong thời gian ngắn, cảnh báo ngay dù vẫn trong giới hạn bình thường:

```python
DELTA_RULES = {
    # (test_code, max_change, time_window_hours)
    "HGB":       (20,  24),   # HGB giảm >20 g/L trong 24h → cảnh báo chảy máu
    "PLT":       (50,  48),   # PLT giảm >50 G/L → cảnh báo DIC
    "CREATININ": (44,  48),   # Creatinin tăng >44 µmol/L → AKI
    "WBC":       (4.0, 24),   # WBC tăng >4 G/L đột ngột → nhiễm trùng?
    "GLU":       (3.0, 6),    # Glucose thay đổi >3 mmol/L trong 6h → rối loạn đường huyết
}

def check_delta(current: Observation, previous: Observation,
                hours_between: float) -> Optional[str]:
    if current.test_code not in DELTA_RULES:
        return None
    max_delta, max_hours = DELTA_RULES[current.test_code]
    if hours_between > max_hours:
        return None
    if current.value_numeric and previous.value_numeric:
        delta = abs(current.value_numeric - previous.value_numeric)
        if delta >= max_delta:
            direction = "↑" if current.value_numeric > previous.value_numeric else "↓"
            return (f"⚡ DELTA CHECK: {current.test_name} thay đổi {direction}"
                    f" {delta:.1f} {current.unit} trong {hours_between:.0f}h")
    return None
```

---

### 5.2 Combination Rule (Cảnh báo tổ hợp)

Một chỉ số bất thường có thể bình thường. **Nhiều chỉ số bất thường cùng lúc** thì nguy hiểm:

```python
COMBINATION_RULES = [
    {
        "name": "Nghi ngờ Nhiễm khuẩn huyết",
        "conditions": [
            ("WBC",  lambda o: o.color_code in ("orange", "red")),
            ("NEU%", lambda o: o.value_numeric and o.value_numeric > 80),
        ],
        "alert_level": "red",
        "message": "WBC cao + NEU% > 80% → Nghi ngờ nhiễm khuẩn huyết. Kiểm tra cấy máu.",
    },
    {
        "name": "Nghi ngờ tổn thương gan cấp",
        "conditions": [
            ("AST", lambda o: o.color_code in ("orange", "red")),
            ("ALT", lambda o: o.color_code in ("orange", "red")),
        ],
        "alert_level": "orange",
        "message": "AST và ALT đều tăng → Nghi ngờ tổn thương tế bào gan.",
    },
    {
        "name": "Nghi ngờ tắc mật",
        "conditions": [
            # Urobilinogen âm tính (bình thường phải có)
            ("UROBILINOGEN", lambda o: o.color_code == "red"),
            ("BILIRUBIN",    lambda o: o.color_code in ("orange","red")),
        ],
        "alert_level": "red",
        "message": "Urobilinogen (-) + Bilirubin niệu (+) → Nghi ngờ tắc mật.",
    },
    {
        "name": "Rối loạn thận cấp (AKI screening)",
        "conditions": [
            ("CREATININ", lambda o: o.color_code in ("yellow","orange","red")),
            ("URE",       lambda o: o.color_code in ("orange","red")),
        ],
        "alert_level": "orange",
        "message": "Creatinin + Urê tăng đồng thời → Sàng lọc AKI.",
    },
]

def check_combination_rules(encounter: LabEncounter) -> list[dict]:
    """Kiểm tra tất cả combination rules, trả về list cảnh báo."""
    obs_map = {o.test_code: o for o in encounter.observations}
    fired = []
    for rule in COMBINATION_RULES:
        if all(
            code in obs_map and cond(obs_map[code])
            for code, cond in rule["conditions"]
        ):
            fired.append(rule)
    return fired
```

---

### 5.3 Trend Alert — Cảnh báo Xu hướng Tệ dần

```python
def check_deterioration_trend(obs_series: list[Observation]) -> Optional[str]:
    """
    Nếu chỉ số liên tục xấu dần trong 3 mốc liên tiếp → cảnh báo.
    Ví dụ: HGB T0=130 → T1=120 → T2=108 → xu hướng giảm liên tục
    """
    if len(obs_series) < 3:
        return None
    values = [o.value_numeric for o in obs_series[-3:] if o.value_numeric]
    if len(values) < 3:
        return None

    # Giảm liên tục
    if values[0] > values[1] > values[2]:
        total_drop_pct = (values[0] - values[2]) / values[0] * 100
        return f"📉 Xu hướng giảm liên tục 3 lần gần nhất ({total_drop_pct:.0f}% tổng)"

    # Tăng liên tục
    if values[0] < values[1] < values[2]:
        total_rise_pct = (values[2] - values[0]) / values[0] * 100
        return f"📈 Xu hướng tăng liên tục 3 lần gần nhất (+{total_rise_pct:.0f}% tổng)"

    return None
```

---

## 6. Dashboard Quản lý Khoa phòng

### 6.1 Lưu trữ lịch sử (Persistence Layer)

Hiện tại dữ liệu mất khi tắt app. Cần lưu trữ:

```python
# Lựa chọn 1: SQLite (đơn giản, local)
import sqlite3

CREATE TABLE encounters (
    id          TEXT PRIMARY KEY,
    patient_id  TEXT,
    patient_name TEXT,
    timestamp   TEXT,
    json_data   TEXT  -- FHIR JSON toàn bộ encounter
);

CREATE INDEX idx_patient ON encounters(patient_id);
CREATE INDEX idx_timestamp ON encounters(timestamp);

# Lựa chọn 2: JSON files theo thư mục (không cần DB)
data/
  patients/
    0063233/
      2026-04-13T08:58:00.json
      2026-03-28T09:00:00.json
      2026-03-01T10:30:00.json

# Lựa chọn 3 (production): PostgreSQL + SQLAlchemy
```

---

### 6.2 Search & Filter Bệnh nhân

```
[ 🔍 Tìm bệnh nhân...              ] [Lọc: Tất cả ▼] [Từ ngày: __/__] [Đến: __/__]

┌────────────────────────────────────────────────────┐
│ 🔴 NGUYỄN VĂN A   | BC# 0012345 | 13/04 | ALT ↑↑  │
│ 🟠 TRẦN THỊ B     | BC# 0067891 | 12/04 | HGB ↓    │
│ 🟡 LÝ THỊ H.H.    | BC# 0063233 | 13/04 | Gan ↑    │
│ 🟢 PHẠM VĂN C     | BC# 0054321 | 11/04 | Bình thường│
└────────────────────────────────────────────────────┘
```

---

## 7. Tích hợp AI Phân tích

### 7.1 Auto-Interpretation bằng Claude API

```python
# Gọi Claude để phân tích lâm sàng theo context bệnh nhân
import anthropic

def generate_ai_interpretation(encounter: LabEncounter, clinical_context: str) -> str:
    """
    clinical_context: "BN nữ 62 tuổi, phẫu thuật rút đinh xương gò má, 
                       gây mê nội khí quản, nhịn ăn 8h trước mổ"
    """
    client = anthropic.Anthropic()
    
    lab_summary = "\n".join(
        f"- {o.test_name}: {o.display_value()} {o.unit} "
        f"(tham chiếu: {o.reference_range.text}, phân loại: {o.interpretation_flag})"
        for o in encounter.observations
        if o.color_code != "green"
    )

    prompt = f"""Bạn là trợ lý AI hỗ trợ phân tích cận lâm sàng.

Bối cảnh lâm sàng: {clinical_context}

Kết quả xét nghiệm bất thường:
{lab_summary}

Hãy:
1. Giải thích ngắn gọn ý nghĩa lâm sàng của từng bất thường
2. Gợi ý liên quan đến bối cảnh lâm sàng
3. Những điểm cần theo dõi thêm

Lưu ý: Đây là hỗ trợ quyết định, không thay thế phán đoán bác sĩ."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
```

**UI cho AI Interpretation:**

```
┌─ 🤖 PHÂN TÍCH AI (Hỗ trợ quyết định) ──────────────────┐
│                                            [Thu gọn ▲]   │
│ Bối cảnh: [BN nhịn ăn trước mổ, gây mê...          ]    │
│                                      [Phân tích ngay]    │
│                                                          │
│ • Ketone (+) trong nước tiểu nhất quán với tình trạng    │
│   nhịn ăn trước phẫu thuật — dự kiến sẽ bình thường     │
│   hóa sau khi bệnh nhân ăn lại.                         │
│                                                          │
│ • ALT tăng 21% — nhẹ, có thể do gây mê. Nên kiểm tra   │
│   lại sau 48-72h.                                        │
│                                                          │
│ • Urobilinogen (-) + Bilirubin niệu (+): Cần loại trừ   │
│   tắc mật, đặc biệt nếu BN có vàng da.                  │
│                                                          │
│ ⚠️ Đây là phân tích hỗ trợ. Quyết định lâm sàng        │
│    thuộc thẩm quyền bác sĩ điều trị.                    │
└──────────────────────────────────────────────────────────┘
```

---

### 7.2 Anomaly Detection bằng ML

```python
# Phát hiện bất thường so với population (cùng loại BN)
# Kỹ thuật: Isolation Forest hoặc Z-score so với dữ liệu lịch sử

from sklearn.ensemble import IsolationForest
import numpy as np

def detect_anomaly_vs_population(
    current_values: dict,      # {"WBC": 8.55, "HGB": 136, ...}
    historical_data: list[dict], # Dữ liệu BN cùng chẩn đoán
) -> dict:
    """
    Trả về dict: {test_code: anomaly_score}
    Score > 0.7 → bất thường so với quần thể
    """
    # ... implementation
```

---

## 8. Xuất Báo cáo PDF Lâm sàng

### 8.1 Report Template

```python
# Dùng reportlab hoặc WeasyPrint để tạo PDF
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table

def export_clinical_report(encounter: LabEncounter, include_charts: bool = True) -> bytes:
    """
    Tạo file PDF báo cáo lâm sàng:
    - Trang 1: Thông tin BN + Tóm tắt + Biểu đồ radar
    - Trang 2: Bảng kết quả đầy đủ có màu sắc
    - Trang 3 (tuỳ chọn): Trend charts cho chỉ số bất thường
    """
```

**Header template:**

```
BỆNH VIỆN TRUNG ƯƠNG HUẾ — CƠ SỞ 2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BÁO CÁO KẾT QUẢ XÉT NGHIỆM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BN: LÝ THỊ HỒNG HUỆ  |  07/05/1964  |  Nữ
BC#: 0063233  |  SID: 2604131206
Lấy mẫu: 08:58 ngày 13/04/2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ CẢNH BÁO: 7 chỉ số bất thường (1 NGUY HIỂM)
```

---

## 9. Lộ trình Sprint

### Sprint 1 — Hoàn thiện core (2 tuần)
- [ ] Biểu đồ đường Plotly cho từng chỉ số số (click-to-expand)
- [ ] Gauge chart cho chỉ số `< ngưỡng`
- [ ] Binary indicator (`✅ / ❌`) cho xét nghiệm định tính
- [ ] SQLite persistence — lưu lịch sử giữa các session

### Sprint 2 — Cảnh báo thông minh (2 tuần)
- [ ] Combination Rules Engine (5 rule đầu tiên)
- [ ] Delta Check cho CBC và sinh hoá
- [ ] Trend alert (3 lần liên tiếp xấu dần)
- [ ] Clinical Summary panel (rule-based)

### Sprint 3 — Multi-patient & Ward view (3 tuần)
- [ ] Ward Overview dashboard
- [ ] Patient search & filter
- [ ] Multi-series trend comparison
- [ ] Export PDF báo cáo

### Sprint 4 — AI & Integration (3 tuần)
- [ ] Claude API integration cho auto-interpretation
- [ ] HL7 FHIR API endpoint (nhận kết quả từ HIS)
- [ ] Giao diện mobile-responsive (PWA)
- [ ] Role-based access (bác sĩ / điều dưỡng / quản trị)

---

## Phụ lục: Bảng Quy đổi Định tính → Định lượng

| Kết quả PDF | Giá trị số quy đổi | Mục đích |
|---|---|---|
| `Âm tính` / `Negative` | `0.0` | Gauge từ 0 → ngưỡng |
| `Dương tính` / `Positive` | `ngưỡng × 1.5` | Rõ ràng vượt ngưỡng |
| `< 2.7` → kết quả `Âm tính` | `0.0` (với max=2.7) | Gauge 0–2.7–5.4 |
| `1+` | `ngưỡng × 1.2` | Vượt nhẹ |
| `2+` | `ngưỡng × 1.6` | Vượt vừa |
| `3+` | `ngưỡng × 2.0` | Vượt nhiều |
| `Rh(D) Dương` | Không số hoá | Hiển thị tag |
| `AB` | Không số hoá | Hiển thị tag |
| `5 - 6` (pH) | `5.5` (midpoint) | Gauge với vùng xanh giữa |

> **Lưu ý thiết kế:** Việc quy đổi này chỉ phục vụ **hiển thị gauge/chart**.  
> Dữ liệu gốc (`value_string`) luôn được bảo toàn trong database  
> và không bao giờ bị ghi đè bởi giá trị quy đổi.

---

*Tài liệu này thuộc dự án HIDU EWS — BVTW Huế Cơ sở 2*  
*Cập nhật lần cuối: 14/04/2026*
