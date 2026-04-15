"""
HIDU EWS — SQLite Persistence Layer
Lưu trữ lịch sử encounter để không mất dữ liệu khi tắt app.
"""

import sqlite3
import json
import os
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from modules.data_models import LabEncounter, Observation, ReferenceRange

# Database path
DB_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DB_DIR / "hidu_ews.db"


def init_db():
    """Create database and tables if they don't exist."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS encounters (
            id              TEXT PRIMARY KEY,
            patient_id      TEXT,
            patient_name    TEXT,
            gender          TEXT,
            dob             TEXT,
            clinical_timestamp TEXT,
            ordering_physician TEXT,
            lab_technician  TEXT,
            json_data       TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patient ON encounters(patient_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON encounters(clinical_timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON encounters(patient_name)")
    conn.commit()
    conn.close()


def _encounter_to_json(encounter: LabEncounter) -> str:
    """Serialize encounter to JSON string."""
    return json.dumps(encounter.to_fhir_json(), ensure_ascii=False)


def _json_to_encounter(json_str: str) -> LabEncounter:
    """Deserialize encounter from JSON string."""
    data = json.loads(json_str)
    observations = []
    for obs_data in data.get("observations", []):
        ref_data = obs_data.get("reference_range", {})
        ref = ReferenceRange(
            low=ref_data.get("low"),
            high=ref_data.get("high"),
            text=ref_data.get("text", ""),
        )
        obs = Observation(
            test_code=obs_data.get("test_code", ""),
            test_name=obs_data.get("test_name", ""),
            value_numeric=obs_data.get("value_numeric"),
            value_string=obs_data.get("value_string"),
            unit=obs_data.get("unit", ""),
            reference_range=ref,
            interpretation_flag=obs_data.get("interpretation_flag", "N"),
            color_code=obs_data.get("color_code", "gray"),
            category=obs_data.get("category", "OTHER"),
            machine=obs_data.get("machine"),
            trend=obs_data.get("trend"),
        )
        observations.append(obs)

    patient = data.get("patient", {})
    return LabEncounter(
        encounter_id=data.get("encounter_id", ""),
        patient_id=patient.get("patient_id", ""),
        patient_name=patient.get("name", ""),
        gender=patient.get("gender", ""),
        dob=patient.get("dob", ""),
        clinical_timestamp=data.get("clinical_timestamp", ""),
        ordering_physician=data.get("ordering_physician", ""),
        observations=observations,
        imaging_reports=data.get("imaging_reports", []),
        vitals=data.get("vitals", {}),
    )


def save_encounter(encounter: LabEncounter) -> bool:
    """Save encounter to database. Returns True if new, False if updated."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    json_data = _encounter_to_json(encounter)

    cursor.execute(
        "SELECT id FROM encounters WHERE id = ?",
        (encounter.encounter_id,),
    )
    exists = cursor.fetchone() is not None

    if exists:
        cursor.execute(
            """UPDATE encounters SET json_data = ?, patient_name = ?,
               patient_id = ?, clinical_timestamp = ?
               WHERE id = ?""",
            (json_data, encounter.patient_name, encounter.patient_id,
             encounter.clinical_timestamp, encounter.encounter_id),
        )
    else:
        cursor.execute(
            """INSERT INTO encounters
               (id, patient_id, patient_name, gender, dob,
                clinical_timestamp, ordering_physician, json_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (encounter.encounter_id, encounter.patient_id,
             encounter.patient_name, encounter.gender, encounter.dob,
             encounter.clinical_timestamp, encounter.ordering_physician,
             json_data),
        )

    conn.commit()
    conn.close()
    return not exists


def load_encounters_by_patient(patient_id: str) -> List[LabEncounter]:
    """Load all encounters for a specific patient, sorted by timestamp."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT json_data FROM encounters WHERE patient_id = ? ORDER BY clinical_timestamp",
        (patient_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [_json_to_encounter(row[0]) for row in rows]


def load_all_patients() -> List[dict]:
    """Load summary of all patients in database."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT patient_id, patient_name, gender, dob,
               COUNT(*) as enc_count,
               MAX(clinical_timestamp) as latest
        FROM encounters
        GROUP BY patient_id
        ORDER BY latest DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "patient_id": r[0],
            "patient_name": r[1],
            "gender": r[2],
            "dob": r[3],
            "encounter_count": r[4],
            "latest_timestamp": r[5],
        }
        for r in rows
    ]


def search_patients(query: str) -> List[dict]:
    """Search patients by name or patient_id."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    like_query = f"%{query}%"
    cursor.execute("""
        SELECT patient_id, patient_name, gender, dob,
               COUNT(*) as enc_count,
               MAX(clinical_timestamp) as latest
        FROM encounters
        WHERE patient_name LIKE ? OR patient_id LIKE ?
        GROUP BY patient_id
        ORDER BY latest DESC
    """, (like_query, like_query))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "patient_id": r[0],
            "patient_name": r[1],
            "gender": r[2],
            "dob": r[3],
            "encounter_count": r[4],
            "latest_timestamp": r[5],
        }
        for r in rows
    ]


def delete_encounter(encounter_id: str):
    """Delete a specific encounter."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM encounters WHERE id = ?", (encounter_id,))
    conn.commit()
    conn.close()


def delete_patient(patient_id: str):
    """Delete all encounters for a specific patient."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM encounters WHERE patient_id = ?", (patient_id,))
    conn.commit()
    conn.close()


def delete_all_data():
    """Delete all data from database."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM encounters")
    conn.commit()
    conn.close()
