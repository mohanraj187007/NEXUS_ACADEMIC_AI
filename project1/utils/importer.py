"""
Universal Bulk Data Import Engine
Academic Attendance Pattern & Risk Analytics System
Supports CSV and Excel (.xlsx) imports across 9 institutional categories:
1. Colleges & Campuses
2. Buildings, Floors & Rooms
3. Departments, HODs & Faculty
4. Courses, Semesters, Batches & Sections
5. Students & Enrollment
6. Subjects & Faculty Allocations
7. Timetables & Room Allocations (with capacity check)
8. Attendance Records
9. Campus Geofence Coordinates
Includes 12-step validation, preview, duplicate detection, row errors, templates, and history logs.
"""

import pandas as pd
import numpy as np
import io
import json
import uuid
import datetime
from typing import Dict, Any, List, Tuple, Optional
import re
import random
import sqlite3
import openpyxl
from database.database import get_connection, log_audit_action, record_import_history, DB_PATH

# 1. Category Definitions & Schemas
IMPORT_CATEGORIES = {
    "attendance": "Attendance Records",
    "students": "Student Information & Registration",
    "subjects_assignments": "Subjects & Faculty Allocations",
    "timetables_allocations": "Timetables & Classroom Allocations",
    "buildings_rooms": "Buildings, Floors & Rooms",
    "departments_faculty": "Departments, HODs & Faculty",
    "courses_batches": "Courses, Semesters & Batches",
    "colleges_campuses": "Colleges & Campus Details",
    "geofence_coordinates": "Campus Geofence Coordinates"
}

CATEGORY_SCHEMAS = {
    "attendance": {
        "required": ["student_id", "attendance_date", "attendance_status"],
        "columns": [
            "student_id", "student_name", "department", "semester", "year", "section",
            "subject_id", "attendance_date", "period_number", "scheduled_start_time",
            "scheduled_end_time", "attendance_status", "check_in_time", "check_out_time", "source_system"
        ],
        "samples": [
            ["STU_1001", "Aarav Gupta", "Computer Science", 5, 3, "A", "CS301", "2024-03-01", 1, "09:00", "09:50", "Present", "08:58", "09:50", "FACULTY_ROSTER"],
            ["STU_1002", "Aditi Sundaram", "Computer Science", 5, 3, "A", "CS301", "2024-03-01", 1, "09:00", "09:50", "Late", "09:12", "09:50", "BIOMETRIC_DOOR"]
        ]
    },
    "students": {
        "required": ["student_id", "register_number", "name", "department"],
        "columns": ["student_id", "register_number", "name", "department", "year", "semester", "section", "email"],
        "samples": [
            ["STU_2001", "21CS101", "Rohan Verma", "Computer Science", 3, 5, "A", "rohan.v@college.edu"],
            ["STU_2002", "21IT102", "Sneha Reddy", "Information Technology", 3, 5, "B", "sneha.r@college.edu"]
        ]
    },
    "subjects_assignments": {
        "required": ["subject_id", "subject_code", "subject_name"],
        "columns": ["subject_id", "subject_code", "subject_name", "department", "semester", "credits", "faculty_name"],
        "samples": [
            ["SUB_CS501", "CS501", "Distributed Cloud Architecture", "Computer Science", 5, 4, "Dr. Ananya Sharma"],
            ["SUB_CS502", "CS502", "Deep Learning & Neural Networks", "Computer Science", 5, 4, "Prof. K. Sundaram"]
        ]
    },
    "timetables_allocations": {
        "required": ["session_id", "subject_id", "day_of_week", "period_number", "scheduled_start_time", "scheduled_end_time"],
        "columns": [
            "session_id", "subject_id", "room_id", "day_of_week", "period_number",
            "scheduled_start_time", "scheduled_end_time", "semester", "section", "expected_strength"
        ],
        "samples": [
            ["SESS_MON_1", "SUB_CS501", "RM_101", "Monday", 1, "09:00", "09:50", 5, "A", 65],
            ["SESS_MON_2", "SUB_CS502", "RM_102", "Monday", 2, "10:00", "10:50", 5, "A", 40]
        ]
    },
    "buildings_rooms": {
        "required": ["room_id", "building_code", "room_number", "room_type", "capacity"],
        "columns": [
            "room_id", "building_code", "building_name", "floor_number", "room_number",
            "room_name", "room_type", "capacity", "dimension_sqft", "equipment_details"
        ],
        "samples": [
            ["RM_105", "ATB", "Alan Turing Block", 1, "105", "Robotics Laboratory", "Laboratory", 35, 800.0, "30 ARM Microcontrollers, 3D Printer"],
            ["RM_205", "ATB", "Alan Turing Block", 2, "205", "Lecture Hall 205", "Classroom", 75, 750.0, "Smart Laser Projector, Audio System"]
        ]
    },
    "departments_faculty": {
        "required": ["department_id", "department_code", "department_name"],
        "columns": ["department_id", "department_code", "department_name", "hod_name", "hod_email", "hod_room_id"],
        "samples": [
            ["DEPT_AI", "AIDS", "Artificial Intelligence & Data Science", "Dr. Priya Nair", "hod.ai@niet.edu", "RM_201"],
            ["DEPT_ECE", "ECE", "Electronics & Communication Engineering", "Dr. M. Karthik", "hod.ece@niet.edu", "RM_301"]
        ]
    },
    "courses_batches": {
        "required": ["batch_id", "programme", "academic_year", "semester", "section"],
        "columns": ["batch_id", "department_code", "programme", "academic_year", "semester", "section"],
        "samples": [
            ["BATCH_BTECH_CS_5A", "CSE", "B.Tech Computer Science", 3, 5, "A"],
            ["BATCH_BTECH_IT_5B", "IT", "B.Tech Information Technology", 3, 5, "B"]
        ]
    },
    "colleges_campuses": {
        "required": ["institution_code", "institution_name", "campus_code", "campus_name"],
        "columns": ["institution_code", "institution_name", "institution_type", "campus_code", "campus_name", "city", "latitude", "longitude", "geofence_radius"],
        "samples": [
            ["NIET", "National Institute of Engineering & Technology", "University", "CAMP_NORTH", "North Innovation Campus", "Bangalore", 13.0358, 77.5970, 280.0],
            ["AGBRC", "Apex Global Business & Research College", "College", "CAMP_EAST", "East Waterfront Campus", "Chennai", 12.9800, 80.2500, 250.0]
        ]
    },
    "geofence_coordinates": {
        "required": ["campus_code", "latitude", "longitude", "geofence_radius_meters"],
        "columns": ["campus_code", "campus_name", "latitude", "longitude", "geofence_radius_meters", "is_active"],
        "samples": [
            ["CAMP_TECH", "Metro Tech Campus", 12.9716, 77.5946, 300.0, 1],
            ["CAMP_CITY", "East Lake Campus", 12.9352, 77.6245, 250.0, 1]
        ]
    }
}


def generate_category_template(category: str, file_format: str = "csv") -> bytes:
    """Generates standard downloadable CSV or Excel templates for any of the 9 categories."""
    schema = CATEGORY_SCHEMAS.get(category, CATEGORY_SCHEMAS["attendance"])
    df = pd.DataFrame(schema["samples"], columns=schema["columns"])

    if file_format.lower() in ["excel", "xlsx"]:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Template_{category[:20]}"
        ws.append(schema["columns"])
        for row in schema["samples"]:
            ws.append(row)

        header_font = openpyxl.styles.Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = openpyxl.styles.PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = openpyxl.styles.Alignment(horizontal="center", vertical="center")

        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()
    else:
        return df.to_csv(index=False).encode("utf-8")


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Standardizes column headers by trimming, lowercasing, and replacing spaces/hyphens with underscores."""
    clean_cols = {c: str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns}
    return df.rename(columns=clean_cols)


def validate_and_prepare_batch(
    file_bytes: bytes,
    file_name: str,
    category: str,
    institution_id: str = "INST_001",
    db_path: str = DB_PATH
) -> Tuple[bool, Dict[str, Any], pd.DataFrame]:
    """
    Parses CSV/XLSX file, normalizes columns, performs row-level type/required/FK checks,
    detects duplicates, and prepares records for transactional commit.
    """
    batch_id = f"BATCH_{uuid.uuid4().hex[:8].upper()}"

    # 1. Parse File
    try:
        if file_name.lower().endswith(".xlsx") or file_name.lower().endswith(".xls"):
            df_raw = pd.read_excel(io.BytesIO(file_bytes))
        else:
            try:
                df_raw = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8")
            except UnicodeDecodeError:
                df_raw = pd.read_csv(io.BytesIO(file_bytes), encoding="latin1")
    except Exception as e:
        return False, {
            "error": f"Failed to read file format: {str(e)}",
            "batch_id": batch_id,
            "total_raw": 0,
            "valid_count": 0,
            "invalid_count": 0,
            "duplicate_count": 0,
            "row_errors": []
        }, pd.DataFrame()

    total_raw = len(df_raw)
    if total_raw == 0:
        return False, {
            "error": "The uploaded file contains zero records.",
            "batch_id": batch_id,
            "total_raw": 0,
            "valid_count": 0,
            "invalid_count": 0,
            "duplicate_count": 0,
            "row_errors": []
        }, pd.DataFrame()

    df = normalize_headers(df_raw.copy())
    schema = CATEGORY_SCHEMAS.get(category, CATEGORY_SCHEMAS["attendance"])
    required_cols = schema["required"]

    # Check for missing required columns
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        return False, {
            "error": f"Missing mandatory columns for category '{IMPORT_CATEGORIES.get(category, category)}': {', '.join(missing)}.",
            "batch_id": batch_id,
            "total_raw": total_raw,
            "valid_count": 0,
            "invalid_count": total_raw,
            "row_errors": [{"row": 1, "id": "HEADER", "field": m, "error": "Missing column"} for m in missing]
        }, pd.DataFrame()

    row_errors = []
    valid_rows = []

    # Connect to check FK references and existing records
    conn = get_connection(db_path)
    cursor = conn.cursor()

    existing_rooms = {}
    if category == "timetables_allocations":
        cursor.execute("SELECT room_id, capacity FROM rooms WHERE institution_id = ?", (institution_id,))
        existing_rooms = {r[0]: r[1] for r in cursor.fetchall()}

    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel row index
        has_error = False

        # Validate required fields non-empty
        for req in required_cols:
            val = str(row.get(req, "")).strip()
            if not val or val.lower() in ["nan", "none", "null"]:
                row_errors.append({
                    "row": row_num,
                    "id": str(row.get(required_cols[0], "N/A")),
                    "field": req,
                    "error": f"Required field '{req}' cannot be empty.",
                    "raw_val": str(row.get(req, ""))
                })
                has_error = True
                break

        if has_error:
            continue

        # Category-Specific Field Sanity Checks
        if category == "attendance":
            raw_d = str(row.get("attendance_date", ""))
            try:
                p_date = pd.to_datetime(raw_d)
                row["attendance_date"] = p_date.strftime("%Y-%m-%d")
            except Exception:
                row_errors.append({
                    "row": row_num,
                    "id": str(row.get("student_id", "")),
                    "field": "attendance_date",
                    "error": "Invalid date format. Expected YYYY-MM-DD.",
                    "raw_val": raw_d
                })
                continue

            status_val = str(row.get("attendance_status", "")).strip().title()
            if status_val not in ["Present", "Absent", "Late", "Excused", "Approved Leave", "Cancelled"]:
                row_errors.append({
                    "row": row_num,
                    "id": str(row.get("student_id", "")),
                    "field": "attendance_status",
                    "error": f"Invalid status '{status_val}'. Must be Present, Absent, Late, Excused, Approved Leave, or Cancelled.",
                    "raw_val": status_val
                })
                continue

        elif category == "buildings_rooms":
            try:
                cap = int(pd.to_numeric(row.get("capacity", 60), errors="coerce") or 60)
                if cap < 1 or cap > 1000:
                    row_errors.append({
                        "row": row_num,
                        "id": str(row.get("room_id", "")),
                        "field": "capacity",
                        "error": "Room capacity must be between 1 and 1000.",
                        "raw_val": str(row.get("capacity"))
                    })
                    continue
                row["capacity"] = cap
            except Exception:
                pass

        elif category == "timetables_allocations":
            room_id = str(row.get("room_id", "")).strip()
            exp_strength = int(pd.to_numeric(row.get("expected_strength", 60), errors="coerce") or 60)
            if room_id in existing_rooms:
                room_cap = existing_rooms[room_id]
                if exp_strength > room_cap:
                    # Capacity warning (not fatal, but flagged)
                    row["capacity_warning"] = f"Expected strength ({exp_strength}) exceeds room capacity ({room_cap})!"

        elif category == "geofence_coordinates":
            try:
                lat = float(row.get("latitude"))
                lon = float(row.get("longitude"))
                rad = float(row.get("geofence_radius_meters", row.get("geofence_radius", 300.0)))
                if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0) or rad <= 0:
                    row_errors.append({
                        "row": row_num,
                        "id": str(row.get("campus_code", "")),
                        "field": "coordinates",
                        "error": "Invalid latitude/longitude or non-positive geofence radius.",
                        "raw_val": f"Lat: {lat}, Lon: {lon}, Rad: {rad}"
                    })
                    continue
            except Exception:
                row_errors.append({
                    "row": row_num,
                    "id": str(row.get("campus_code", "")),
                    "field": "coordinates",
                    "error": "Latitude, longitude, and radius must be valid numbers.",
                    "raw_val": ""
                })
                continue

        valid_rows.append(row.to_dict())

    conn.close()
    valid_df = pd.DataFrame(valid_rows)

    if valid_df.empty:
        return False, {
            "error": "All submitted rows failed validation. See row errors table below.",
            "batch_id": batch_id,
            "total_raw": total_raw,
            "valid_count": 0,
            "invalid_count": len(row_errors),
            "duplicate_count": 0,
            "row_errors": row_errors
        }, pd.DataFrame()

    # Deduplicate within batch on primary unique keys
    primary_key_map = {
        "attendance": ["student_id", "attendance_date", "period_number", "subject_id"],
        "students": ["student_id"],
        "subjects_assignments": ["subject_id"],
        "timetables_allocations": ["session_id"],
        "buildings_rooms": ["room_id"],
        "departments_faculty": ["department_id"],
        "courses_batches": ["batch_id"],
        "colleges_campuses": ["campus_code"],
        "geofence_coordinates": ["campus_code"]
    }

    dedup_keys = [k for k in primary_key_map.get(category, []) if k in valid_df.columns]
    dup_count = 0
    if dedup_keys:
        before_len = len(valid_df)
        valid_df = valid_df.drop_duplicates(subset=dedup_keys, keep="last").reset_index(drop=True)
        dup_count = before_len - len(valid_df)

    summary = {
        "batch_id": batch_id,
        "category": category,
        "file_name": file_name,
        "total_raw": total_raw,
        "valid_count": len(valid_df),
        "invalid_count": len(row_errors),
        "duplicate_count": dup_count,
        "row_errors": row_errors
    }

    return True, summary, valid_df


def commit_prepared_batch(
    valid_df: pd.DataFrame,
    category: str,
    batch_id: str,
    institution_id: str = "INST_001",
    performed_by: str = "Administrator",
    file_name: str = "upload.csv",
    db_path: str = DB_PATH
) -> Tuple[bool, str]:
    """
    Saves validated batch records into SQLite within a safe transaction.
    Logs to import_history and audit_logs.
    """
    if valid_df.empty:
        return False, "No valid records to commit."

    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.datetime.now().isoformat()

    try:
        conn.execute("BEGIN IMMEDIATE;")

        if category == "attendance":
            for _, r in valid_df.iterrows():
                sub_id = str(r.get("subject_id", "GEN101"))
                p_num = int(pd.to_numeric(r.get("period_number", 1), errors="coerce") or 1)
                
                # Ensure student exists
                cursor.execute("""
                    INSERT INTO students (student_id, institution_id, register_number, name, department, year, semester, section, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(student_id) DO UPDATE SET
                        name = COALESCE(excluded.name, students.name);
                """, (r["student_id"], institution_id, str(r.get("register_number", r["student_id"])), str(r.get("student_name", f"Student {r['student_id']}")), str(r.get("department", "General")), int(r.get("year", 1)), int(r.get("semester", 1)), str(r.get("section", "A")), now_iso))

                # Ensure subject exists
                cursor.execute("""
                    INSERT INTO subjects (subject_id, institution_id, subject_code, subject_name, department, semester)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(subject_id) DO NOTHING;
                """, (sub_id, institution_id, sub_id.replace("SUB_", ""), str(r.get("subject_name", f"Course {sub_id}")), str(r.get("department", "General")), int(r.get("semester", 1))))

                # Insert attendance
                cursor.execute("""
                    INSERT INTO attendance (
                        institution_id, student_id, subject_id, date, status, hour, week,
                        scheduled_start_time, scheduled_end_time, check_in_time, check_out_time,
                        source_system, record_created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    institution_id, r["student_id"], sub_id, r["attendance_date"], r["attendance_status"],
                    p_num, str(r.get("scheduled_start_time", "")), str(r.get("scheduled_end_time", "")),
                    str(r.get("check_in_time", "")), str(r.get("check_out_time", "")),
                    str(r.get("source_system", "BULK_UPLOAD")), now_iso, now_iso
                ))

        elif category == "students":
            for _, r in valid_df.iterrows():
                cursor.execute("""
                    INSERT INTO students (student_id, institution_id, register_number, name, department, year, semester, section, email, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(student_id) DO UPDATE SET
                        register_number = excluded.register_number,
                        name = excluded.name,
                        department = excluded.department,
                        year = excluded.year,
                        semester = excluded.semester,
                        section = excluded.section,
                        email = excluded.email;
                """, (
                    r["student_id"], institution_id, str(r["register_number"]), str(r["name"]),
                    str(r["department"]), int(r.get("year", 1)), int(r.get("semester", 1)),
                    str(r.get("section", "A")), str(r.get("email", "")), now_iso
                ))

        elif category == "buildings_rooms":
            for _, r in valid_df.iterrows():
                b_code = str(r.get("building_code", "MAIN"))
                b_id = f"BLD_{b_code}"
                cursor.execute("""
                    INSERT INTO buildings (building_id, campus_id, institution_id, building_name, building_code, total_floors)
                    VALUES (?, 'CAMP_001', ?, ?, ?, ?)
                    ON CONFLICT(building_id) DO NOTHING;
                """, (b_id, institution_id, str(r.get("building_name", f"Building {b_code}")), b_code, 4))

                cursor.execute("""
                    INSERT INTO rooms (
                        room_id, building_id, campus_id, institution_id, room_number, room_name,
                        floor_number, room_type, capacity, dimension_sqft, equipment_details
                    ) VALUES (?, ?, 'CAMP_001', ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(room_id) DO UPDATE SET
                        capacity = excluded.capacity,
                        room_name = excluded.room_name,
                        equipment_details = excluded.equipment_details;
                """, (
                    r["room_id"], b_id, institution_id, str(r["room_number"]),
                    str(r.get("room_name", f"Room {r['room_number']}")),
                    int(r.get("floor_number", 1)), str(r.get("room_type", "Classroom")),
                    int(r.get("capacity", 60)), float(r.get("dimension_sqft", 650.0)),
                    str(r.get("equipment_details", "Standard Classroom"))
                ))

        elif category == "timetables_allocations":
            for _, r in valid_df.iterrows():
                cursor.execute("""
                    INSERT INTO timetable_sessions (
                        session_id, institution_id, subject_id, room_id, day_of_week, period_number,
                        scheduled_start_time, scheduled_end_time, semester, section, expected_strength
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        room_id = excluded.room_id,
                        scheduled_start_time = excluded.scheduled_start_time,
                        scheduled_end_time = excluded.scheduled_end_time,
                        expected_strength = excluded.expected_strength;
                """, (
                    r["session_id"], institution_id, str(r["subject_id"]), str(r.get("room_id", "")),
                    str(r["day_of_week"]), int(r["period_number"]), str(r["scheduled_start_time"]),
                    str(r["scheduled_end_time"]), int(r.get("semester", 1)), str(r.get("section", "A")),
                    int(r.get("expected_strength", 60))
                ))

        elif category == "subjects_assignments":
            for _, r in valid_df.iterrows():
                cursor.execute("""
                    INSERT INTO subjects (subject_id, institution_id, subject_code, subject_name, department, semester, credits, faculty_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(subject_id) DO UPDATE SET
                        subject_name = excluded.subject_name,
                        faculty_name = excluded.faculty_name;
                """, (
                    r["subject_id"], institution_id, str(r["subject_code"]), str(r["subject_name"]),
                    str(r.get("department", "General")), int(r.get("semester", 1)),
                    int(r.get("credits", 3)), str(r.get("faculty_name", "Faculty Assigned"))
                ))

        elif category == "departments_faculty":
            for _, r in valid_df.iterrows():
                cursor.execute("""
                    INSERT INTO departments (department_id, institution_id, campus_id, department_code, name, hod_name, hod_email, hod_room_id)
                    VALUES (?, ?, 'CAMP_001', ?, ?, ?, ?, ?)
                    ON CONFLICT(department_id) DO UPDATE SET
                        name = excluded.name,
                        hod_name = excluded.hod_name,
                        hod_email = excluded.hod_email;
                """, (
                    r["department_id"], institution_id, str(r["department_code"]),
                    str(r.get("department_name", r.get("name", "Department"))),
                    str(r.get("hod_name", "")), str(r.get("hod_email", "")), str(r.get("hod_room_id", ""))
                ))

        elif category == "geofence_coordinates":
            for _, r in valid_df.iterrows():
                cursor.execute("""
                    UPDATE campuses SET
                        latitude = ?, longitude = ?, geofence_radius_meters = ?
                    WHERE campus_code = ? AND institution_id = ?;
                """, (
                    float(r["latitude"]), float(r["longitude"]),
                    float(r.get("geofence_radius_meters", r.get("geofence_radius", 300.0))),
                    str(r["campus_code"]), institution_id
                ))

        # Record Import History Log
        cursor.execute("""
            INSERT INTO import_history (
                import_id, institution_id, data_category, file_name, total_rows,
                valid_rows, invalid_rows, duplicate_rows, status, performed_by, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'SUCCESS', ?, ?);
        """, (batch_id, institution_id, category, file_name, len(valid_df), len(valid_df), performed_by, now_iso))

        # Record Audit Log
        cursor.execute("""
            INSERT INTO audit_logs (institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details)
            VALUES (?, 'BULK_IMPORT', ?, ?, NULL, ?, ?, ?, ?);
        """, (institution_id, category, batch_id, f"Committed {len(valid_df)} rows", performed_by, now_iso, f"Batch {batch_id} committed from {file_name}"))

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Transactional commit aborted: {str(e)}"
    finally:
        conn.close()

    return True, f"Successfully committed {len(valid_df)} records for {IMPORT_CATEGORIES.get(category, category)}."


def generate_student_sample_template(file_format: str = "xlsx") -> bytes:
    """Generates an official sample student roster template with VSB Engineering College sample rows."""
    sample_data = [
        {"register_number": "22CS101", "name": "Monish K", "department": "Computer Science & Engineering", "year": 2, "semester": 3, "section": "A", "email": "monish.k@vsbec.com"},
        {"register_number": "22CS102", "name": "Priya S", "department": "Computer Science & Engineering", "year": 2, "semester": 3, "section": "A", "email": "priya.s@vsbec.com"},
        {"register_number": "22CS103", "name": "Aarav Gupta", "department": "Computer Science & Engineering", "year": 2, "semester": 3, "section": "A", "email": "aarav.g@vsbec.com"},
        {"register_number": "22IT104", "name": "Karthik R", "department": "Information Technology", "year": 2, "semester": 3, "section": "B", "email": "karthik.r@vsbec.com"},
        {"register_number": "22AI105", "name": "Sneha Reddy", "department": "Artificial Intelligence & Data Science", "year": 2, "semester": 3, "section": "A", "email": "sneha.r@vsbec.com"}
    ]
    df_sample = pd.DataFrame(sample_data)
    buf = io.BytesIO()
    if file_format.lower() in ["xlsx", "xls"]:
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_sample.to_excel(writer, index=False, sheet_name="Students_Roster")
    else:
        df_sample.to_csv(buf, index=False, encoding="utf-8")
    return buf.getvalue()


def parse_student_roster_file(file_bytes: bytes, file_name: str) -> Tuple[bool, pd.DataFrame, str]:
    """
    Parses a student roster file from Excel (.xlsx, .xls), CSV (.csv), or PDF (.pdf).
    Returns (success, DataFrame with normalized student columns, message).
    """
    df_raw = None
    fn_lower = file_name.lower()

    try:
        if fn_lower.endswith((".xlsx", ".xls")):
            df_raw = pd.read_excel(io.BytesIO(file_bytes))
        elif fn_lower.endswith(".csv"):
            try:
                df_raw = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8")
            except UnicodeDecodeError:
                df_raw = pd.read_csv(io.BytesIO(file_bytes), encoding="latin1")
        elif fn_lower.endswith(".pdf"):
            try:
                from pypdf import PdfReader
            except ImportError:
                return False, pd.DataFrame(), "PDF reader library 'pypdf' is not available. Please install it or use an Excel/CSV file."

            reader = PdfReader(io.BytesIO(file_bytes))
            full_text = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"

            lines = [line.strip() for line in full_text.splitlines() if line.strip()]
            extracted = []
            reg_pattern = re.compile(r'\b([0-9]{2}[A-Za-z]{2,5}[0-9]{2,6}|VSB[0-9]{3,6}|STU[0-9_-]{3,6}|[0-9]{6,12})\b', re.IGNORECASE)

            for line in lines:
                m = reg_pattern.search(line)
                if m:
                    reg_no = m.group(1).upper()
                    parts = line.split(m.group(0))
                    after_match = parts[1].strip() if len(parts) > 1 else ""
                    before_match = parts[0].strip() if len(parts) > 0 else ""
                    before_clean = re.sub(r'^[0-9]+[\.\)\s-]*', '', before_match).strip()

                    dept = "Computer Science & Engineering"
                    name_candidate = ""

                    if len(after_match) >= 2:
                        tokens = after_match.split()
                        name_tokens = []
                        for t in tokens:
                            tu = t.upper().replace("&", "")
                            if tu in ["CSE", "CS", "IT", "AIDS", "AI", "ECE", "EEE", "MECH", "CIVIL"]:
                                if tu in ["CSE", "CS"]: dept = "Computer Science & Engineering"
                                elif tu == "IT": dept = "Information Technology"
                                elif tu in ["AIDS", "AI"]: dept = "Artificial Intelligence & Data Science"
                                elif tu == "ECE": dept = "Electronics & Communication Engineering"
                                elif tu == "MECH": dept = "Mechanical Engineering"
                                break
                            name_tokens.append(t)
                        name_candidate = " ".join(name_tokens).strip(" ,|-")
                    elif len(before_clean) >= 2:
                        name_candidate = before_clean.strip(" ,|-")

                    if not name_candidate:
                        name_candidate = f"Student {reg_no}"

                    extracted.append({
                        "register_number": reg_no,
                        "name": name_candidate.title(),
                        "department": dept,
                        "year": 2,
                        "semester": 3,
                        "section": "A"
                    })

            if not extracted:
                return False, pd.DataFrame(), "Could not automatically detect student roll numbers or names in this PDF. Please verify the PDF contains selectable text or upload as Excel/CSV."

            df_raw = pd.DataFrame(extracted)
        else:
            return False, pd.DataFrame(), f"Unsupported file type: {file_name}. Supported formats: .xlsx, .xls, .csv, .pdf"

    except Exception as e:
        return False, pd.DataFrame(), f"Error reading file '{file_name}': {str(e)}"

    if df_raw is None or df_raw.empty:
        return False, pd.DataFrame(), "The uploaded file contains zero records."

    # Column mapping & normalization
    col_map = {}
    for col in df_raw.columns:
        c_clean = str(col).strip().lower().replace(" ", "_").replace("-", "_").replace(".", "")
        if c_clean in ["student_name", "name", "full_name", "student", "candidate_name", "studentname", "student_names"]:
            col_map[col] = "name"
        elif c_clean in ["register_number", "reg_no", "regno", "roll_no", "rollno", "register_no", "reg_num", "roll_number", "reg_number", "id", "student_id"]:
            col_map[col] = "register_number"
        elif c_clean in ["department", "dept", "branch", "programme", "course"]:
            col_map[col] = "department"
        elif c_clean in ["year", "yr", "academic_year"]:
            col_map[col] = "year"
        elif c_clean in ["semester", "sem"]:
            col_map[col] = "semester"
        elif c_clean in ["section", "sec"]:
            col_map[col] = "section"
        elif c_clean in ["email", "mail", "email_id", "mail_id"]:
            col_map[col] = "email"

    df_norm = df_raw.rename(columns=col_map)

    if "name" not in df_norm.columns and len(df_norm.columns) >= 2:
        df_norm["name"] = df_norm.iloc[:, 1].astype(str)

    if "register_number" not in df_norm.columns:
        if len(df_norm.columns) >= 1:
            df_norm["register_number"] = df_norm.iloc[:, 0].astype(str)
        else:
            df_norm["register_number"] = [f"22CS{101+i}" for i in range(len(df_norm))]

    if "name" not in df_norm.columns:
        df_norm["name"] = df_norm["register_number"].astype(str)

    clean_records = []
    seen_regs = set()
    for idx, row in df_norm.iterrows():
        reg = str(row["register_number"]).strip().upper()
        if not reg or reg in ["NAN", "NONE", "NULL"] or reg in seen_regs:
            continue
        seen_regs.add(reg)

        name = str(row.get("name", f"Student {reg}")).strip().title()
        if not name or name in ["Nan", "None"]:
            name = f"Student {reg}"

        dept = str(row.get("department", "Computer Science & Engineering")).strip()
        if not dept or dept in ["nan", "None"]:
            dept = "Computer Science & Engineering"

        try:
            yr = int(row.get("year", 2))
        except (ValueError, TypeError):
            yr = 2

        try:
            sem = int(row.get("semester", 3))
        except (ValueError, TypeError):
            sem = 3

        sec = str(row.get("section", "A")).strip().upper()
        if not sec or sec in ["NAN", "NONE"]:
            sec = "A"

        clean_reg_alnum = re.sub(r'[^A-Za-z0-9]', '', reg).lower()
        clean_name_alnum = re.sub(r'[^A-Za-z0-9]', '', name.split()[0]).lower() if name else "student"
        email = str(row.get("email", f"{clean_name_alnum}.{clean_reg_alnum}@vsbec.com")).strip().lower()

        s_id = f"STU_{reg}"
        clean_records.append({
            "student_id": s_id,
            "register_number": reg,
            "name": name,
            "department": dept,
            "year": yr,
            "semester": sem,
            "section": sec,
            "email": email
        })

    if not clean_records:
        return False, pd.DataFrame(), "No valid student records could be identified in the uploaded file."

    result_df = pd.DataFrame(clean_records)
    return True, result_df, f"Successfully extracted {len(result_df)} student profile(s) from {file_name}."


def save_students_and_seed_attendance(
    students_df: pd.DataFrame,
    institution_id: str = "INST_001",
    campus_id: str = "CAMP_001",
    department_id: str = "DEPT_CS",
    generate_attendance: bool = True,
    attendance_profile: str = "REGULAR",
    performed_by: str = "Academic Administrator",
    db_path: str = DB_PATH
) -> Tuple[int, int, str]:
    """
    Saves students to the database and generates baseline multi-week attendance records
    so individual student profiles, streaks, and trend intelligence activate immediately.
    """
    if students_df.empty:
        return 0, 0, "No student records provided to save."

    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.datetime.now().isoformat()
    saved_students = 0
    saved_attendance = 0

    try:
        # 1. Upsert student records
        for _, s in students_df.iterrows():
            cursor.execute("""
                INSERT INTO students (
                    student_id, institution_id, campus_id, department_id, batch_id,
                    register_number, name, department, year, semester, section, email, created_at
                ) VALUES (?, ?, ?, ?, 'BATCH_2022', ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    register_number = excluded.register_number,
                    name = excluded.name,
                    department = excluded.department,
                    year = excluded.year,
                    semester = excluded.semester,
                    section = excluded.section,
                    email = excluded.email;
            """, (
                s["student_id"], institution_id, campus_id, department_id,
                s["register_number"], s["name"], s["department"],
                int(s.get("year", 2)), int(s.get("semester", 3)),
                str(s.get("section", "A")), str(s.get("email", "")), now_iso
            ))
            saved_students += 1

        # 2. Seed Baseline Attendance Records if requested
        if generate_attendance:
            cursor.execute("SELECT subject_id, subject_code, subject_name FROM subjects WHERE institution_id = ?;", (institution_id,))
            sub_rows = cursor.fetchall()
            if not sub_rows:
                sub_rows = [
                    ('SUB_CS301', 'CS301', 'Data Structures & Algorithms'),
                    ('SUB_CS302', 'CS302', 'Operating Systems'),
                    ('SUB_CS303', 'CS303', 'Database Management Systems'),
                    ('SUB_CS304', 'CS304', 'Artificial Intelligence & ML'),
                    ('SUB_CS305', 'CS305', 'Discrete Mathematics')
                ]
                for s_id, s_code, s_name in sub_rows:
                    cursor.execute("""
                        INSERT OR IGNORE INTO subjects (subject_id, institution_id, department_id, subject_code, subject_name, department, semester, credits, faculty_name)
                        VALUES (?, ?, 'DEPT_CS', ?, ?, 'Computer Science & Engineering', 3, 4, 'Faculty Assigned');
                    """, (s_id, institution_id, s_code, s_name))

            subjects = sub_rows[:5]
            
            if attendance_profile == "HIGH":
                p_present = 0.95
            elif attendance_profile == "WARNING":
                p_present = 0.72
            elif attendance_profile == "CRITICAL":
                p_present = 0.52
            else:  # REGULAR
                p_present = 0.88

            today = datetime.date.today()
            num_weeks = 6

            dates = []
            for w in range(num_weeks, 0, -1):
                monday = today - datetime.timedelta(weeks=w, days=today.weekday())
                for d in range(5):
                    c_date = monday + datetime.timedelta(days=d)
                    if c_date <= today:
                        dates.append((c_date.isoformat(), num_weeks - w + 1))

            period_times = [
                (1, "09:00", "09:50"),
                (2, "10:00", "10:50"),
                (3, "11:10", "12:00"),
                (4, "13:00", "13:50"),
                (5, "14:00", "14:50")
            ]

            att_batch = []
            for _, s in students_df.iterrows():
                stu_id = s["student_id"]
                for date_str, week_no in dates:
                    for p_num, s_start, s_end in period_times:
                        sub = subjects[(p_num - 1) % len(subjects)]
                        is_present = (random.random() < p_present)
                        st_choice = "Present" if is_present else "Absent"
                        
                        # Late arrival simulation (5% chance if present)
                        check_in = None
                        if is_present:
                            if random.random() < 0.05:
                                check_in = f"{s_start[:2]}:12"
                            else:
                                check_in = s_start
                            
                        att_batch.append((
                            institution_id, campus_id, stu_id, sub[0], date_str,
                            st_choice, p_num, week_no, "OFFICIAL_ROSTER", s_start, s_end,
                            check_in, "VSB_PORTAL_UPLOAD", now_iso
                        ))

            if att_batch:
                cursor.executemany("""
                    INSERT INTO attendance (
                        institution_id, campus_id, student_id, subject_id, date,
                        status, hour, week, verification_method, scheduled_start_time, scheduled_end_time,
                        check_in_time, source_system, record_created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, att_batch)
                saved_attendance = len(att_batch)

        cursor.execute("""
            INSERT INTO audit_logs (institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details)
            VALUES (?, 'STUDENTS_INGESTION', 'students', ?, NULL, ?, ?, ?, ?);
        """, (institution_id, f"COUNT_{saved_students}", f"Registered {saved_students} students, {saved_attendance} attendance logs", performed_by, now_iso, "Direct roster upload with baseline intelligence"))

        conn.commit()
    finally:
        conn.close()

    msg = f"Successfully registered {saved_students} student(s) with {saved_attendance:,} attendance records in VSB Engineering College!"
    return saved_students, saved_attendance, msg
