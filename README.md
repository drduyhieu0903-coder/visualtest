# HIDU EWS — Clinical Early Warning System
## Hệ thống Trực quan hoá & Cảnh báo Sớm Kết quả Cận lâm sàng

> **Bệnh viện Trung ương Huế - Cơ sở 2**  
> Dự án HIDU EWS — Module Cận lâm sàng & Tích hợp Lịch sử Khám

---

## 📖 Giới thiệu chung

**HIDU EWS** (Clinical Early Warning System) là hệ thống bảng điều khiển (dashboard) lâm sàng được phát triển chuyên biệt giúp chuyển đổi kết quả xét nghiệm, cận lâm sàng tĩnh (từ các file PDF của máy xét nghiệm) thành một nền tảng dữ liệu động trực quan. 

Hệ thống cung cấp một cái nhìn tổng thể, phân màu đánh giá mức độ rủi ro, cảnh báo thông minh, theo dõi xu hướng, và lưu trữ lịch sử khám bệnh của từng bệnh nhân nhằm mục đích giảm thiểu sai sót y khoa và nâng cao chất lượng quyết định lâm sàng.

---

## ✨ Tính năng Nổi bật

### 1. Phân tích & Trích xuất Dữ liệu Thông minh
- Tự động đọc và trích xuất dữ liệu từ các tệp PDF xuất ra trực tiếp từ hệ thống LIS hoặc các máy xét nghiệm cục bộ (VD: XN1000, Cobas Pro, CombiScan500).
- **KHÔNG hardcode** khoảng tham chiếu: Hệ thống linh hoạt tự động lấy khoảng tham chiếu ngay trên từng kết quả trả về của máy tính nhằm đảm bảo chính xác theo loại hóa chất bệnh viện đang sử dụng.

### 2. Thuật toán Phân màu & Đánh giá Rủi ro (Rule Engine)
Phân tách dữ liệu thành 5 cấp độ bệnh lý dễ dàng nhận diện bằng màu sắc:
- 🟢 **Xanh (Bình thường):** Số liệu nằm trong khoảng tham chiếu.
- 🟡 **Vàng (Chú ý / Nhẹ):** Số liệu chênh lệch/lệch ≤ 20% so với giới hạn tiêu chuẩn.
- 🟠 **Cam (Bất thường):** Tình trạng lệch từ 20% – 50%.
- 🔴 **Đỏ (Nguy hiểm / Báo động):** Lệch rất cao (> 50%) - Đi kèm với UI nhấp nháy thu hút sự chú ý.
- ⚪ **Xám (Không ưu tiên):** Kết quả không có thông số tham chiếu.

### 3. Hệ thống Cảnh báo Thông minh (Smart Alerts & AI Insights)
- **Cảnh báo Biến động (Delta Checks):** Phát hiện sự thay đổi vượt mức quy định trong một khoảng thời gian ngắn (Ví dụ: Chỉ số Creatinin tăng rất nhanh để cảnh báo nguy cơ AKI).
- **Quy tắc Kết hợp (Combination Rules):** Cảnh báo tổng hợp khi có nhiều chỉ số suy giảm cùng lúc (Ví dụ: AST, ALT đồng loạt tăng kèm Urobilinogen cảnh báo nghi ngờ tổn thương gan).
- **Đánh giá Thể trạng Sinh hiệu:** Phát hiện sốc thông qua các chỉ số sinh hiệu (Huyết áp, Nhịp tim, Thân nhiệt, Hô hấp). Phân loại chỉ số qua Risk Gauge cảnh báo sớm chỉ số điểm.

### 4. Quản lý Hồ sơ Lâm sàng Dài hạn
- Cấu trúc cây thời gian thực theo từng mốc khám (Timeline T0, T1, T2).
- Cung cấp tính năng tìm kiếm lịch sử các ca khám (Database SQLite có khả năng lưu trữ cố định vào thư mục gốc).
- Tổ chức quản lý theo chỉ định và máy xét nghiệm. 

### 5. Biểu đồ Xu hướng Động & Giao diện Responsive
- Có khả năng tương thích toàn diện (Mobile, Tablet, Desktop) đáp ứng tính cấp bách ở khoa cấp cứu.
- Hỗ trợ xem các biến động chỉ số thông qua Trend Charts, Sparkline trực quan thay thế cho những biểu đồ số truyền thống. Định tính kết quả nhị phân hoặc chuỗi thứ bậc ra một định dạng trực quan.

---

## 📂 Kiến trúc Module

```text
hidu_ews/
├── app.py                    # Luồng ứng dụng chính, Dashboard Streamlit (Giao diện hiển thị)
├── modules/                  # Hệ sinh thái phân tích Backend
│   ├── data_models.py        # Định nghĩa các Model chuẩn hoá dữ liệu (FHIR-inspired)
│   ├── db.py                 # Interface và Logic quản lý CSDL (SQLite)
│   ├── rule_engine.py        # Logic phân màu dữ liệu lâm sàng
│   ├── pdf_parser.py         # Trình Engine bóc tách Table dữ liệu PDF 
│   ├── smart_alerts.py       # Engine phân tích Delta, Combination Rule
│   ├── clinical_summary.py   # Tính toán Điểm Rủi ro lâm sàng & Trình Tóm tắt văn bản
│   ├── qualitative_render.py # Logic hiển thị với dữ liệu xét nghiệm định tính / Binary
│   └── trend_chart.py        # Trình kết xuất biểu đồ chỉ số tương tác Plotly
├── data/                     # Thư mục File CSDL SQLite & Data mẫu
├── requirements.txt          # Các Thư viện phụ thuộc Python
├── README.md                 # Chỉ dẫn kĩ thuật chung
└── FEATURE_ROADMAP.md        # Lộ trình phát triển phần mềm trong tương lai
```

---

## ⚙️ Hướng dẫn Cài đặt & Khởi chạy

### Môi trường Yêu cầu
- Máy tính có hỗ trợ cài đặt **Python 3.9+**.
- Công cụ cài đặt gói `pip`.

### Thiết lập Nhanh

**1. Khôi phục Thư viện**
Tại thư mục gốc, tiến hành cài đặt toàn bộ thành phần phụ thuộc của nền tảng:
```bash
pip install -r requirements.txt
```

**2. Khởi động Giao diện Điều khiển**
Khởi tạo Web-app thông qua framework Streamlit:
```bash
streamlit run app.py
```
*(Nếu máy cung cấp sẵn quy trình khởi tạo tệp lệnh `.bat`, hãy thực thi file `start.bat`)*

**3. Trải nghiệm Chương trình**
- URL truy cập Dashboard mặc định: **http://localhost:8501**
- Tải lên một tệp `.pdf` đại diện cho các mẫu kết quả cận lâm sàng của bệnh nhân để tiến trình số hoá và phân tích được bắt đầu.

---

## 🔄 Phác đồ Xử lý Dữ liệu

```text
  [PDF Dữ liệu từ LIS]
           │
           ▼
 [modules/pdf_parser.py]      ➔ Bóc tách Table định dạng, Dữ liệu bệnh nhân & Metadata
           │
           ▼
 [modules/rule_engine.py]     ➔ Đánh giá độ sai lệch, Phân tách màu và thuật toán đánh giá bệnh lý
           │
           ▼
 [modules/smart_alerts.py]    ➔ Nối ghép với T/Lịch sử để đánh giá các rủi ro thay đổi lâm sàng (Delta/Combination)
           │
           ▼
 [modules/data_models.py]     ➔ Chuẩn hóa định dạng và tạo khối Encounter (Bản ghi khám)
           │
           ▼
    [Streamlit app.py]        ➔ Màn hiển thị (Heatmap, Tóm lược thông số lâm sàng, Đồ thị Tương tác Plotly)
```

---

## 🚀 Sprint & Lộ trình Tiếp theo (Roadmap)

Hệ thống đang tích cực phát triển lên các tính năng cao cấp tại `FEATURE_ROADMAP.md`:
- Mở rộng chức năng điều khiển toàn vùng (Ward overview) thay vì chỉ phân loại cá nhân từng bệnh nhân.
- Nâng cấp **Tích hợp Trí Tuệ Nhân Tạo (AI)**: Sử dụng các mô hình ngôn ngữ lớn (LLM - Claude API) để Auto-Interpretation các ghi chú y tế.
- Tương thích giao thức mở HL7 FHIR để thực hiện liên kết hai chiều trực tiếp với Hệ thống Thông tin Y tế Bệnh viện (HIS).
- Hỗ trợ xuất dữ liệu báo cáo PDF.

---

> ⚠️ **Tuyên bố Miễn trừ Trách nhiệm**  
> Ứng dụng này cung cấp chức năng quản lý, trình diễn thông tin trực quan để **hỗ trợ cảnh báo và quyết định y tế**. Đây là công cụ hệ thống thuộc trạng thái thử nghiệm — Toàn bộ kết quả hiển thị **không nhằm thay thế cho chẩn đoán cuối cùng** hoặc y lệnh độc lập tới từ các Bác sĩ có chuyên môn lâm sàng. Niềm tin vào các chỉ số kỹ thuật và cảnh báo tự động yêu cầu cần có phân tách và chẩn đoán kĩ càng.
