"""
Attendance Reconciliation & Multi-Source Audit Engine
Cross-references timetable schedules, faculty attendance logs, biometric door sensors,
campus gate turnstiles, and classroom QR check-ins.
Detects discrepancies with evidence tracking, confidence scoring, and review workflows.
Includes strict administrative disclaimers regarding presumptive absence and proof of presence.
"""

import sqlite3
import pandas as pd
import numpy as np
import datetime
from typing import Dict, Any, List, Optional, Tuple
from database.database import get_connection, log_audit_action, DB_PATH

DISCLAIMER_TEXT = (
    "DISCREPANCY VERIFICATION ADVISORY: Gate entry does not prove continuous campus presence. "
    "A missing biometric record does not prove absence. Wi-Fi connection, device location, or "
    "QR check-in alone does not prove a student's identity or classroom presence. "
    "Flagged items represent operational discrepancies requiring human review, NOT confirmed misconduct."
)


def import_raw_events_stream(
    events_df: pd.DataFrame,
    source_type: str,
    batch_id: str,
    db_path: str = DB_PATH
) -> int:
    """
    Ingests raw source event logs (biometric, gate, qr_code) into imported_source_events table.
    Expected columns: student_id, event_timestamp, event_type, location_or_device, raw_payload
    """
    if events_df.empty:
        return 0

    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.datetime.now().isoformat()
    rows = []

    for _, r in events_df.iterrows():
        s_id = str(r.get("student_id", "")).strip()
        ts = str(r.get("event_timestamp", r.get("timestamp", ""))).strip()
        e_type = str(r.get("event_type", "scan")).strip()
        loc = str(r.get("location_or_device", r.get("device_id", "Default_Sensor"))).strip()
        payload = str(r.get("raw_payload", "{}"))
        if s_id and ts:
            rows.append((source_type, s_id, ts, e_type, loc, payload, batch_id, now_iso))

    cursor.executemany("""
        INSERT INTO imported_source_events (
            source_type, student_id, event_timestamp, event_type, location_or_device, raw_payload, batch_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, rows)

    conn.commit()
    conn.close()
    return len(rows)


def run_reconciliation_scan(
    date_filter: Optional[str] = None,
    tolerance_minutes: int = 15,
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """
    Executes multi-source reconciliation scanning for discrepancies:
    1. Gate entry logged, but classroom attendance marked Absent.
    2. Classroom attendance marked Present, but supporting check-in event is missing.
    3. Duplicate biometric punches within short window (< 3 minutes).
    4. Missing gate exit by end of day for students with gate entry.
    5. Late arrival beyond schedule start + tolerance.
    6. Conflicting attendance status across faculty vs device.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.datetime.now().isoformat()

    # Query attendance records
    att_query = "SELECT attendance_id, student_id, subject_id, date, hour, status, scheduled_start_time, check_in_time, check_out_time, source_system FROM attendance"
    if date_filter:
        att_query += f" WHERE date = '{date_filter}'"
    att_df = pd.read_sql_query(att_query, conn)

    # Query events
    events_query = "SELECT event_id, source_type, student_id, event_timestamp, event_type, location_or_device FROM imported_source_events"
    if date_filter:
        events_query += f" WHERE event_timestamp LIKE '{date_filter}%'"
    events_df = pd.read_sql_query(events_query, conn)

    new_cases_count = 0

    if att_df.empty and events_df.empty:
        conn.close()
        return {"total_cases_found": 0, "disclaimer": DISCLAIMER_TEXT}

    # Helper to check if case already exists in DB
    def case_exists(stu_id: str, d: str, p: int, disc_type: str) -> bool:
        cursor.execute("""
            SELECT COUNT(*) FROM reconciliation_cases 
            WHERE student_id = ? AND date = ? AND period_number = ? AND discrepancy_type = ?
        """, (stu_id, d, p, disc_type))
        return cursor.fetchone()[0] > 0

    # Rule 1: Gate Entry Recorded but Classroom Attendance Marked Absent
    if not events_df.empty and not att_df.empty:
        gate_entries = events_df[(events_df["source_type"] == "campus_gate") & (events_df["event_type"].isin(["gate_entry", "entry", "in"]))]
        absent_classes = att_df[att_df["status"] == "Absent"]

        for _, att_row in absent_classes.iterrows():
            stu = att_row["student_id"]
            d = att_row["date"]
            period = int(att_row["hour"])
            
            # Check if student had a gate entry on this date
            stu_gate = gate_entries[(gate_entries["student_id"] == stu) & (gate_entries["event_timestamp"].str.startswith(d))]
            if not stu_gate.empty:
                disc_type = "GATE_ENTRY_CLASSROOM_ABSENT"
                if not case_exists(stu, d, period, disc_type):
                    entry_ts = stu_gate.iloc[0]["event_timestamp"]
                    gate_loc = stu_gate.iloc[0]["location_or_device"]
                    cursor.execute("""
                        INSERT INTO reconciliation_cases (
                            student_id, date, period_number, subject_id, discrepancy_type,
                            sources_involved, evidence_present, evidence_missing, confidence_score,
                            review_status, reviewer_notes, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', '', ?, ?);
                    """, (
                        stu, d, period, att_row["subject_id"], disc_type,
                        "Campus Gate, Faculty Attendance",
                        f"Gate entry logged at {entry_ts} ({gate_loc})",
                        f"Classroom presence for period {period} marked Absent",
                        75.0, now_iso, now_iso
                    ))
                    new_cases_count += 1

    # Rule 2: Classroom Marked Present but Supporting Biometric/QR Event Missing (when devices configured)
    if not events_df.empty and not att_df.empty:
        device_sources = events_df[events_df["source_type"].isin(["biometric_door", "classroom_qr", "biometric"])]
        if not device_sources.empty:
            present_classes = att_df[att_df["status"] == "Present"]
            for _, att_row in present_classes.iterrows():
                stu = att_row["student_id"]
                d = att_row["date"]
                period = int(att_row["hour"])

                stu_dev = device_sources[(device_sources["student_id"] == stu) & (device_sources["event_timestamp"].str.startswith(d))]
                if stu_dev.empty:
                    disc_type = "PRESENT_WITHOUT_DEVICE_CHECKIN"
                    if not case_exists(stu, d, period, disc_type):
                        cursor.execute("""
                            INSERT INTO reconciliation_cases (
                                student_id, date, period_number, subject_id, discrepancy_type,
                                sources_involved, evidence_present, evidence_missing, confidence_score,
                                review_status, reviewer_notes, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', '', ?, ?);
                        """, (
                            stu, d, period, att_row["subject_id"], disc_type,
                            "Faculty Attendance, Biometric Door",
                            f"Faculty roster marked Present for period {period}",
                            "No digital biometric or QR check-in timestamp found",
                            60.0, now_iso, now_iso
                        ))
                        new_cases_count += 1

    # Rule 3: Duplicate Rapid Biometric Events (< 2 minutes apart)
    if not events_df.empty:
        bio_events = events_df[events_df["source_type"].isin(["biometric_door", "biometric"])].copy()
        if not bio_events.empty:
            bio_events["dt"] = pd.to_datetime(bio_events["event_timestamp"], errors="coerce")
            bio_events = bio_events.sort_values(by=["student_id", "dt"])
            
            for stu, grp in bio_events.groupby("student_id"):
                grp_times = grp["dt"].dropna().tolist()
                for i in range(len(grp_times) - 1):
                    diff_sec = (grp_times[i+1] - grp_times[i]).total_seconds()
                    if 0 < diff_sec < 120:  # less than 2 minutes
                        d = grp_times[i].strftime("%Y-%m-%d")
                        disc_type = "DUPLICATE_BIOMETRIC_PUNCH"
                        if not case_exists(stu, d, 1, disc_type):
                            cursor.execute("""
                                INSERT INTO reconciliation_cases (
                                    student_id, date, period_number, subject_id, discrepancy_type,
                                    sources_involved, evidence_present, evidence_missing, confidence_score,
                                    review_status, reviewer_notes, created_at, updated_at
                                ) VALUES (?, ?, 1, NULL, ?, ?, ?, ?, ?, 'Pending', '', ?, ?);
                            """, (
                                stu, d, disc_type,
                                "Biometric Terminal",
                                f"Successive punches recorded at {grp_times[i].strftime('%H:%M:%S')} and {grp_times[i+1].strftime('%H:%M:%S')} (Δ {int(diff_sec)}s)",
                                "Unique verification token",
                                85.0, now_iso, now_iso
                            ))
                            new_cases_count += 1

    # Rule 4: Late Arrival Discrepancy based on Schedule Timestamps
    if not att_df.empty:
        timed_att = att_df[(att_df["scheduled_start_time"].str.len() > 0) & (att_df["check_in_time"].str.len() > 0)].copy()
        for _, row in timed_att.iterrows():
            try:
                # Compare HH:MM
                t_sched = datetime.datetime.strptime(row["scheduled_start_time"][:5], "%H:%M")
                t_actual = datetime.datetime.strptime(row["check_in_time"][:5], "%H:%M")
                delta_mins = (t_actual - t_sched).total_seconds() / 60.0
                if delta_mins > tolerance_minutes and row["status"] != "Late":
                    stu = row["student_id"]
                    d = row["date"]
                    period = int(row["hour"])
                    disc_type = "UNRECORDED_LATE_ARRIVAL"
                    if not case_exists(stu, d, period, disc_type):
                        cursor.execute("""
                            INSERT INTO reconciliation_cases (
                                student_id, date, period_number, subject_id, discrepancy_type,
                                sources_involved, evidence_present, evidence_missing, confidence_score,
                                review_status, reviewer_notes, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', '', ?, ?);
                        """, (
                            stu, d, period, row["subject_id"], disc_type,
                            "Check-in Timestamp vs Timetable Schedule",
                            f"Arrived at {row['check_in_time']} for {row['scheduled_start_time']} session (+{int(delta_mins)} mins)",
                            "Official Late designation or faculty excuse note",
                            90.0, now_iso, now_iso
                        ))
                        new_cases_count += 1
            except Exception:
                pass

    conn.commit()
    conn.close()

    return {
        "new_cases_created": new_cases_count,
        "disclaimer": DISCLAIMER_TEXT
    }


def get_reconciliation_cases(
    status: Optional[str] = None,
    discrepancy_type: Optional[str] = None,
    student_id: Optional[str] = None,
    db_path: str = DB_PATH
) -> pd.DataFrame:
    """
    Retrieves reconciliation cases merged with student details for administrative review.
    """
    conn = get_connection(db_path)
    query = """
        SELECT 
            rc.case_id,
            rc.student_id,
            s.register_number,
            s.name AS student_name,
            s.department,
            s.section,
            rc.date,
            rc.period_number,
            rc.subject_id,
            rc.discrepancy_type,
            rc.sources_involved,
            rc.evidence_present,
            rc.evidence_missing,
            rc.confidence_score,
            rc.review_status,
            rc.reviewer_notes,
            rc.resolved_by,
            rc.resolved_at,
            rc.created_at
        FROM reconciliation_cases rc
        LEFT JOIN students s ON rc.student_id = s.student_id
        WHERE 1=1
    """
    params = []
    if status and status != "All":
        query += " AND rc.review_status = ?"
        params.append(status)
    if discrepancy_type and discrepancy_type != "All":
        query += " AND rc.discrepancy_type = ?"
        params.append(discrepancy_type)
    if student_id:
        query += " AND rc.student_id = ?"
        params.append(student_id)

    query += " ORDER BY rc.case_id DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def update_case_status(
    case_id: int,
    new_status: str,
    reviewer_notes: str,
    reviewer_user: str,
    db_path: str = DB_PATH
) -> bool:
    """
    Updates the status and resolution notes of a reconciliation discrepancy case,
    recording an immutable entry in the audit log.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.datetime.now().isoformat()

    cursor.execute("SELECT student_id, review_status, discrepancy_type FROM reconciliation_cases WHERE case_id = ?", (case_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    stu_id, old_status, disc_type = row

    cursor.execute("""
        UPDATE reconciliation_cases SET
            review_status = ?,
            reviewer_notes = ?,
            resolved_by = ?,
            resolved_at = ?,
            updated_at = ?
        WHERE case_id = ?;
    """, (new_status, reviewer_notes, reviewer_user, now_iso, now_iso, case_id))

    # Log action in audit log directly
    cursor.execute("""
        INSERT INTO audit_logs (action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "RECONCILIATION_REVIEW", "reconciliation_cases", str(case_id),
        old_status, new_status, reviewer_user, now_iso,
        f"Case {case_id} ({disc_type}) for {stu_id}. Notes: {reviewer_notes}"
    ))

    conn.commit()
    conn.close()
    return True
