"""
HIDU EWS - PDF Parser
Extracts structured lab data from BVTW Hue (and compatible) PDF reports.
Uses pdfplumber for table extraction with text fallback.

Design principles:
  - Reference ranges are ALWAYS extracted from PDF, never hardcoded
  - Timestamps are preserved with full precision
  - Category grouping mirrors physical lab sections
"""

import re
import io
from typing import List, Optional, Dict, Tuple
from datetime import datetime

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from modules.data_models import ReferenceRange, Observation, LabEncounter
from modules.rule_engine import sanitize_value, parse_reference_range, process_encounter


# ─── Category Mapping ─────────────────────────────────────────────────────────

SECTION_TO_CATEGORY = {
    # Vietnamese section headers → category code
    "huyết học tế bào": "CBC",
    "tổng phân tích tế bào máu": "CBC",
    "đông máu": "COAG",
    "truyền máu": "BLOOD_TYPE",
    "nhóm máu": "BLOOD_TYPE",
    "test nhanh": "RAPID",
    "hóa sinh máu": "CHEMISTRY",
    "hoa sinh mau": "CHEMISTRY",
    "sinh hoá nước tiểu": "URINALYSIS",
    "sinh hoa nuoc tieu": "URINALYSIS",
    "nước tiểu": "URINALYSIS",
    "tổng phân tích nước tiểu": "URINALYSIS",
}


def _detect_category(text: str, current_category: str) -> str:
    """Detect lab category from section header text."""
    lower = text.lower().strip()
    for key, cat in SECTION_TO_CATEGORY.items():
        if key in lower:
            return cat
    return current_category


# ─── Patient Info Extraction ──────────────────────────────────────────────────

def _extract_patient_info(full_text: str) -> Dict:
    """Extract patient demographics from PDF text."""
    info = {
        "patient_id": "",
        "patient_name": "",
        "gender": "",
        "dob": "",
        "encounter_id": "",
        "clinical_timestamp": "",
        "ordering_physician": "",
        "lab_technician": "",
    }

    # Patient name (Vietnamese: "Họ và tên:" or "Họ tên:")
    name_match = re.search(
        r'Họ(?:\s+và)?\s+tên\s*:\s*([^\n\t]+?)(?:\s+Năm|\s+Ngày|\s+Giới|\t|$)',
        full_text, re.IGNORECASE
    )
    if name_match:
        name_raw = name_match.group(1).strip()
        # Remove any trailing metadata that snuck in
        name_raw = re.sub(r'\s+(Năm|Ngày|Giới|Địa|Khoa).*', '', name_raw, flags=re.IGNORECASE)
        info["patient_name"] = name_raw

    # DOB
    dob_match = re.search(
        r'Ngày\s+sinh\s*:\s*(\d{2}/\d{2}/\d{4})'
        r'|Năm\s+sinh\s*:\s*(\d{2}/\d{2}/\d{4})',
        full_text, re.IGNORECASE
    )
    if dob_match:
        info["dob"] = dob_match.group(1) or dob_match.group(2) or ""

    # Gender
    if re.search(r'Giới\s+tính\s*:\s*Nữ|Giới\s*:\s*Nữ', full_text, re.IGNORECASE):
        info["gender"] = "Female"
    elif re.search(r'Giới\s+tính\s*:\s*Nam|Giới\s*:\s*Nam', full_text, re.IGNORECASE):
        info["gender"] = "Male"

    # Patient ID (Số bệnh nhân, or standalone patient number like "0063233")
    id_match = re.search(r'Số\s+bệnh\s+nhân\s*:\s*(\d+)', full_text, re.IGNORECASE)
    if id_match:
        info["patient_id"] = id_match.group(1)
    else:
        # Try 7-digit standalone barcode number (appears at top of BVTW Hue pages)
        barcode_match = re.search(r'(?:^|\n)\s*(00\d{5})\s*(?:\n|$)', full_text, re.MULTILINE)
        if barcode_match:
            info["patient_id"] = barcode_match.group(1)

    # SID (Sample ID)
    sid_match = re.search(r'SID\s*:\s*(\w+)', full_text, re.IGNORECASE)
    if sid_match:
        info["encounter_id"] = "SID_" + sid_match.group(1)

    # Sample collection time (Giờ lấy mẫu)
    time_match = re.search(
        r'Giờ\s+lấy\s+mẫu\s*:\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})',
        full_text, re.IGNORECASE
    )
    if time_match:
        date_str = time_match.group(1)
        time_str = time_match.group(2)
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
            info["clinical_timestamp"] = dt.isoformat() + "Z"
        except ValueError:
            info["clinical_timestamp"] = f"{date_str}T{time_str}:00Z"

    # Ordering physician
    doc_match = re.search(
        r'Bác\s+sĩ\s+chỉ\s+định\s*:\s*([^\n]+)',
        full_text, re.IGNORECASE
    )
    if doc_match:
        info["ordering_physician"] = doc_match.group(1).strip()

    return info


# ─── Table Row Parser ─────────────────────────────────────────────────────────

def _parse_table_row(row: List, category: str) -> Optional[Observation]:
    """
    Parse a single table row from pdfplumber extract_tables().

    BVTW Hue PDF format (6 columns):
      col[0] = test name (may have "1. " prefix or subsection heading)
      col[1] = None / empty (always empty in this PDF format)
      col[2] = result value
      col[3] = reference range
      col[4] = unit
      col[5] = machine name

    Also handles 5-col format (Name | Result | Ref | Unit | Machine).
    """
    if not row or not any(row):
        return None

    # Clean None values
    row = [str(c).strip() if c is not None else "" for c in row]

    # Detect layout by checking if col[1] is always empty (BVTW Hue format)
    if len(row) >= 6 and not row[1]:
        # BVTW Hue 6-col format: Name | (empty) | Result | Ref | Unit | Machine
        test_name = row[0]
        result_raw = row[2]
        ref_raw = row[3]
        unit = row[4]
        machine = row[5]
    elif len(row) >= 6:
        # Generic 6-col: # | Name | Result | Ref | Unit | Machine
        test_name = row[1]
        result_raw = row[2]
        ref_raw = row[3]
        unit = row[4]
        machine = row[5]
    elif len(row) >= 5:
        test_name = row[0]
        result_raw = row[1]
        ref_raw = row[2]
        unit = row[3]
        machine = row[4]
    elif len(row) >= 3:
        test_name = row[0]
        result_raw = row[1]
        ref_raw = row[2]
        unit = row[3] if len(row) > 3 else ""
        machine = ""
    else:
        return None

    # Skip header rows or empty
    if not test_name or test_name in ["#", "TÊN XÉT NGHIỆM", "TEN XET NGHIEM"]:
        return None
    if not result_raw or result_raw in ["KẾT QUẢ", "KET QUA", "KẾTQUẢ"]:
        return None

    # Skip section header rows (long names with no result)
    if len(test_name) > 60 and not result_raw:
        return None

    # Strip leading number prefix "1. ", "2. " etc.
    test_name = re.sub(r'^\d+\.\s*', '', test_name).strip()

    # Fix garbled machine names from PDF (e.g. "C o mbiScan500")
    machine = re.sub(r'\s+', '', machine)  # Remove spurious spaces in machine names

    # Generate a test code from test name
    test_code = _generate_test_code(test_name)

    # Sanitize value
    value_numeric, value_string = sanitize_value(result_raw)

    # Parse reference range
    ref = parse_reference_range(ref_raw)

    # Create observation with temporary color (will be assigned by rule engine)
    obs = Observation(
        test_code=test_code,
        test_name=test_name,
        value_numeric=value_numeric,
        value_string=value_string,
        unit=unit.replace("µ", "μ"),  # Normalize micro symbol
        reference_range=ref,
        interpretation_flag="N",
        color_code="gray",
        category=category,
        machine=machine if machine else None,
    )
    return obs


def _generate_test_code(name: str) -> str:
    """Generate a short code from test name for identification."""
    # Remove common Vietnamese words
    code = name.upper()
    code = re.sub(r'\[.*?\]', '', code)  # Remove brackets like [Máu]
    code = re.sub(r'\(.*?\)', '', code)  # Remove parentheses
    code = code.strip()
    # Keep first word(s) up to 15 chars
    words = code.split()
    if words:
        return "_".join(words[:2])[:20]
    return code[:15]


# ─── Text-Based Fallback Parser ───────────────────────────────────────────────

# Pattern for: "TestName  8.55  4 - 10  G/L  XN1000"
TEXT_ROW_PATTERN = re.compile(
    r'^([A-Za-zÀ-ỹ%#\s\(\)\[\]\/\.]+?)\s+'  # Test name
    r'([\d,\.]+|[A-Za-zÀ-ỹ\s\(\)]+?)\s+'    # Result value
    r'([\d\s\-<>≤≥\.,]+|ÂM TÍNH|AM TINH|NEGATIVE|DƯƠNG TÍNH)\s+'  # Ref range
    r'([A-Za-zÀ-ỹ\/μµ%²³]+)?\s*'            # Unit
    r'([A-Za-z0-9\s]+)?$',                   # Machine
    re.UNICODE
)


def _parse_text_fallback(page_text: str, category: str) -> List[Observation]:
    """
    Fallback parser using regex on raw text when table extraction fails.
    """
    observations = []
    lines = page_text.split('\n')

    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        # Skip obvious non-data lines
        if any(skip in line for skip in [
            "BỆNH VIỆN", "KHOA", "Họ và tên", "Địa chỉ", "Giờ",
            "Bác sĩ", "Người", "Duyệt", "Trang:", "PHIẾU", "ĐT:"
        ]):
            continue

        # Try to parse line with space-separated format
        parts = re.split(r'\s{2,}', line)  # Split on 2+ spaces
        if len(parts) >= 3:
            # Create a fake row and try to parse
            obs = _parse_table_row(parts, category)
            if obs and (obs.value_numeric is not None or obs.value_string):
                observations.append(obs)

    return observations


# ─── Per-Page Info Extraction ─────────────────────────────────────────────────

def _extract_page_sid(page_text: str) -> Optional[str]:
    """Extract SID from a single page's text."""
    sid_match = re.search(r'SID\s*:\s*(\w+)', page_text, re.IGNORECASE)
    return sid_match.group(1) if sid_match else None


def _extract_page_timestamp(page_text: str) -> Optional[str]:
    """Extract sample collection timestamp from a single page's text."""
    time_match = re.search(
        r'Giờ\s+lấy\s+mẫu\s*:\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})',
        page_text, re.IGNORECASE
    )
    if time_match:
        date_str = time_match.group(1)
        time_str = time_match.group(2)
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
            return dt.isoformat() + "Z"
        except ValueError:
            return f"{date_str}T{time_str}:00Z"
    return None


def _categorize_page(page_text: str) -> str:
    """Return 'LAB', 'IMAGING', or 'UNKNOWN'."""
    text_upper = page_text.upper()
    lab_keywords = ["KẾT QUẢ XÉT NGHIỆM", "XÉT NGHIỆM", "HUYẾT HỌC",
                    "HÓA SINH", "SINH HOÁ", "NƯỚC TIỂU", "TEST NHANH",
                    "ĐÔNG MÁU", "TRUYỀN MÁU"]
    imaging_keywords = ["SIÊU ÂM", "X QUANG", "CT SCAN", "MRI", "CHẨN ĐOÁN HÌNH ẢNH",
                        "NỘI SOI", "ĐIỆN TIM"]

    has_lab = any(kw in text_upper for kw in lab_keywords)
    has_imaging = any(kw in text_upper for kw in imaging_keywords)

    if has_imaging and not "XÉT NGHIỆM" in text_upper:
        return "IMAGING"
    
    if has_lab or "SID" in text_upper:
        return "LAB"

    return "UNKNOWN"


def _extract_imaging_report(page_text: str) -> Optional[dict]:
    """Extract imaging type and conclusion if present."""
    text_upper = page_text.upper()
    
    report_type = "Chẩn đoán hình ảnh"
    first_lines = page_text.split('\n')[:15]
    for line in first_lines:
        line_u = line.upper()
        if any(kw in line_u for kw in ["SIÊU ÂM", "X QUANG", "CT SCAN", "MRI", "NỘI SOI", "ĐIỆN TIM"]):
            # Get the exact title line, cleaning up '-'
            report_type = line.strip(" -")
            break
            
    conclusion = ""
    # Try finding "KẾT LUẬN" and capturing the rest
    match = re.search(r'KẾT\s+LUẬN[\s:-]*(.*)', page_text, re.IGNORECASE | re.DOTALL)
    if match:
        conclusion_text = match.group(1).strip()
        # Clean up physician signature blocks and extra date/location text
        for split_term in ["BÁC SĨ", "Bác sĩ", "Người thực hiện", "Lời dặn của BS", "Lời dặn:", "Huế,", "Huế,"]:
            conclusion_text = conclusion_text.split(split_term)[0]
        
        # Also cut off if "Ngày" is followed by a number (e.g. Ngày 14)
        conclusion_text = re.split(r'\bNgày\s+\d{1,2}\b', conclusion_text, flags=re.IGNORECASE)[0]
        
        conclusion = conclusion_text.strip(".,;: \n\r")
    if conclusion:
        return {
            "type": report_type,
            "conclusion": conclusion
        }
    return None


# ─── Main PDF Parser (Multi-Encounter) ───────────────────────────────────────

def parse_lab_pdf_multi(pdf_file) -> List[LabEncounter]:
    """
    Parse a lab PDF that may contain multiple sampling events (SIDs).
    Each SID becomes a separate LabEncounter.

    Args:
        pdf_file: File-like object or path string

    Returns:
        List of LabEncounter objects, sorted by timestamp (oldest first)
    """
    if pdfplumber is None:
        raise ImportError("pdfplumber is required. Run: pip install pdfplumber")

    if isinstance(pdf_file, (str, bytes)):
        pdf_stream = io.BytesIO(pdf_file) if isinstance(pdf_file, bytes) else open(pdf_file, 'rb')
    else:
        pdf_stream = pdf_file

    # ── Phase 1: Extract per-page data ──
    # Each page gets: (page_text, sid, timestamp, observations, category)
    page_data = []

    try:
        with pdfplumber.open(pdf_stream) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""

                page_cat = _categorize_page(page_text)

                if page_cat != "LAB":
                    # It might be an imaging page, try to extract report
                    img_report = _extract_imaging_report(page_text)
                    if img_report:
                        # Append to page_data with an IMAGING marker
                        page_data.append({
                            "type": "IMAGING",
                            "text": page_text,
                            "report": img_report
                        })
                    continue

                # Extract SID and timestamp for this page
                page_sid = _extract_page_sid(page_text)
                page_ts = _extract_page_timestamp(page_text)

                # Detect category from page text
                current_category = "OTHER"
                for line in page_text.split('\n'):
                    new_cat = _detect_category(line, current_category)
                    if new_cat != current_category:
                        current_category = new_cat

                # Extract observations from tables
                observations = []
                tables = page.extract_tables()
                found_via_table = False

                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        if not row:
                            continue
                        row_text = " ".join(str(c) for c in row if c).lower()
                        new_cat = _detect_category(row_text, current_category)
                        if new_cat != current_category:
                            current_category = new_cat
                            continue
                        obs = _parse_table_row(row, current_category)
                        if obs and (obs.value_numeric is not None or obs.value_string):
                            observations.append(obs)
                            found_via_table = True

                # Text fallback
                if not found_via_table and page_text:
                    fallback_obs = _parse_text_fallback(page_text, current_category)
                    observations.extend(fallback_obs)

                if observations:
                    page_data.append({
                        "type": "LAB",
                        "text": page_text,
                        "sid": page_sid,
                        "timestamp": page_ts,
                        "observations": observations,
                    })

    except Exception as e:
        raise ValueError(f"Lỗi đọc PDF: {str(e)}")

    if not page_data:
        return []

    # ── Phase 2: Group pages by (SID, Timestamp) and separate Imaging ──
    sid_groups: Dict[Tuple[str, str], list] = {}
    imaging_reports = []
    text_for_patient_info = []

    for pd_item in page_data:
        text_for_patient_info.append(pd_item["text"])
        if pd_item["type"] == "IMAGING":
            imaging_reports.append(pd_item["report"])
        elif pd_item["type"] == "LAB":
            sid = pd_item["sid"] or "UNKNOWN"
            ts = pd_item.get("timestamp") or ""
            group_key = (sid, ts)
            if group_key not in sid_groups:
                sid_groups[group_key] = []
            sid_groups[group_key].append(pd_item)

    # ── Phase 3: Build one encounter per SID ──
    # Extract patient info from all page texts combined
    all_text = "\n".join(text_for_patient_info)
    patient_info = _extract_patient_info(all_text)

    encounters = []
    for group_key, pages in sid_groups.items():
        sid, group_ts = group_key
        # Merge observations from all pages in this group
        all_obs = []
        for p in pages:
            all_obs.extend(p["observations"])

        # Use the group timestamp
        enc_timestamp = group_ts if group_ts else patient_info["clinical_timestamp"]

        # Deduplicate within this encounter
        seen_names = {}
        unique_obs = []
        for obs in all_obs:
            key = obs.test_name.lower().strip()
            if key not in seen_names:
                seen_names[key] = True
                unique_obs.append(obs)

        encounter = LabEncounter(
            encounter_id=f"SID_{sid}_{len(encounters)}" if sid != "UNKNOWN" else f"ENC_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            patient_id=patient_info["patient_id"],
            patient_name=patient_info["patient_name"],
            gender=patient_info["gender"],
            dob=patient_info["dob"],
            clinical_timestamp=enc_timestamp or "",
            ordering_physician=patient_info["ordering_physician"],
            observations=unique_obs,
            imaging_reports=[], # Assign below
        )
        encounter = process_encounter(encounter)
        encounters.append(encounter)

    # Sort by timestamp (oldest first)
    encounters.sort(key=lambda e: e.clinical_timestamp or "")
    
    # Attach all imaging reports to the latest encounter
    if encounters and imaging_reports:
        encounters[-1].imaging_reports = imaging_reports

    return encounters


def parse_lab_pdf(pdf_file) -> Optional[LabEncounter]:
    """
    Legacy single-encounter parser. Returns the latest encounter.
    For multi-encounter support, use parse_lab_pdf_multi() instead.
    """
    encounters = parse_lab_pdf_multi(pdf_file)
    if not encounters:
        return None
    return encounters[-1]  # Return the most recent


def parse_lab_pdf_bytes(pdf_bytes: bytes) -> List[LabEncounter]:
    """Parse PDF bytes, returning list of encounters (one per SID)."""
    return parse_lab_pdf_multi(io.BytesIO(pdf_bytes))
