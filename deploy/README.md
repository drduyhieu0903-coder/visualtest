# HIDU EWS — Clinical Early Warning System
## Hệ thống Trực quan hoá & Cảnh báo Sớm Kết quả Cận lâm sàng

> **Bệnh viện Trung ương Huế - Cơ sở 2**  
> Dự án HIDU EWS — Module Cận lâm sàng

---

## Kiến trúc Module

```
hidu_ews/
├── app.py                    # Streamlit Dashboard (UI chính)
├── modules/
│   ├── data_models.py        # FHIR-inspired data structures
│   ├── rule_engine.py        # Clinical color-coding algorithm
│   └── pdf_parser.py         # PDF extraction engine
├── requirements.txt
└── README.md
```

## Cài đặt & Chạy

```bash
# 1. Cài thư viện
pip install -r requirements.txt

# 2. Chạy app
streamlit run app.py
```

Mở trình duyệt tại: **http://localhost:8501**

---

## Luồng dữ liệu

```
PDF file
  └─► pdf_parser.py      → Trích xuất bảng + thông tin bệnh nhân
        └─► rule_engine.py  → Áp dụng thuật toán phân màu
              └─► data_models.py  → Cấu trúc JSON chuẩn FHIR
                    └─► app.py       → Render Heatmap Dashboard
```

## Thuật toán Phân màu (Rule Engine)

| Màu    | Cờ | Ý nghĩa              | Điều kiện             |
|--------|-----|---------------------|-----------------------|
| 🟢 Xanh | N  | Bình thường         | Trong khoảng tham chiếu |
| 🟡 Vàng | H/L | Chú ý (nhẹ)        | Lệch ≤ 20%             |
| 🟠 Cam  | A  | Bất thường          | Lệch 20–50%            |
| 🔴 Đỏ   | C  | Nguy hiểm           | Lệch > 50%             |
| ⚪ Xám  | N  | Không có tham chiếu | —                      |

**Ngưỡng 20% và 50% có thể điều chỉnh theo quyết định của bác sĩ lâm sàng.**

## Lưu ý Triển khai

- **KHÔNG hardcode** khoảng tham chiếu — luôn lấy từ file PDF
- Mỗi máy xét nghiệm (XN1000, Cobas Pro, CombiScan500) có khoảng tham chiếu riêng
- Hỗ trợ đa mốc thời gian (khi có ≥2 lần XN sẽ hiện mũi tên xu hướng)
- Export JSON định dạng FHIR-inspired để tích hợp HIS

## Đường phát triển (Agile)

- [x] **Tuần 1:** PDF parser + Rule engine → JSON chuẩn
- [x] **Tuần 2:** Streamlit dashboard với heatmap có màu sắc
- [ ] **Tuần 3:** Multi-timepoint timeline (T0, T1, T2)
- [ ] **Tuần 4:** Tích hợp HIS — push/pull qua API
- [ ] **Tuần 5:** Mobile-responsive PWA

---

*⚠️ Phiên bản thử nghiệm — Kết quả chỉ mang tính tham khảo*
