"""
Enterprise Multi-Tenant Database Management Module
Academic Attendance Pattern & Risk Analytics System
Supports multi-college and multi-campus management, campus infrastructure (buildings, floors, rooms),
room capacity validation, dynamic QR sessions, GPS geofence check-in logs, bulk import history,
audit logging, and role-based data isolation.
"""

import sqlite3
import os
import json
import datetime
import uuid
import pandas as pd
from typing import Optional, Dict, Any, List, Tuple
try:
    from utils.security import hash_password, verify_password, hash_token, generate_secure_token
except ImportError:
    from project1.utils.security import hash_password, verify_password, hash_token, generate_secure_token

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "attendance.db")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Returns a SQLite connection with foreign keys enabled, WAL journal mode, and timeout."""
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
    except Exception:
        pass
    return conn


def _migrate_table_columns(conn: sqlite3.Connection, table_name: str, required_columns: Dict[str, str]) -> None:
    """Safely adds missing columns to an existing table without data loss."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    existing_cols = {row[1]: row for row in cursor.fetchall()}
    
    for col_name, col_def in required_columns.items():
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def};")
                conn.commit()
            except Exception:
                pass


def _migrate_users_table_constraint(conn: sqlite3.Connection) -> None:
    """Safely relaxes restrictive legacy CHECK constraint on the users table."""
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users';")
    row = cursor.fetchone()
    if row and row[0] and "CHECK(role IN" in row[0]:
        try:
            cursor.execute("PRAGMA foreign_keys = OFF;")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users_migrated (
                    user_id TEXT PRIMARY KEY,
                    institution_id TEXT,
                    campus_id TEXT,
                    department_id TEXT,
                    username TEXT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    email TEXT,
                    role TEXT NOT NULL,
                    password_hash TEXT,
                    salt TEXT,
                    account_status TEXT DEFAULT 'ACTIVE',
                    failed_login_attempts INTEGER DEFAULT 0,
                    locked_until TEXT,
                    last_login_at TEXT,
                    updated_at TEXT,
                    must_change_password INTEGER DEFAULT 0,
                    student_id TEXT,
                    faculty_id TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT
                );
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO users_migrated (
                    user_id, institution_id, campus_id, department_id, username, full_name,
                    email, role, password_hash, salt, account_status, failed_login_attempts,
                    locked_until, last_login_at, updated_at, must_change_password, student_id,
                    faculty_id, is_active, created_at
                )
                SELECT user_id, institution_id, campus_id, department_id, username, full_name,
                       email, role, password_hash, salt, account_status, failed_login_attempts,
                       locked_until, last_login_at, updated_at, must_change_password, student_id,
                       faculty_id, is_active, created_at
                FROM users;
            """)
            cursor.execute("DROP TABLE users;")
            cursor.execute("ALTER TABLE users_migrated RENAME TO users;")
            cursor.execute("PRAGMA foreign_keys = ON;")
            conn.commit()
        except Exception:
            cursor.execute("PRAGMA foreign_keys = ON;")
            pass


def init_db(db_path: str = DB_PATH) -> None:
    """Initializes the multi-tenant database schema with institutions, campuses, rooms, and sessions."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    _migrate_users_table_constraint(conn)

    # 1. Institutions (Colleges & Universities)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS institutions (
            institution_id TEXT PRIMARY KEY,
            institution_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            type TEXT DEFAULT 'College',
            address TEXT,
            contact_email TEXT,
            created_at TEXT NOT NULL
        );
    """)

    # 2. Campuses / Branches
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campuses (
            campus_id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            campus_code TEXT NOT NULL,
            name TEXT NOT NULL,
            city TEXT,
            latitude REAL DEFAULT 12.9716,
            longitude REAL DEFAULT 77.5946,
            geofence_radius_meters REAL DEFAULT 300.0,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (institution_id) REFERENCES institutions(institution_id) ON DELETE CASCADE
        );
    """)

    # 3. Buildings & Blocks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS buildings (
            building_id TEXT PRIMARY KEY,
            campus_id TEXT NOT NULL,
            institution_id TEXT NOT NULL,
            building_name TEXT NOT NULL,
            building_code TEXT NOT NULL,
            total_floors INTEGER DEFAULT 4,
            FOREIGN KEY (campus_id) REFERENCES campuses(campus_id) ON DELETE CASCADE,
            FOREIGN KEY (institution_id) REFERENCES institutions(institution_id) ON DELETE CASCADE
        );
    """)

    # 4. Rooms (Classrooms, Laboratories, Seminar Halls, HOD Rooms, Libraries)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            building_id TEXT NOT NULL,
            campus_id TEXT NOT NULL,
            institution_id TEXT NOT NULL,
            room_number TEXT NOT NULL,
            room_name TEXT NOT NULL,
            floor_number INTEGER DEFAULT 1,
            room_type TEXT NOT NULL CHECK(room_type IN ('Classroom', 'Laboratory', 'Seminar Hall', 'Library', 'HOD Office', 'Faculty Room')),
            capacity INTEGER NOT NULL DEFAULT 60,
            dimension_sqft REAL DEFAULT 650.0,
            equipment_details TEXT DEFAULT 'Projector, Whiteboard, Wi-Fi',
            department_id TEXT,
            FOREIGN KEY (building_id) REFERENCES buildings(building_id) ON DELETE CASCADE,
            FOREIGN KEY (institution_id) REFERENCES institutions(institution_id) ON DELETE CASCADE
        );
    """)

    # 5. Departments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            department_id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            campus_id TEXT NOT NULL,
            department_code TEXT NOT NULL,
            name TEXT NOT NULL,
            hod_name TEXT,
            hod_email TEXT,
            hod_room_id TEXT,
            FOREIGN KEY (institution_id) REFERENCES institutions(institution_id) ON DELETE CASCADE,
            FOREIGN KEY (campus_id) REFERENCES campuses(campus_id) ON DELETE CASCADE
        );
    """)

    # 6. Academic Batches (Programmes, Years, Semesters, Sections)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS academic_batches (
            batch_id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            department_id TEXT NOT NULL,
            programme TEXT NOT NULL,
            academic_year INTEGER NOT NULL,
            semester INTEGER NOT NULL,
            section TEXT NOT NULL,
            FOREIGN KEY (institution_id) REFERENCES institutions(institution_id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE
        );
    """)

    # 7. Students Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            institution_id TEXT DEFAULT 'INST_001',
            campus_id TEXT DEFAULT 'CAMP_001',
            department_id TEXT,
            batch_id TEXT,
            register_number TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            year INTEGER NOT NULL,
            semester INTEGER DEFAULT 1,
            section TEXT NOT NULL,
            email TEXT,
            created_at TEXT
        );
    """)

    # 8. Subjects Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            subject_id TEXT PRIMARY KEY,
            institution_id TEXT DEFAULT 'INST_001',
            department_id TEXT,
            subject_code TEXT UNIQUE NOT NULL,
            subject_name TEXT NOT NULL,
            department TEXT,
            semester INTEGER DEFAULT 1,
            credits INTEGER DEFAULT 3,
            faculty_id TEXT,
            faculty_name TEXT
        );
    """)

    # 9. Timetable Sessions Table (with room allocations & capacity limits)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable_sessions (
            session_id TEXT PRIMARY KEY,
            institution_id TEXT DEFAULT 'INST_001',
            campus_id TEXT DEFAULT 'CAMP_001',
            department_id TEXT,
            department TEXT DEFAULT 'Computer Science & Engineering',
            subject_id TEXT NOT NULL,
            room_id TEXT,
            room_number TEXT DEFAULT '101',
            day_of_week TEXT NOT NULL,
            period_number INTEGER NOT NULL CHECK(period_number BETWEEN 1 AND 10),
            scheduled_start_time TEXT NOT NULL,
            scheduled_end_time TEXT NOT NULL,
            semester INTEGER DEFAULT 1,
            section TEXT DEFAULT 'A',
            expected_strength INTEGER DEFAULT 60,
            FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,
            FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE SET NULL
        );
    """)

    # 10. Dynamic QR Attendance Sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qr_attendance_sessions (
            qr_session_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            institution_id TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            room_id TEXT,
            token_hash TEXT NOT NULL,
            opened_by TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (session_id) REFERENCES timetable_sessions(session_id) ON DELETE CASCADE
        );
    """)

    # 11. GPS Geofence Check-In Logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gps_checkin_logs (
            checkin_id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            campus_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            distance_from_center_meters REAL NOT NULL,
            verification_status TEXT NOT NULL,
            device_info TEXT,
            timestamp TEXT NOT NULL,
            reviewed_by TEXT,
            review_status TEXT DEFAULT 'Auto-Verified'
        );
    """)

    # 12. Attendance Records Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution_id TEXT DEFAULT 'INST_001',
            campus_id TEXT DEFAULT 'CAMP_001',
            student_id TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL,
            hour INTEGER NOT NULL CHECK(hour BETWEEN 1 AND 10),
            week INTEGER NOT NULL CHECK(week >= 1),
            room_id TEXT,
            verification_method TEXT DEFAULT 'FILE_IMPORT',
            scheduled_start_time TEXT,
            scheduled_end_time TEXT,
            check_in_time TEXT,
            check_out_time TEXT,
            source_system TEXT DEFAULT 'CSV_IMPORT',
            session_id TEXT,
            record_created_at TEXT,
            updated_at TEXT,
            is_manually_corrected INTEGER DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
        );
    """)

    # 13. Bulk Import History Registry
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_history (
            import_id TEXT PRIMARY KEY,
            institution_id TEXT NOT NULL,
            data_category TEXT NOT NULL,
            file_name TEXT NOT NULL,
            total_rows INTEGER NOT NULL,
            valid_rows INTEGER NOT NULL,
            invalid_rows INTEGER NOT NULL,
            duplicate_rows INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('SUCCESS', 'FAILED', 'PARTIAL')),
            performed_by TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            error_report_json TEXT
        );
    """)

    # 14. Multi-Source Raw Events (Biometrics, Campus Turnstiles, QR)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS imported_source_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution_id TEXT DEFAULT 'INST_001',
            source_type TEXT NOT NULL,
            student_id TEXT NOT NULL,
            event_timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            location_or_device TEXT,
            raw_payload TEXT,
            batch_id TEXT,
            created_at TEXT NOT NULL
        );
    """)

    # 15. Reconciliation Discrepancy Cases
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reconciliation_cases (
            case_id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution_id TEXT DEFAULT 'INST_001',
            student_id TEXT NOT NULL,
            date TEXT NOT NULL,
            period_number INTEGER NOT NULL,
            subject_id TEXT,
            discrepancy_type TEXT NOT NULL,
            sources_involved TEXT NOT NULL,
            evidence_present TEXT,
            evidence_missing TEXT,
            confidence_score REAL DEFAULT 50.0,
            review_status TEXT DEFAULT 'Pending' CHECK(review_status IN ('Pending', 'Verified', 'Corrected', 'Dismissed')),
            reviewer_notes TEXT,
            resolved_by TEXT,
            resolved_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
        );
    """)

    # 16. Audit Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution_id TEXT DEFAULT 'INST_001',
            action_type TEXT NOT NULL,
            table_affected TEXT NOT NULL,
            record_id TEXT,
            old_value TEXT,
            new_value TEXT,
            performed_by TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            details TEXT
        );
    """)

    # 17. System Configuration & Threshold Settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT
        );
    """)

    # 18. Role-Based Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            institution_id TEXT,
            campus_id TEXT,
            department_id TEXT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL,
            password_hash TEXT,
            salt TEXT,
            account_status TEXT DEFAULT 'ACTIVE',
            failed_login_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            last_login_at TEXT,
            updated_at TEXT,
            must_change_password INTEGER DEFAULT 0,
            student_id TEXT,
            faculty_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );
    """)

    # 19. Authenticated Sessions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            session_token_hash TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            last_activity_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            is_remember_me INTEGER DEFAULT 0,
            ip_address TEXT,
            user_agent TEXT,
            is_revoked INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
    """)

    # 20. Password Reset Tokens Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token_hash TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
    """)

    # 21. Authentication & Security Audit Trail
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_audit_logs (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            event_type TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            details TEXT,
            timestamp TEXT NOT NULL
        );
    """)

    # Run safe column migrations for existing databases
    _migrate_table_columns(conn, "students", {
        "institution_id": "TEXT DEFAULT 'INST_001'",
        "campus_id": "TEXT DEFAULT 'CAMP_001'",
        "department_id": "TEXT",
        "batch_id": "TEXT",
        "semester": "INTEGER DEFAULT 1",
        "created_at": "TEXT"
    })
    _migrate_table_columns(conn, "subjects", {
        "institution_id": "TEXT DEFAULT 'INST_001'",
        "department_id": "TEXT",
        "department": "TEXT",
        "semester": "INTEGER DEFAULT 1",
        "credits": "INTEGER DEFAULT 3",
        "faculty_id": "TEXT"
    })
    _migrate_table_columns(conn, "attendance", {
        "institution_id": "TEXT DEFAULT 'INST_001'",
        "campus_id": "TEXT DEFAULT 'CAMP_001'",
        "room_id": "TEXT",
        "verification_method": "TEXT DEFAULT 'FILE_IMPORT'",
        "scheduled_start_time": "TEXT",
        "scheduled_end_time": "TEXT",
        "check_in_time": "TEXT",
        "check_out_time": "TEXT",
        "source_system": "TEXT DEFAULT 'CSV_IMPORT'",
        "session_id": "TEXT",
        "record_created_at": "TEXT",
        "updated_at": "TEXT",
        "is_manually_corrected": "INTEGER DEFAULT 0"
    })
    _migrate_table_columns(conn, "reconciliation_cases", {"institution_id": "TEXT DEFAULT 'INST_001'"})
    _migrate_table_columns(conn, "audit_logs", {"institution_id": "TEXT DEFAULT 'INST_001'"})
    _migrate_table_columns(conn, "timetable_sessions", {
        "institution_id": "TEXT DEFAULT 'INST_001'",
        "campus_id": "TEXT DEFAULT 'CAMP_001'",
        "department_id": "TEXT",
        "department": "TEXT DEFAULT 'Computer Science & Engineering'",
        "room_id": "TEXT",
        "room_number": "TEXT DEFAULT '101'",
        "semester": "INTEGER DEFAULT 1",
        "section": "TEXT DEFAULT 'A'",
        "expected_strength": "INTEGER DEFAULT 60"
    })
    _migrate_table_columns(conn, "rooms", {
        "building_id": "TEXT",
        "campus_id": "TEXT",
        "institution_id": "TEXT DEFAULT 'INST_001'",
        "floor_number": "INTEGER DEFAULT 1",
        "dimension_sqft": "REAL DEFAULT 650.0",
        "equipment_details": "TEXT",
        "department_id": "TEXT"
    })
    _migrate_table_columns(conn, "campuses", {
        "geofence_radius_meters": "REAL DEFAULT 300.0",
        "is_active": "INTEGER DEFAULT 1"
    })
    _migrate_table_columns(conn, "buildings", {
        "institution_id": "TEXT DEFAULT 'INST_001'",
        "total_floors": "INTEGER DEFAULT 4"
    })
    _migrate_table_columns(conn, "departments", {
        "institution_id": "TEXT DEFAULT 'INST_001'",
        "campus_id": "TEXT DEFAULT 'CAMP_001'",
        "hod_room_id": "TEXT"
    })
    _migrate_table_columns(conn, "users", {
        "institution_id": "TEXT",
        "campus_id": "TEXT",
        "department_id": "TEXT",
        "email": "TEXT",
        "role": "TEXT",
        "password_hash": "TEXT",
        "salt": "TEXT",
        "account_status": "TEXT DEFAULT 'ACTIVE'",
        "failed_login_attempts": "INTEGER DEFAULT 0",
        "locked_until": "TEXT",
        "last_login_at": "TEXT",
        "updated_at": "TEXT",
        "must_change_password": "INTEGER DEFAULT 0",
        "student_id": "TEXT",
        "faculty_id": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "created_at": "TEXT"
    })

    # Performance & Security Indexes (safely executed with fallback)
    perf_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_att_stu_date ON attendance(student_id, date);",
        "CREATE INDEX IF NOT EXISTS idx_att_inst ON attendance(institution_id);",
        "CREATE INDEX IF NOT EXISTS idx_rooms_bld ON rooms(building_id);",
        "CREATE INDEX IF NOT EXISTS idx_time_room ON timetable_sessions(room_id);",
        "CREATE INDEX IF NOT EXISTS idx_qr_sess_token ON qr_attendance_sessions(token_hash);",
        "CREATE INDEX IF NOT EXISTS idx_gps_user ON gps_checkin_logs(user_id, timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_auth_token ON auth_sessions(session_token_hash);",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
        "CREATE INDEX IF NOT EXISTS idx_reset_token ON password_reset_tokens(token_hash);",
        "CREATE INDEX IF NOT EXISTS idx_auth_audit_time ON auth_audit_logs(timestamp);"
    ]
    for idx_sql in perf_indexes:
        try:
            cursor.execute(idx_sql)
        except Exception:
            pass

    # Seed Baseline Multi-College Infrastructure
    cursor.execute("""
        INSERT OR IGNORE INTO institutions (institution_id, institution_code, name, type, address, contact_email, created_at)
        VALUES 
            ('INST_001', 'VSBEC', 'VSB Engineering College, Karur', 'Engineering College', 'NH-67, Covai Road, Karudayampalayam, Karur, Tamil Nadu 639111', 'admin@vsbec.com', datetime('now')),
            ('INST_002', 'AGBRC', 'Apex Global Business & Research College', 'Independent College', 'Downtown Knowledge Park', 'contact@apex.edu', datetime('now'));
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO campuses (campus_id, institution_id, campus_code, name, city, latitude, longitude, geofence_radius_meters, is_active)
        VALUES 
            ('CAMP_001', 'INST_001', 'CAMP_VSB_MAIN', 'VSB Engineering College - Main Campus', 'Karur', 10.954850, 77.954630, 350.0, 1),
            ('CAMP_002', 'INST_001', 'CAMP_VSB_TECH', 'VSB Technical Campus', 'Coimbatore', 10.835000, 77.012000, 300.0, 1),
            ('CAMP_003', 'INST_002', 'CAMP_APEX_MAIN', 'Apex Central Campus', 'Chennai', 13.0827, 80.2707, 200.0, 1);
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO buildings (building_id, campus_id, institution_id, building_name, building_code, total_floors)
        VALUES 
            ('BLD_001', 'CAMP_001', 'INST_001', 'Alan Turing Block', 'ATB', 4),
            ('BLD_002', 'CAMP_001', 'INST_001', 'Ada Lovelace Innovation Hall', 'ALH', 3),
            ('BLD_003', 'CAMP_002', 'INST_001', 'Ramanujan Science Tower', 'RST', 5),
            ('BLD_004', 'CAMP_003', 'INST_002', 'Corporate Management Tower', 'CMT', 6);
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO rooms (room_id, building_id, campus_id, institution_id, room_number, room_name, floor_number, room_type, capacity, dimension_sqft, equipment_details)
        VALUES 
            ('RM_101', 'BLD_001', 'CAMP_001', 'INST_001', '101', 'Advanced AI Lecture Theater', 1, 'Classroom', 70, 750.0, 'Dual Laser Projector, Smart Podium, 5G Wi-Fi'),
            ('RM_102', 'BLD_001', 'CAMP_001', 'INST_001', '102', 'Systems & Computing Lab', 1, 'Laboratory', 40, 900.0, '40 High-End Workstations, Gigabit LAN'),
            ('RM_201', 'BLD_001', 'CAMP_001', 'INST_001', '201', 'Computer Science HOD Office', 2, 'HOD Office', 10, 350.0, 'Executive Board Table, File Archives'),
            ('RM_301', 'BLD_002', 'CAMP_001', 'INST_001', '301', 'Kavitha Memorial Seminar Hall', 3, 'Seminar Hall', 150, 1800.0, 'Dolby Sound System, Wireless Mics, Tiered Seating'),
            ('RM_401', 'BLD_004', 'CAMP_003', 'INST_002', '401', 'Apex Executive MBA Classroom', 4, 'Classroom', 50, 600.0, 'Smart Interactive Screen, Air Conditioning');
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO departments (department_id, institution_id, campus_id, department_code, name, hod_name, hod_email, hod_room_id)
        VALUES 
            ('DEPT_CS', 'INST_001', 'CAMP_001', 'CSE', 'Computer Science & Engineering', 'Dr. Rajesh Sundaram', 'hod.cs@niet.edu', 'RM_201'),
            ('DEPT_IT', 'INST_001', 'CAMP_001', 'IT', 'Information Technology', 'Dr. Priya Venkatesh', 'hod.it@niet.edu', 'RM_101'),
            ('DEPT_MGMT', 'INST_002', 'CAMP_003', 'MGMT', 'Management & Leadership', 'Prof. Arvind Menon', 'hod.mgmt@apex.edu', 'RM_401');
    """)

    # Seed or synchronize default enterprise users with secure hashed passwords
    default_accounts = [
        {
            "user_id": "USR_ADMIN",
            "institution_id": "INST_001",
            "campus_id": "CAMP_001",
            "department_id": None,
            "username": "admin",
            "full_name": "Dean of Academic Affairs",
            "email": "admin@nexus.edu",
            "role": "Administrator",
            "password": "NexusAdmin@2026!",
            "student_id": None,
            "faculty_id": None
        },
        {
            "user_id": "USR_COORDINATOR",
            "institution_id": "INST_001",
            "campus_id": "CAMP_001",
            "department_id": "DEPT_CS",
            "username": "coordinator",
            "full_name": "Dr. Rajesh Sundaram (Coordinator)",
            "email": "coordinator@nexus.edu",
            "role": "Academic Coordinator",
            "password": "NexusCoord@2026!",
            "student_id": None,
            "faculty_id": None
        },
        {
            "user_id": "USR_FACULTY_1",
            "institution_id": "INST_001",
            "campus_id": "CAMP_001",
            "department_id": "DEPT_CS",
            "username": "prof_sharma",
            "full_name": "Prof. Ananya Sharma",
            "email": "faculty.sharma@nexus.edu",
            "role": "Faculty",
            "password": "NexusFaculty@2026!",
            "student_id": None,
            "faculty_id": "FAC_CS_01"
        },
        {
            "user_id": "USR_STUDENT_1",
            "institution_id": "INST_001",
            "campus_id": "CAMP_001",
            "department_id": "DEPT_CS",
            "username": "student_aarav",
            "full_name": "Aarav Gupta",
            "email": "student.aarav@nexus.edu",
            "role": "Student",
            "password": "NexusStudent@2026!",
            "student_id": "STU_1001",
            "faculty_id": None
        }
    ]

    for acc in default_accounts:
        p_hash, p_salt = hash_password(acc["password"])
        cursor.execute("""
            INSERT INTO users (
                user_id, institution_id, campus_id, department_id, username, full_name, email,
                role, password_hash, salt, account_status, failed_login_attempts, is_active,
                student_id, faculty_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 0, 1, ?, ?, datetime('now'))
            ON CONFLICT(username) DO UPDATE SET
                full_name = excluded.full_name,
                email = excluded.email,
                role = excluded.role,
                password_hash = COALESCE(users.password_hash, excluded.password_hash),
                salt = COALESCE(users.salt, excluded.salt),
                student_id = COALESCE(users.student_id, excluded.student_id),
                faculty_id = COALESCE(users.faculty_id, excluded.faculty_id);
        """, (
            acc["user_id"], acc["institution_id"], acc["campus_id"], acc["department_id"],
            acc["username"], acc["full_name"], acc["email"], acc["role"], p_hash, p_salt,
            acc["student_id"], acc["faculty_id"]
        ))

    # Also backfill password hashes for any legacy users where password_hash is NULL
    cursor.execute("SELECT user_id, username, role FROM users WHERE password_hash IS NULL;")
    legacy_rows = cursor.fetchall()
    for row in legacy_rows:
        u_id, u_name, u_role = row[0], row[1], row[2]
        fallback_pw = "NexusAdmin@2026!" if ("admin" in u_role.lower() or "super" in u_role.lower()) else ("NexusFaculty@2026!" if "faculty" in u_role.lower() else "NexusCoord@2026!")
        f_hash, f_salt = hash_password(fallback_pw)
        cursor.execute("UPDATE users SET password_hash = ?, salt = ?, account_status = 'ACTIVE' WHERE user_id = ?;", (f_hash, f_salt, u_id))



    # Seed baseline system settings
    cursor.execute("""
        INSERT OR IGNORE INTO system_settings (setting_key, setting_value, description, updated_at)
        VALUES 
            ('mandatory_attendance_pct', '75.0', 'Statutory institutional minimum attendance requirement (%)', datetime('now')),
            ('warning_attendance_pct', '80.0', 'Proactive early warning benchmark threshold (%)', datetime('now')),
            ('critical_risk_score', '80', 'Cutoff score for classification into Critical Risk Tier', datetime('now')),
            ('late_arrival_tolerance_mins', '10', 'Grace period in minutes after scheduled start before marked Late', datetime('now')),
            ('excused_absence_rule', 'exclude_from_total', 'Policy for excused absence: exclude_from_total, count_as_attended, count_as_neutral', datetime('now')),
            ('active_institution_id', 'INST_001', 'Default active tenant institution identifier', datetime('now'));
    """)

    conn.commit()
    conn.close()


def get_setting(key: str, default: Any = None, db_path: str = DB_PATH) -> Any:
    """Fetches a system configuration setting."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row is not None:
        val = row[0]
        try:
            if "." in val:
                return float(val)
            return int(val)
        except ValueError:
            return val
    return default


def set_setting(key: str, value: Any, description: Optional[str] = None, db_path: str = DB_PATH) -> None:
    """Updates or sets a system configuration setting with timestamp."""
    conn = get_connection(db_path)
    now = datetime.datetime.now().isoformat()
    conn.execute("""
        INSERT INTO system_settings (setting_key, setting_value, description, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(setting_key) DO UPDATE SET
            setting_value = excluded.setting_value,
            description = COALESCE(excluded.description, system_settings.description),
            updated_at = excluded.updated_at;
    """, (key, str(value), description, now))
    conn.commit()
    conn.close()


def log_audit_action(
    action_type: str,
    table_affected: str,
    record_id: Optional[str],
    old_value: Optional[str],
    new_value: Optional[str],
    performed_by: str,
    details: Optional[str] = None,
    institution_id: str = "INST_001",
    db_path: str = DB_PATH
) -> int:
    """Appends an immutable audit log entry."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO audit_logs (institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, now, details))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def get_audit_logs(institution_id: Optional[str] = None, limit: int = 100, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves recent audit logs with tenant filtering."""
    conn = get_connection(db_path)
    if institution_id:
        query = "SELECT log_id, institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details FROM audit_logs WHERE institution_id = ? ORDER BY timestamp DESC LIMIT ?"
        df = pd.read_sql_query(query, conn, params=[institution_id, limit])
    else:
        query = "SELECT log_id, institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details FROM audit_logs ORDER BY timestamp DESC LIMIT ?"
        df = pd.read_sql_query(query, conn, params=[limit])
    conn.close()
    return df


def reset_database(db_path: str = DB_PATH) -> None:
    """Drops and re-initializes all tables cleanly."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    tables = [
        "attendance", "imported_source_events", "reconciliation_cases", 
        "audit_logs", "qr_attendance_sessions", "gps_checkin_logs", "import_history",
        "timetable_sessions", "subjects", "students", "academic_batches",
        "departments", "rooms", "buildings", "campuses", "institutions", 
        "system_settings", "auth_sessions", "password_reset_tokens", "auth_audit_logs", "users"
    ]
    for tbl in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {tbl};")
    conn.commit()
    conn.close()
    init_db(db_path)


def clear_attendance_records(institution_id: Optional[str] = None, db_path: str = DB_PATH) -> int:
    """Purges attendance, reconciliation cases, and raw events while retaining institutional structure."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    if institution_id:
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE institution_id = ?;", (institution_id,))
        count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM attendance WHERE institution_id = ?;", (institution_id,))
        cursor.execute("DELETE FROM imported_source_events WHERE institution_id = ?;", (institution_id,))
        cursor.execute("DELETE FROM reconciliation_cases WHERE institution_id = ?;", (institution_id,))
        cursor.execute("DELETE FROM qr_attendance_sessions WHERE institution_id = ?;", (institution_id,))
        cursor.execute("DELETE FROM gps_checkin_logs WHERE institution_id = ?;", (institution_id,))
    else:
        cursor.execute("SELECT COUNT(*) FROM attendance;")
        count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM attendance;")
        cursor.execute("DELETE FROM imported_source_events;")
        cursor.execute("DELETE FROM reconciliation_cases;")
        cursor.execute("DELETE FROM qr_attendance_sessions;")
        cursor.execute("DELETE FROM gps_checkin_logs;")
    conn.commit()
    conn.close()
    return count


# Institutional & Infrastructure Query APIs
def get_all_institutions(db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves all registered institutions."""
    conn = get_connection(db_path)
    df = pd.read_sql_query("SELECT institution_id, institution_code, name, type, address, contact_email, created_at FROM institutions ORDER BY name ASC", conn)
    conn.close()
    return df


def get_campuses(institution_id: Optional[str] = None, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves campuses for a specific institution or all campuses."""
    conn = get_connection(db_path)
    if institution_id:
        df = pd.read_sql_query("SELECT campus_id, institution_id, campus_code, name, city, latitude, longitude, geofence_radius_meters, is_active FROM campuses WHERE institution_id = ? ORDER BY name ASC", conn, params=[institution_id])
    else:
        df = pd.read_sql_query("SELECT campus_id, institution_id, campus_code, name, city, latitude, longitude, geofence_radius_meters, is_active FROM campuses ORDER BY name ASC", conn)
    conn.close()
    return df


def get_buildings(campus_id: Optional[str] = None, institution_id: Optional[str] = None, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves buildings filtered by campus or institution."""
    conn = get_connection(db_path)
    query = "SELECT building_id, campus_id, institution_id, building_name, building_code, total_floors FROM buildings WHERE 1=1"
    params = []
    if campus_id:
        query += " AND campus_id = ?"
        params.append(campus_id)
    if institution_id:
        query += " AND institution_id = ?"
        params.append(institution_id)
    df = pd.read_sql_query(query + " ORDER BY building_name ASC", conn, params=params)
    conn.close()
    return df


def get_rooms(building_id: Optional[str] = None, institution_id: Optional[str] = None, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves rooms with capacity, dimensions, and equipment."""
    conn = get_connection(db_path)
    query = """
        SELECT r.room_id, r.building_id, b.building_name, r.campus_id, r.institution_id, 
               r.room_number, r.room_name, r.floor_number, r.room_type, r.capacity, 
               r.dimension_sqft, r.equipment_details, r.department_id
        FROM rooms r
        JOIN buildings b ON r.building_id = b.building_id
        WHERE 1=1
    """
    params = []
    if building_id:
        query += " AND r.building_id = ?"
        params.append(building_id)
    if institution_id:
        query += " AND r.institution_id = ?"
        params.append(institution_id)
    df = pd.read_sql_query(query + " ORDER BY r.room_number ASC", conn, params=params)
    conn.close()
    return df


def get_departments(institution_id: Optional[str] = None, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves departments scoped by institution."""
    conn = get_connection(db_path)
    if institution_id:
        df = pd.read_sql_query("SELECT department_id, institution_id, campus_id, department_code, name, hod_name, hod_email, hod_room_id FROM departments WHERE institution_id = ? ORDER BY name ASC", conn, params=[institution_id])
    else:
        df = pd.read_sql_query("SELECT department_id, institution_id, campus_id, department_code, name, hod_name, hod_email, hod_room_id FROM departments ORDER BY name ASC", conn)
    conn.close()
    return df


def get_all_students(institution_id: Optional[str] = None, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves students scoped by institution."""
    conn = get_connection(db_path)
    if institution_id:
        query = "SELECT student_id, institution_id, campus_id, register_number, name, department, year, semester, section, email FROM students WHERE institution_id = ? ORDER BY register_number ASC"
        df = pd.read_sql_query(query, conn, params=[institution_id])
    else:
        query = "SELECT student_id, institution_id, campus_id, register_number, name, department, year, semester, section, email FROM students ORDER BY register_number ASC"
        df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_all_subjects(institution_id: Optional[str] = None, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves subjects scoped by institution."""
    conn = get_connection(db_path)
    if institution_id:
        query = "SELECT subject_id, institution_id, subject_code, subject_name, department, semester, credits, faculty_name FROM subjects WHERE institution_id = ? ORDER BY subject_code ASC"
        df = pd.read_sql_query(query, conn, params=[institution_id])
    else:
        query = "SELECT subject_id, institution_id, subject_code, subject_name, department, semester, credits, faculty_name FROM subjects ORDER BY subject_code ASC"
        df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_timetable_sessions(institution_id: Optional[str] = None, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves scheduled class timetable sessions joined with room capacities and subject metadata."""
    conn = get_connection(db_path)
    query = """
        SELECT 
            t.session_id,
            t.institution_id,
            t.campus_id,
            t.subject_id,
            sub.subject_code,
            sub.subject_name,
            sub.faculty_name,
            t.room_id,
            r.room_number,
            r.room_type,
            r.capacity AS room_capacity,
            t.day_of_week,
            t.period_number,
            t.scheduled_start_time,
            t.scheduled_end_time,
            t.semester,
            t.section,
            t.expected_strength,
            (t.expected_strength > r.capacity) AS has_capacity_breach
        FROM timetable_sessions t
        LEFT JOIN subjects sub ON t.subject_id = sub.subject_id
        LEFT JOIN rooms r ON t.room_id = r.room_id
        WHERE 1=1
    """
    params = []
    if institution_id:
        query += " AND t.institution_id = ?"
        params.append(institution_id)
    df = pd.read_sql_query(query + " ORDER BY t.day_of_week ASC, t.period_number ASC", conn, params=params)
    conn.close()
    return df


def get_full_attendance_dataset(db_path: str = DB_PATH, filters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Retrieves merged attendance records with student, subject, and room details,
    enforcing institutional tenant isolation and optional scope filters.
    """
    conn = get_connection(db_path)
    query = """
        SELECT 
            a.attendance_id,
            a.institution_id,
            a.campus_id,
            a.student_id,
            s.register_number,
            s.name AS student_name,
            s.department,
            s.year,
            s.semester,
            s.section,
            a.subject_id,
            sub.subject_code,
            sub.subject_name,
            sub.faculty_name,
            a.room_id,
            r.room_number,
            a.date,
            a.status,
            a.hour,
            a.week,
            a.verification_method,
            a.scheduled_start_time,
            a.scheduled_end_time,
            a.check_in_time,
            a.check_out_time,
            a.source_system,
            a.is_manually_corrected,
            a.record_created_at
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        JOIN subjects sub ON a.subject_id = sub.subject_id
        LEFT JOIN rooms r ON a.room_id = r.room_id
        WHERE 1=1
    """
    params = []

    if filters:
        if filters.get("institution_id") and filters["institution_id"] != "All":
            query += " AND a.institution_id = ?"
            params.append(filters["institution_id"])
        if filters.get("campus_id") and filters["campus_id"] != "All":
            query += " AND a.campus_id = ?"
            params.append(filters["campus_id"])
        if filters.get("department") and filters["department"] != "All":
            query += " AND s.department = ?"
            params.append(filters["department"])
        if filters.get("year") and filters["year"] != "All":
            query += " AND s.year = ?"
            params.append(int(filters["year"]))
        if filters.get("semester") and filters["semester"] != "All":
            query += " AND s.semester = ?"
            params.append(int(filters["semester"]))
        if filters.get("section") and filters["section"] != "All":
            query += " AND s.section = ?"
            params.append(filters["section"])
        if filters.get("subject_id") and filters["subject_id"] != "All":
            query += " AND a.subject_id = ?"
            params.append(filters["subject_id"])
        if filters.get("start_date"):
            query += " AND a.date >= ?"
            params.append(str(filters["start_date"]))
        if filters.get("end_date"):
            query += " AND a.date <= ?"
            params.append(str(filters["end_date"]))
        if filters.get("student_id"):
            query += " AND a.student_id = ?"
            params.append(filters["student_id"])

    query += " ORDER BY a.date ASC, a.hour ASC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_student_attendance(student_id: str, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves chronological attendance records for a specific student."""
    return get_full_attendance_dataset(db_path=db_path, filters={"student_id": student_id})


def insert_students_bulk(students_df: pd.DataFrame, db_path: str = DB_PATH) -> int:
    """Bulk inserts or appends student records."""
    conn = get_connection(db_path)
    students_df.to_sql("students", conn, if_exists="append", index=False)
    conn.close()
    return len(students_df)


def insert_subjects_bulk(subjects_df: pd.DataFrame, db_path: str = DB_PATH) -> int:
    """Bulk inserts or appends subject records."""
    conn = get_connection(db_path)
    subjects_df.to_sql("subjects", conn, if_exists="append", index=False)
    conn.close()
    return len(subjects_df)


def insert_attendance_bulk(attendance_df: pd.DataFrame, db_path: str = DB_PATH) -> int:
    """Bulk inserts attendance records."""
    conn = get_connection(db_path)
    attendance_df.to_sql("attendance", conn, if_exists="append", index=False)
    conn.close()
    return len(attendance_df)


def record_manual_attendance_correction(
    attendance_id: int,
    new_status: str,
    reason: str,
    performed_by: str,
    institution_id: str = "INST_001",
    db_path: str = DB_PATH
) -> bool:
    """Updates an attendance status manually and writes an immutable audit record."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, date, hour, status FROM attendance WHERE attendance_id = ?", (attendance_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    old_status = row[3]
    stu_id = row[0]
    now = datetime.datetime.now().isoformat()

    cursor.execute("""
        UPDATE attendance 
        SET status = ?, is_manually_corrected = 1, updated_at = ?
        WHERE attendance_id = ?;
    """, (new_status, now, attendance_id))

    cursor.execute("""
        INSERT INTO audit_logs (institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        institution_id, "MANUAL_CORRECTION", "attendance", str(attendance_id),
        old_status, new_status, performed_by, now,
        f"Student: {stu_id}, Date: {row[1]}, Hour: {row[2]}, Reason: {reason}"
    ))

    conn.commit()
    conn.close()
    return True


def record_import_history(
    import_id: str,
    institution_id: str,
    data_category: str,
    file_name: str,
    total_rows: int,
    valid_rows: int,
    invalid_rows: int,
    duplicate_rows: int,
    status: str,
    performed_by: str,
    error_report_json: Optional[str] = None,
    db_path: str = DB_PATH
) -> None:
    """Records a permanent record of bulk upload executions."""
    conn = get_connection(db_path)
    now = datetime.datetime.now().isoformat()
    conn.execute("""
        INSERT INTO import_history (
            import_id, institution_id, data_category, file_name, total_rows,
            valid_rows, invalid_rows, duplicate_rows, status, performed_by, timestamp, error_report_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (import_id, institution_id, data_category, file_name, total_rows, valid_rows, invalid_rows, duplicate_rows, status, performed_by, now, error_report_json))
    conn.commit()
    conn.close()


def get_import_history(institution_id: Optional[str] = None, limit: int = 50, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves recent import records."""
    conn = get_connection(db_path)
    if institution_id:
        query = "SELECT import_id, institution_id, data_category, file_name, total_rows, valid_rows, invalid_rows, duplicate_rows, status, performed_by, timestamp FROM import_history WHERE institution_id = ? ORDER BY timestamp DESC LIMIT ?"
        df = pd.read_sql_query(query, conn, params=[institution_id, limit])
    else:
        query = "SELECT import_id, institution_id, data_category, file_name, total_rows, valid_rows, invalid_rows, duplicate_rows, status, performed_by, timestamp FROM import_history ORDER BY timestamp DESC LIMIT ?"
        df = pd.read_sql_query(query, conn, params=[limit])
    conn.close()
    return df


def get_database_summary(institution_id: Optional[str] = None, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Returns total counts for institutions, campuses, rooms, students, and attendance."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM institutions;")
    total_institutions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM campuses;")
    total_campuses = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM rooms;")
    total_rooms = cursor.fetchone()[0]

    if institution_id:
        cursor.execute("SELECT COUNT(*) FROM students WHERE institution_id = ?;", (institution_id,))
        total_students = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM subjects WHERE institution_id = ?;", (institution_id,))
        total_subjects = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*), MIN(date), MAX(date), MAX(week) FROM attendance WHERE institution_id = ?;", (institution_id,))
        att_row = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM reconciliation_cases WHERE institution_id = ? AND review_status = 'Pending';", (institution_id,))
        pending_cases = cursor.fetchone()[0]
    else:
        cursor.execute("SELECT COUNT(*) FROM students;")
        total_students = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM subjects;")
        total_subjects = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*), MIN(date), MAX(date), MAX(week) FROM attendance;")
        att_row = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM reconciliation_cases WHERE review_status = 'Pending';")
        pending_cases = cursor.fetchone()[0]
    
    total_attendance = att_row[0] if att_row else 0
    min_date = att_row[1] if att_row else None
    max_date = att_row[2] if att_row else None
    max_week = att_row[3] if att_row else 0

    # Room capacity breaches in timetable
    cursor.execute("""
        SELECT COUNT(*) FROM timetable_sessions t
        JOIN rooms r ON t.room_id = r.room_id
        WHERE t.expected_strength > r.capacity;
    """)
    capacity_breaches = cursor.fetchone()[0]
    
    conn.close()
    return {
        "total_institutions": total_institutions,
        "total_campuses": total_campuses,
        "total_rooms": total_rooms,
        "total_students": total_students,
        "total_subjects": total_subjects,
        "total_attendance_records": total_attendance,
        "date_range": (min_date, max_date),
        "total_weeks": max_week or 0,
        "pending_reconciliations": pending_cases,
        "capacity_breaches": capacity_breaches
    }


# ==============================================================================
# Dynamic QR Attendance Sessions
# ==============================================================================

def create_qr_session(
    session_id: str,
    institution_id: str,
    subject_id: str,
    room_id: Optional[str],
    token_hash: str,
    opened_by: str,
    validity_seconds: int = 120,
    db_path: str = DB_PATH
) -> str:
    """Creates a short-lived dynamic QR attendance session with cryptographic token hash."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        # Ensure session exists in timetable_sessions so foreign key constraint is satisfied
        cursor.execute("SELECT 1 FROM timetable_sessions WHERE session_id = ?;", (session_id,))
        if not cursor.fetchone():
            # Validate or fallback subject_id to an existing subject in DB
            actual_sub = subject_id
            cursor.execute("SELECT subject_id FROM subjects WHERE subject_id = ?;", (actual_sub,))
            if not cursor.fetchone():
                cursor.execute("SELECT subject_id FROM subjects WHERE institution_id = ? LIMIT 1;", (institution_id,))
                sub_row = cursor.fetchone()
                if sub_row:
                    actual_sub = sub_row[0]
                else:
                    actual_sub = "SUB_CS301"
                    cursor.execute("""
                        INSERT OR IGNORE INTO subjects (subject_id, institution_id, subject_code, subject_name)
                        VALUES (?, ?, 'CS301', 'General Computer Science Lecture');
                    """, (actual_sub, institution_id))

            # Validate or fallback room_id
            actual_room = room_id
            if actual_room:
                cursor.execute("SELECT 1 FROM rooms WHERE room_id = ?;", (actual_room,))
                if not cursor.fetchone():
                    actual_room = None

            cursor.execute("SELECT campus_id FROM campuses WHERE institution_id = ? LIMIT 1;", (institution_id,))
            c_row = cursor.fetchone()
            actual_campus = c_row[0] if c_row else "CAMP_001"

            cursor.execute("SELECT department_id FROM departments WHERE institution_id = ? LIMIT 1;", (institution_id,))
            d_row = cursor.fetchone()
            actual_dept = d_row[0] if d_row else "DEPT_CS"

            cursor.execute("""
                INSERT OR IGNORE INTO timetable_sessions (
                    session_id, institution_id, campus_id, department_id, department, subject_id, room_id, room_number,
                    day_of_week, period_number, scheduled_start_time, scheduled_end_time,
                    semester, section, expected_strength
                ) VALUES (?, ?, ?, ?, 'Computer Science & Engineering', ?, ?, '101', ?, 1, '09:00', '10:00', 1, 'A', 60);
            """, (session_id, institution_id, actual_campus, actual_dept, actual_sub, actual_room, datetime.datetime.now().strftime("%A")))

            subject_id = actual_sub
            room_id = actual_room

        qr_session_id = f"QRS_{uuid.uuid4().hex[:10].upper()}"
        now_dt = datetime.datetime.now()
        opened_at = now_dt.isoformat()
        expires_at = (now_dt + datetime.timedelta(seconds=validity_seconds)).isoformat()

        cursor.execute("""
            INSERT INTO qr_attendance_sessions (
                qr_session_id, session_id, institution_id, subject_id, room_id,
                token_hash, opened_by, opened_at, expires_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
        """, (qr_session_id, session_id, institution_id, subject_id, room_id, token_hash, opened_by, opened_at, expires_at))

        cursor.execute("""
            INSERT INTO audit_logs (institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details)
            VALUES (?, 'QR_SESSION_OPEN', 'qr_attendance_sessions', ?, NULL, ?, ?, ?, ?);
        """, (institution_id, qr_session_id, expires_at, opened_by, opened_at, f"Subject: {subject_id}, Room: {room_id}, Validity: {validity_seconds}s"))

        conn.commit()
        return qr_session_id
    finally:
        conn.close()


def close_qr_session(qr_session_id: str, closed_by: str = "Instructor", db_path: str = DB_PATH) -> bool:
    """Closes an active QR attendance session."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        now = datetime.datetime.now().isoformat()
        cursor.execute("""
            UPDATE qr_attendance_sessions
            SET is_active = 0
            WHERE qr_session_id = ?;
        """, (qr_session_id,))
        success = cursor.rowcount > 0
        if success:
            cursor.execute("""
                INSERT INTO audit_logs (institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details)
                VALUES ('INST_001', 'QR_SESSION_CLOSE', 'qr_attendance_sessions', ?, '1', '0', ?, ?, 'Session closed by operator');
            """, (qr_session_id, closed_by, now))
        conn.commit()
        return success
    finally:
        conn.close()


def get_active_qr_session(qr_session_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves metadata of a QR session and auto-expires if time is past expires_at."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT q.qr_session_id, q.session_id, q.institution_id, q.subject_id, q.room_id,
                   q.token_hash, q.opened_by, q.opened_at, q.expires_at, q.is_active,
                   sub.subject_code, sub.subject_name, r.room_number, r.capacity
            FROM qr_attendance_sessions q
            LEFT JOIN subjects sub ON q.subject_id = sub.subject_id
            LEFT JOIN rooms r ON q.room_id = r.room_id
            WHERE q.qr_session_id = ?;
        """, (qr_session_id,))
        row = cursor.fetchone()
        if not row:
            return None

        now_dt = datetime.datetime.now()
        expires_dt = datetime.datetime.fromisoformat(row[8])
        is_active = row[9]

        if is_active and now_dt > expires_dt:
            cursor.execute("UPDATE qr_attendance_sessions SET is_active = 0 WHERE qr_session_id = ?;", (qr_session_id,))
            conn.commit()
            is_active = 0

        return {
            "qr_session_id": row[0],
            "session_id": row[1],
            "institution_id": row[2],
            "subject_id": row[3],
            "room_id": row[4],
            "token_hash": row[5],
            "opened_by": row[6],
            "opened_at": row[7],
            "expires_at": row[8],
            "is_active": bool(is_active),
            "is_expired": now_dt > expires_dt,
            "subject_code": row[10] or row[3],
            "subject_name": row[11] or "Class Session",
            "room_number": row[12] or "N/A",
            "room_capacity": row[13] or 60,
            "remaining_seconds": max(0, int((expires_dt - now_dt).total_seconds()))
        }
    finally:
        conn.close()


def get_qr_sessions(institution_id: Optional[str] = None, active_only: bool = False, db_path: str = DB_PATH) -> pd.DataFrame:
    """Returns list of QR attendance sessions."""
    conn = get_connection(db_path)
    try:
        query = """
            SELECT q.qr_session_id, q.session_id, q.institution_id, q.subject_id,
                   sub.subject_code, sub.subject_name, q.room_id, r.room_number,
                   q.opened_by, q.opened_at, q.expires_at, q.is_active,
                   (SELECT COUNT(*) FROM attendance a WHERE a.session_id = q.session_id AND a.verification_method = 'DYNAMIC_QR') AS attendee_count
            FROM qr_attendance_sessions q
            LEFT JOIN subjects sub ON q.subject_id = sub.subject_id
            LEFT JOIN rooms r ON q.room_id = r.room_id
            WHERE 1=1
        """
        params = []
        if institution_id:
            query += " AND q.institution_id = ?"
            params.append(institution_id)
        if active_only:
            query += " AND q.is_active = 1"
        query += " ORDER BY q.opened_at DESC LIMIT 50;"
        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        conn.close()


def submit_qr_attendance(
    qr_session_id: str,
    student_identifier: str,
    token_submitted: str,
    db_path: str = DB_PATH
) -> Tuple[bool, str]:
    """
    Validates a student QR attendance submission against cryptographic token,
    session expiry, student enrollment, and duplicate check-in constraints.
    """
    session = get_active_qr_session(qr_session_id, db_path=db_path)
    if not session:
        return False, "Invalid or non-existent QR attendance session."

    if not session["is_active"] or session["is_expired"]:
        return False, "This QR attendance session has expired or has been closed by the instructor."

    # Validate token hash match
    import hashlib
    submitted_token_clean = token_submitted.strip()
    calculated_hash = hashlib.sha256(submitted_token_clean.encode("utf-8")).hexdigest()
    if submitted_token_clean != session["token_hash"] and calculated_hash != session["token_hash"]:
        return False, "Security verification failed: QR token signature mismatch or corrupted code."

    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        # Verify student exists in current institution
        clean_id = student_identifier.strip().upper()
        cursor.execute("""
            SELECT student_id, register_number, name, department, year, semester, section, institution_id, campus_id
            FROM students
            WHERE (UPPER(student_id) = ? OR UPPER(register_number) = ?) AND institution_id = ?;
        """, (clean_id, clean_id, session["institution_id"]))
        stu_row = cursor.fetchone()

        if not stu_row:
            return False, f"Verification failed: Student '{student_identifier}' is not enrolled in institution '{session['institution_id']}'."

        student_id = stu_row[0]
        reg_no = stu_row[1]
        student_name = stu_row[2]
        campus_id = stu_row[8] or "CAMP_001"

        # Today's date and time
        today_date = datetime.date.today().isoformat()
        now_time = datetime.datetime.now().strftime("%H:%M:%S")

        # Fetch period number and scheduled times from timetable_sessions
        cursor.execute("""
            SELECT period_number, scheduled_start_time, scheduled_end_time
            FROM timetable_sessions
            WHERE session_id = ?;
        """, (session["session_id"],))
        ts_row = cursor.fetchone()
        period_number = ts_row[0] if ts_row else 1
        sched_start = ts_row[1] if ts_row else "09:00"
        sched_end = ts_row[2] if ts_row else "09:50"

        # Check for duplicate submission
        cursor.execute("""
            SELECT attendance_id, check_in_time FROM attendance
            WHERE student_id = ? AND date = ? AND (session_id = ? OR (subject_id = ? AND hour = ?));
        """, (student_id, today_date, session["session_id"], session["subject_id"], period_number))
        dup_row = cursor.fetchone()

        if dup_row:
            return False, f"Duplicate rejected: Attendance already recorded for {student_name} ({reg_no}) at {dup_row[1]}."

        # Record attendance
        now_iso = datetime.datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO attendance (
                institution_id, campus_id, student_id, subject_id, date, status,
                hour, week, room_id, verification_method, scheduled_start_time,
                scheduled_end_time, check_in_time, check_out_time, source_system,
                session_id, record_created_at, is_manually_corrected
            ) VALUES (?, ?, ?, ?, ?, 'Present', ?, 1, ?, 'DYNAMIC_QR', ?, ?, ?, ?, 'QR_CHECKIN', ?, ?, 0);
        """, (
            session["institution_id"], campus_id, student_id, session["subject_id"],
            today_date, period_number, session["room_id"], sched_start, sched_end,
            now_time, sched_end, session["session_id"], now_iso
        ))

        # Audit log
        cursor.execute("""
            INSERT INTO audit_logs (institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details)
            VALUES (?, 'QR_CHECKIN_VERIFIED', 'attendance', ?, NULL, 'Present', ?, ?, ?);
        """, (
            session["institution_id"], student_id, "STUDENT_QR_CLIENT", now_iso,
            f"Session: {session['session_id']}, Subject: {session['subject_id']}, Student: {reg_no} - {student_name}"
        ))

        conn.commit()
        return True, f"Verified! Attendance marked Present for {student_name} ({reg_no})."
    finally:
        conn.close()


def get_qr_session_roster(session_id: str, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves live roster of students who checked in via QR for a timetable session."""
    conn = get_connection(db_path)
    try:
        query = """
            SELECT a.attendance_id, a.student_id, s.register_number, s.name AS student_name,
                   s.department, s.section, a.check_in_time, a.status, a.verification_method
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.session_id = ? AND a.verification_method = 'DYNAMIC_QR'
            ORDER BY a.check_in_time ASC;
        """
        df = pd.read_sql_query(query, conn, params=[session_id])
        return df
    finally:
        conn.close()


# ==============================================================================
# GPS Geofence Campus Check-In Module
# ==============================================================================

def record_gps_checkin(
    institution_id: str,
    campus_id: str,
    user_id: str,
    latitude: float,
    longitude: float,
    distance_meters: float,
    verification_status: str,
    device_info: Optional[str] = "Web Browser Geolocation",
    db_path: str = DB_PATH
) -> str:
    """Logs a single GPS check-in attempt with verification result."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        checkin_id = f"GPS_{uuid.uuid4().hex[:10].upper()}"
        now_iso = datetime.datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO gps_checkin_logs (
                checkin_id, institution_id, campus_id, user_id, latitude, longitude,
                distance_from_center_meters, verification_status, device_info, timestamp,
                reviewed_by, review_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'Auto-Verified');
        """, (checkin_id, institution_id, campus_id, user_id, latitude, longitude, distance_meters, verification_status, device_info, now_iso))

        cursor.execute("""
            INSERT INTO audit_logs (institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details)
            VALUES (?, 'GPS_CHECKIN', 'gps_checkin_logs', ?, NULL, ?, ?, ?, ?);
        """, (institution_id, checkin_id, verification_status, user_id, now_iso, f"Dist: {distance_meters:.1f}m, Status: {verification_status}"))

        conn.commit()
        return checkin_id
    finally:
        conn.close()


def get_gps_checkin_logs(institution_id: Optional[str] = None, limit: int = 100, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves GPS check-in logs with campus coordinates and user IDs."""
    conn = get_connection(db_path)
    try:
        query = """
            SELECT g.checkin_id, g.institution_id, g.campus_id, c.name AS campus_name,
                   g.user_id, g.latitude, g.longitude, g.distance_from_center_meters,
                   g.verification_status, g.device_info, g.timestamp, g.reviewed_by, g.review_status
            FROM gps_checkin_logs g
            LEFT JOIN campuses c ON g.campus_id = c.campus_id
            WHERE 1=1
        """
        params = []
        if institution_id:
            query += " AND g.institution_id = ?"
            params.append(institution_id)
        query += " ORDER BY g.timestamp DESC LIMIT ?;"
        params.append(limit)
        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        conn.close()


def review_gps_checkin(
    checkin_id: str,
    new_review_status: str,
    reviewed_by: str,
    reason: Optional[str] = None,
    db_path: str = DB_PATH
) -> bool:
    """Allows an administrator to manually review or override a GPS check-in record."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        now_iso = datetime.datetime.now().isoformat()
        cursor.execute("""
            UPDATE gps_checkin_logs
            SET review_status = ?, reviewed_by = ?
            WHERE checkin_id = ?;
        """, (new_review_status, reviewed_by, checkin_id))
        success = cursor.rowcount > 0
        if success:
            cursor.execute("""
                INSERT INTO audit_logs (institution_id, action_type, table_affected, record_id, old_value, new_value, performed_by, timestamp, details)
                VALUES ('INST_001', 'GPS_REVIEW_OVERRIDE', 'gps_checkin_logs', ?, 'Pending', ?, ?, ?, ?);
            """, (checkin_id, new_review_status, reviewed_by, now_iso, reason or "Administrative override"))
        conn.commit()
        return success
    finally:
        conn.close()


# ==============================================================================
# Campus Infrastructure Analytics & Operations
# ==============================================================================

def get_room_occupancy_analysis(
    institution_id: Optional[str] = None,
    target_date: Optional[str] = None,
    db_path: str = DB_PATH
) -> pd.DataFrame:
    """
    Calculates room occupancy estimates by comparing attendance check-in counts
    against room seating capacity.
    """
    conn = get_connection(db_path)
    try:
        query = """
            SELECT 
                r.room_id,
                r.room_number,
                r.room_name,
                r.room_type,
                b.building_name,
                c.name AS campus_name,
                r.capacity AS room_capacity,
                r.dimension_sqft,
                r.equipment_details,
                COUNT(DISTINCT a.attendance_id) AS checkins_count,
                COUNT(DISTINCT t.session_id) AS scheduled_sessions_count,
                MAX(t.expected_strength) AS max_scheduled_strength
            FROM rooms r
            JOIN buildings b ON r.building_id = b.building_id
            JOIN campuses c ON r.campus_id = c.campus_id
            LEFT JOIN timetable_sessions t ON r.room_id = t.room_id
            LEFT JOIN attendance a ON r.room_id = a.room_id 
        """
        where_clauses = []
        params = []

        if institution_id:
            where_clauses.append("r.institution_id = ?")
            params.append(institution_id)
        if target_date:
            where_clauses.append("(a.date = ? OR a.date IS NULL)")
            params.append(target_date)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += " GROUP BY r.room_id ORDER BY r.room_number ASC;"
        df = pd.read_sql_query(query, conn, params=params)

        if not df.empty:
            df["occupancy_pct"] = (df["checkins_count"] / df["room_capacity"].replace(0, 1) * 100).round(1)
            df["capacity_breach_warning"] = df["max_scheduled_strength"] > df["room_capacity"]
        return df
    finally:
        conn.close()


def get_capacity_breach_alerts(institution_id: Optional[str] = None, db_path: str = DB_PATH) -> pd.DataFrame:
    """Finds all scheduled classes where expected student strength exceeds the room's seating capacity."""
    conn = get_connection(db_path)
    try:
        query = """
            SELECT 
                t.session_id,
                t.institution_id,
                c.name AS campus_name,
                b.building_name,
                r.room_number,
                r.room_type,
                r.capacity AS room_capacity,
                sub.subject_code,
                sub.subject_name,
                t.day_of_week,
                t.period_number,
                t.scheduled_start_time,
                t.expected_strength,
                (t.expected_strength - r.capacity) AS excess_students
            FROM timetable_sessions t
            JOIN rooms r ON t.room_id = r.room_id
            JOIN buildings b ON r.building_id = b.building_id
            JOIN campuses c ON t.campus_id = c.campus_id
            JOIN subjects sub ON t.subject_id = sub.subject_id
            WHERE t.expected_strength > r.capacity
        """
        params = []
        if institution_id:
            query += " AND t.institution_id = ?"
            params.append(institution_id)
        query += " ORDER BY excess_students DESC;"
        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        conn.close()


def create_or_update_room(
    room_id: str,
    building_id: str,
    campus_id: str,
    institution_id: str,
    room_number: str,
    room_name: str,
    floor_number: int,
    room_type: str,
    capacity: int,
    dimension_sqft: float,
    equipment_details: str,
    db_path: str = DB_PATH
) -> bool:
    """Inserts or updates room infrastructure record."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO rooms (
                room_id, building_id, campus_id, institution_id, room_number,
                room_name, floor_number, room_type, capacity, dimension_sqft, equipment_details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                building_id = excluded.building_id,
                campus_id = excluded.campus_id,
                room_number = excluded.room_number,
                room_name = excluded.room_name,
                floor_number = excluded.floor_number,
                room_type = excluded.room_type,
                capacity = excluded.capacity,
                dimension_sqft = excluded.dimension_sqft,
                equipment_details = excluded.equipment_details;
        """, (room_id, building_id, campus_id, institution_id, room_number, room_name, floor_number, room_type, capacity, dimension_sqft, equipment_details))
        conn.commit()
        return True
    finally:
        conn.close()


# =====================================================================
# AUTHENTICATION & ACCESS CONTROL (RBAC) DATABASE OPERATIONS
# =====================================================================

def get_user_by_credentials(identifier: str, role_hint: Optional[str] = None, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """
    Looks up a user record by either institutional username, email address, or institute name.
    """
    if not identifier:
        return None
    clean_id = identifier.strip().lower()
    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, institution_id, campus_id, department_id, username, full_name, email,
               role, password_hash, salt, account_status, failed_login_attempts, locked_until,
               last_login_at, must_change_password, student_id, faculty_id, is_active, created_at
        FROM users
        WHERE LOWER(username) = ? OR LOWER(email) = ?;
    """, (clean_id, clean_id))
    row = cursor.fetchone()

    # Fallback: if identifier is an institute name/code, match the primary user of that institution
    if not row:
        if any(term in clean_id for term in ["vsb", "vsbec", "institution", "college", "institutation", "engineering"]):
            target_role = role_hint or "Administrator"
            cursor.execute("""
                SELECT user_id, institution_id, campus_id, department_id, username, full_name, email,
                       role, password_hash, salt, account_status, failed_login_attempts, locked_until,
                       last_login_at, must_change_password, student_id, faculty_id, is_active, created_at
                FROM users
                WHERE (institution_id = 'INST_001' OR institution_id IS NULL)
                  AND (role = ? OR role LIKE ?)
                ORDER BY created_at ASC LIMIT 1;
            """, (target_role, f"%{target_role}%"))
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    SELECT user_id, institution_id, campus_id, department_id, username, full_name, email,
                           role, password_hash, salt, account_status, failed_login_attempts, locked_until,
                           last_login_at, must_change_password, student_id, faculty_id, is_active, created_at
                    FROM users
                    WHERE role = 'Administrator'
                    ORDER BY created_at ASC LIMIT 1;
                """)
                row = cursor.fetchone()

    conn.close()
    if row:
        return dict(row)
    return None


def get_user_by_id(user_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves full user record by user_id."""
    if not user_id:
        return None
    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, institution_id, campus_id, department_id, username, full_name, email,
               role, password_hash, salt, account_status, failed_login_attempts, locked_until,
               last_login_at, must_change_password, student_id, faculty_id, is_active, created_at
        FROM users
        WHERE user_id = ?;
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def is_account_locked(user_id_or_identifier: str, db_path: str = DB_PATH) -> Tuple[bool, Optional[str]]:
    """
    Checks if an account is currently locked due to brute-force protection.
    If lock duration (15 min) has expired, automatically unlocks the account.
    Returns (is_locked, unlock_time_str).
    """
    user = get_user_by_credentials(user_id_or_identifier, db_path=db_path)
    if not user:
        return False, None

    if user.get("account_status") != "LOCKED":
        return False, None

    locked_until_str = user.get("locked_until")
    if not locked_until_str:
        return True, "Administrator intervention required"

    try:
        locked_until_dt = datetime.datetime.fromisoformat(locked_until_str)
        now_dt = datetime.datetime.now()
        if now_dt >= locked_until_dt:
            # Automatic unlock
            unlock_user_account(user["user_id"], db_path=db_path)
            return False, None
        else:
            diff_mins = max(1, int((locked_until_dt - now_dt).total_seconds() / 60) + 1)
            return True, f"{diff_mins} minutes"
    except Exception:
        return True, "Temporarily locked"


def record_login_success(
    user_id: str,
    ip_address: str = "127.0.0.1",
    user_agent: str = "Mozilla/5.0 Web Browser",
    db_path: str = DB_PATH
) -> None:
    """Resets failed login attempts and updates last_login_at timestamp."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute("""
        UPDATE users
        SET failed_login_attempts = 0,
            locked_until = NULL,
            account_status = 'ACTIVE',
            last_login_at = ?
        WHERE user_id = ?;
    """, (now, user_id))
    conn.commit()
    conn.close()

    # Log successful authentication
    user = get_user_by_id(user_id, db_path=db_path)
    uname = user["username"] if user else user_id
    log_auth_audit(
        event_type="LOGIN_SUCCESS",
        user_id=user_id,
        username=uname,
        ip_address=ip_address,
        user_agent=user_agent,
        details="User successfully authenticated with institutional credentials",
        db_path=db_path
    )


def record_login_failure(
    identifier: str,
    ip_address: str = "127.0.0.1",
    user_agent: str = "Mozilla/5.0 Web Browser",
    max_attempts: int = 5,
    lockout_minutes: int = 15,
    db_path: str = DB_PATH
) -> Tuple[bool, str, int]:
    """
    Records a failed login attempt with brute-force rate-limiting.
    Locks the account for `lockout_minutes` once `max_attempts` is reached.
    Returns (is_now_locked, status_message, remaining_attempts).
    """
    user = get_user_by_credentials(identifier, db_path=db_path)
    if not user:
        # Unknown user: log event and return generic failure without disclosing account absence
        log_auth_audit(
            event_type="LOGIN_FAILED_UNKNOWN",
            user_id=None,
            username=identifier,
            ip_address=ip_address,
            user_agent=user_agent,
            details="Failed login attempt for unrecognized institutional username/email",
            db_path=db_path
        )
        return False, "Invalid institutional credentials. Please verify your email/username and password.", 0

    user_id = user["user_id"]
    new_attempts = int(user.get("failed_login_attempts") or 0) + 1
    conn = get_connection(db_path)
    cursor = conn.cursor()

    if new_attempts >= max_attempts:
        lock_until = (datetime.datetime.now() + datetime.timedelta(minutes=lockout_minutes)).isoformat()
        cursor.execute("""
            UPDATE users
            SET failed_login_attempts = ?,
                account_status = 'LOCKED',
                locked_until = ?
            WHERE user_id = ?;
        """, (new_attempts, lock_until, user_id))
        conn.commit()
        conn.close()

        log_auth_audit(
            event_type="ACCOUNT_LOCKED",
            user_id=user_id,
            username=user["username"],
            ip_address=ip_address,
            user_agent=user_agent,
            details=f"Account locked for {lockout_minutes} minutes after {new_attempts} consecutive failed login attempts",
            db_path=db_path
        )
        return True, f"Account temporarily locked due to {max_attempts} failed attempts. Please wait {lockout_minutes} minutes or reset your password.", 0
    else:
        cursor.execute("""
            UPDATE users
            SET failed_login_attempts = ?
            WHERE user_id = ?;
        """, (new_attempts, user_id))
        conn.commit()
        conn.close()

        remaining = max_attempts - new_attempts
        log_auth_audit(
            event_type="LOGIN_FAILED",
            user_id=user_id,
            username=user["username"],
            ip_address=ip_address,
            user_agent=user_agent,
            details=f"Invalid password submitted (attempt {new_attempts}/{max_attempts})",
            db_path=db_path
        )
        return False, "Invalid institutional credentials. Please verify your email/username and password.", remaining


def create_auth_session(
    user_id: str,
    remember_me: bool = False,
    ip_address: str = "127.0.0.1",
    user_agent: str = "Mozilla/5.0 Web Browser",
    db_path: str = DB_PATH
) -> Tuple[str, str]:
    """
    Issues a cryptographically secure session token and persists its SHA-256 hash.
    Standard session expires in 2 hours; Remember-Me session expires in 30 days.
    Returns (raw_session_token, session_id).
    """
    raw_token = generate_secure_token(32)
    token_hash = hash_token(raw_token)
    session_id = f"SESS_{uuid.uuid4().hex[:12].upper()}"

    now = datetime.datetime.now()
    if remember_me:
        expires_at = (now + datetime.timedelta(days=30)).isoformat()
    else:
        expires_at = (now + datetime.timedelta(hours=2)).isoformat()

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO auth_sessions (
            session_id, user_id, session_token_hash, created_at, last_activity_at,
            expires_at, is_remember_me, ip_address, user_agent, is_revoked
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0);
    """, (session_id, user_id, token_hash, now.isoformat(), now.isoformat(), expires_at, 1 if remember_me else 0, ip_address, user_agent))
    conn.commit()
    conn.close()

    return raw_token, session_id


def validate_session_token(token: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """
    Validates a session token against stored SHA-256 hash and expiration.
    If valid, updates `last_activity_at` and returns joined user dictionary.
    If expired or revoked, invalidates and returns None.
    """
    if not token:
        return None
    token_hash = hash_token(token)
    now = datetime.datetime.now().isoformat()

    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.session_id, s.user_id, s.expires_at, s.is_revoked, s.is_remember_me,
               u.institution_id, u.campus_id, u.department_id, u.username, u.full_name,
               u.email, u.role, u.account_status, u.is_active, u.student_id, u.faculty_id
        FROM auth_sessions s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.session_token_hash = ? AND s.is_revoked = 0 AND u.is_active = 1 AND u.account_status = 'ACTIVE';
    """, (token_hash,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    session_data = dict(row)
    if session_data["expires_at"] < now:
        # Mark expired session as revoked
        cursor.execute("UPDATE auth_sessions SET is_revoked = 1 WHERE session_id = ?;", (session_data["session_id"],))
        conn.commit()
        conn.close()
        return None

    # Sliding expiration update for active session
    cursor.execute("UPDATE auth_sessions SET last_activity_at = ? WHERE session_id = ?;", (now, session_data["session_id"]))
    conn.commit()
    conn.close()

    return session_data


def revoke_session(token: str, db_path: str = DB_PATH) -> bool:
    """Revokes a specific session token upon logout."""
    if not token:
        return False
    token_hash = hash_token(token)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE auth_sessions SET is_revoked = 1 WHERE session_token_hash = ?;", (token_hash,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def revoke_all_user_sessions(user_id: str, db_path: str = DB_PATH) -> bool:
    """Invalidates all active sessions for a user (used upon password reset or security revocation)."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE auth_sessions SET is_revoked = 1 WHERE user_id = ? AND is_revoked = 0;", (user_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def create_password_reset_token(identifier: str, db_path: str = DB_PATH) -> Tuple[bool, str, Optional[str]]:
    """
    Generates a secure password reset token valid for 30 minutes.
    Returns (success, message, raw_token_for_display_or_email).
    """
    user = get_user_by_credentials(identifier, db_path=db_path)
    if not user:
        # Generic response to prevent user enumeration
        return True, "If an account matching the provided institutional identifier exists, password reset instructions have been generated.", None

    raw_token = generate_secure_token(24)
    token_hash = hash_token(raw_token)
    token_id = f"RST_{uuid.uuid4().hex[:10].upper()}"
    now = datetime.datetime.now()
    expires_at = (now + datetime.timedelta(minutes=30)).isoformat()

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO password_reset_tokens (token_id, user_id, token_hash, created_at, expires_at, used_at)
        VALUES (?, ?, ?, ?, ?, NULL);
    """, (token_id, user["user_id"], token_hash, now.isoformat(), expires_at))
    conn.commit()
    conn.close()

    log_auth_audit(
        event_type="PASSWORD_RESET_REQUEST",
        user_id=user["user_id"],
        username=user["username"],
        ip_address="127.0.0.1",
        user_agent="System",
        details="Password reset token issued (valid 30 minutes)",
        db_path=db_path
    )

    return True, "Password reset token generated successfully. Valid for 30 minutes.", raw_token


def validate_and_consume_reset_token(
    token: str,
    new_password_hash: str,
    new_salt: str,
    db_path: str = DB_PATH
) -> Tuple[bool, str]:
    """
    Validates a password reset token, applies the new hashed password, unlocks the account,
    invalidates the reset token, and revokes all older active sessions.
    """
    if not token:
        return False, "Invalid or missing reset token."
    token_hash = hash_token(token)
    now = datetime.datetime.now().isoformat()

    conn = get_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT token_id, user_id, expires_at, used_at
        FROM password_reset_tokens
        WHERE token_hash = ?;
    """, (token_hash,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return False, "Invalid or unrecognized reset token."

    token_data = dict(row)
    if token_data["used_at"] is not None:
        conn.close()
        return False, "This password reset token has already been consumed."

    if token_data["expires_at"] < now:
        conn.close()
        return False, "This password reset token has expired. Please request a new token."

    user_id = token_data["user_id"]

    # Apply password update, unlock account, and mark token as used in single transaction
    cursor.execute("""
        UPDATE users
        SET password_hash = ?,
            salt = ?,
            account_status = 'ACTIVE',
            failed_login_attempts = 0,
            locked_until = NULL,
            must_change_password = 0,
            updated_at = ?
        WHERE user_id = ?;
    """, (new_password_hash, new_salt, now, user_id))

    cursor.execute("UPDATE password_reset_tokens SET used_at = ? WHERE token_id = ?;", (now, token_data["token_id"]))
    cursor.execute("UPDATE auth_sessions SET is_revoked = 1 WHERE user_id = ?;", (user_id,))

    conn.commit()
    conn.close()

    log_auth_audit(
        event_type="PASSWORD_RESET_SUCCESS",
        user_id=user_id,
        username=None,
        ip_address="127.0.0.1",
        user_agent="System",
        details="Password successfully updated and account unlocked via secure reset token",
        db_path=db_path
    )

    return True, "Your password has been successfully reset. You can now sign in with your new credentials."


def update_user_password(
    user_id: str,
    new_password_hash: str,
    new_salt: str,
    db_path: str = DB_PATH
) -> bool:
    """Updates a user's password directly (by admin or authenticated user)."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute("""
        UPDATE users
        SET password_hash = ?,
            salt = ?,
            account_status = 'ACTIVE',
            failed_login_attempts = 0,
            locked_until = NULL,
            must_change_password = 0,
            updated_at = ?
        WHERE user_id = ?;
    """, (new_password_hash, new_salt, now, user_id))
    affected = cursor.rowcount
    cursor.execute("UPDATE auth_sessions SET is_revoked = 1 WHERE user_id = ?;", (user_id,))
    conn.commit()
    conn.close()
    return affected > 0


def create_new_user(user_data: Dict[str, Any], db_path: str = DB_PATH) -> Tuple[bool, str, Optional[str]]:
    """Creates a new institutional user with role and credentials."""
    username = (user_data.get("username") or "").strip().lower()
    email = (user_data.get("email") or "").strip().lower()
    full_name = (user_data.get("full_name") or "").strip()
    role = user_data.get("role", "Faculty")
    password = user_data.get("password")

    if not username or not full_name:
        return False, "Username and Full Name are required fields.", None

    if not password:
        return False, "Password is required for user creation.", None

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = ? OR (email IS NOT NULL AND LOWER(email) = ?);", (username, email))
    if cursor.fetchone():
        conn.close()
        return False, f"A user with username '{username}' or email '{email}' already exists.", None

    p_hash, p_salt = hash_password(password)
    user_id = f"USR_{uuid.uuid4().hex[:10].upper()}"
    now = datetime.datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO users (
            user_id, institution_id, campus_id, department_id, username, full_name, email,
            role, password_hash, salt, account_status, failed_login_attempts, must_change_password,
            student_id, faculty_id, is_active, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 0, ?, ?, ?, 1, ?);
    """, (
        user_id,
        user_data.get("institution_id", "INST_001"),
        user_data.get("campus_id", "CAMP_001"),
        user_data.get("department_id"),
        username,
        full_name,
        email or None,
        role,
        p_hash,
        p_salt,
        1 if user_data.get("must_change_password") else 0,
        user_data.get("student_id"),
        user_data.get("faculty_id"),
        now
    ))
    conn.commit()
    conn.close()

    log_auth_audit(
        event_type="USER_CREATED",
        user_id=user_id,
        username=username,
        ip_address="127.0.0.1",
        user_agent="System Admin",
        details=f"New user created with role '{role}' and institution '{user_data.get('institution_id', 'INST_001')}'",
        db_path=db_path
    )

    return True, f"User '{username}' created successfully.", user_id


def get_all_registered_users(limit: int = 200, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves all registered users without exposing password hashes or salts."""
    conn = get_connection(db_path)
    query = """
        SELECT user_id, username, full_name, email, role, institution_id, department_id,
               account_status, failed_login_attempts, locked_until, last_login_at,
               student_id, is_active, created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT ?;
    """
    df = pd.read_sql_query(query, conn, params=[limit])
    conn.close()
    return df


def unlock_user_account(user_id: str, db_path: str = DB_PATH) -> bool:
    """Manually or automatically unlocks a locked user account."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET account_status = 'ACTIVE',
            failed_login_attempts = 0,
            locked_until = NULL
        WHERE user_id = ?;
    """, (user_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()

    if affected > 0:
        log_auth_audit(
            event_type="ACCOUNT_UNLOCKED",
            user_id=user_id,
            username=None,
            ip_address="127.0.0.1",
            user_agent="System",
            details="Account status restored to ACTIVE with zero failed attempts",
            db_path=db_path
        )
    return affected > 0


def log_auth_audit(
    event_type: str,
    user_id: Optional[str],
    username: Optional[str],
    ip_address: str,
    user_agent: str,
    details: str,
    db_path: str = DB_PATH
) -> None:
    """Appends an event to the security & authentication audit log."""
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO auth_audit_logs (user_id, username, event_type, ip_address, user_agent, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (user_id, username, event_type, ip_address, user_agent, details, now))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_auth_audit_logs_df(limit: int = 150, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieves recent authentication and security audit logs."""
    conn = get_connection(db_path)
    query = """
        SELECT event_id, timestamp, event_type, username, user_id, ip_address, details
        FROM auth_audit_logs
        ORDER BY timestamp DESC
        LIMIT ?;
    """
    df = pd.read_sql_query(query, conn, params=[limit])
    conn.close()
    return df


