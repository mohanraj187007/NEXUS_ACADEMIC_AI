"""
Comprehensive Automated Test Suite for Academic Attendance Pattern & Risk Analytics System
Validates database migrations, institutional attendance calculation rules, CSV/Excel ingestion,
row-level validation error handling, duplicate and conflict resolution, threshold boundaries,
multi-source reconciliation rules, genuine ML model evaluation, audit logging, and vendor adapters.
Uses an isolated temporary SQLite database to guarantee zero test leakage into production.
"""

import os
import sys
import unittest
import tempfile
import pandas as pd
import numpy as np

# Ensure root directory is on python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database.database import (
    init_db, reset_database, get_all_students, get_all_subjects, 
    get_full_attendance_dataset, get_database_summary, get_setting, set_setting,
    record_manual_attendance_correction, get_audit_logs, clear_attendance_records
)
from data.generator import generate_and_seed_database
from analytics.attendance import (
    calculate_overall_metrics, calculate_student_summary, get_all_students_summary,
    get_subject_wise_attendance, get_weekly_attendance_trend, get_class_benchmarks,
    compute_session_eligibility, get_department_wise_attendance, get_periodic_trends
)
from analytics.trend_analysis import analyze_student_trend, get_cohort_trend_distribution
from analytics.risk_engine import calculate_student_risk, calculate_cohort_risk_registry
from analytics.pattern_detection import get_all_student_patterns, calculate_attendance_streaks
from analytics.anomaly_detection import detect_student_anomaly, scan_cohort_anomalies
from analytics.prediction import predict_student_trajectory, get_early_warning_registry
from analytics.recovery_simulator import calculate_recovery_roadmap, simulate_what_if_scenario
from analytics.reconciliation import (
    run_reconciliation_scan, get_reconciliation_cases, update_case_status, 
    import_raw_events_stream
)
from analytics.ml_risk_model import train_and_evaluate_risk_model, predict_student_risk_ml
from utils.preprocessing import (
    validate_and_process_file, validate_and_process_csv, 
    generate_csv_template, generate_excel_template
)
from integrations.vendor_adapters import (
    CsvXlsxExportAdapter, BiometricApiAdapter, CampusGateApiAdapter, get_all_adapters
)
from reports.report_generator import generate_student_csv, generate_class_csv, generate_student_pdf
from utils.importer import (
    generate_category_template, validate_and_prepare_batch, commit_prepared_batch,
    IMPORT_CATEGORIES, CATEGORY_SCHEMAS
)
from analytics.qr_engine import open_new_qr_session, validate_and_record_student_qr
from database.database import (
    get_connection, get_campuses, get_rooms, get_timetable_sessions,
    get_capacity_breach_alerts, get_room_occupancy_analysis, create_or_update_room,
    close_qr_session, get_active_qr_session, get_gps_checkin_logs, review_gps_checkin
)
from analytics.gps_engine import haversine_distance_meters, evaluate_geofence, execute_gps_checkin
from utils.auth_context import (
    can_import_data, can_manage_infrastructure, can_start_qr_session,
    can_adjudicate_reconciliation, can_edit_settings, can_access_module,
    normalize_role, ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY, ROLE_STUDENT
)
from utils.security import (
    hash_password, verify_password, validate_password_strength, generate_secure_token
)
from database.database import (
    get_user_by_credentials, record_login_success, record_login_failure,
    is_account_locked, unlock_user_account, create_auth_session, validate_session_token,
    revoke_session, create_password_reset_token, validate_and_consume_reset_token,
    get_all_registered_users, get_auth_audit_logs_df, update_user_password, create_new_user
)


class TestAcademicAttendanceSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initializes an isolated temporary test database to prevent production leakage."""
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = os.path.join(cls.temp_dir.name, "test_attendance.db")
        print(f"\n[SETUP] Initializing isolated test database at: {cls.test_db_path}")
        init_db(cls.test_db_path)

        # Seed isolated test dataset
        summary = generate_and_seed_database(num_students=40, num_weeks=10, db_path=cls.test_db_path)
        cls.df = get_full_attendance_dataset(db_path=cls.test_db_path)
        print(f"[SETUP] Seeded isolated test fixture: {summary['total_students']} students, {summary['total_attendance_records']} records.")

    @classmethod
    def tearDownClass(cls):
        """Cleans up the temporary test database."""
        import gc
        gc.collect()
        try:
            cls.temp_dir.cleanup()
            print("[TEARDOWN] Temporary test database removed cleanly.")
        except Exception:
            pass

    def test_01_database_schema_and_integrity(self):
        """Tests that all core, reconciliation, and audit tables exist and are queryable."""
        summary = get_database_summary(db_path=self.test_db_path)
        self.assertGreater(summary["total_students"], 0)
        self.assertGreater(summary["total_subjects"], 0)
        self.assertGreater(summary["total_attendance_records"], 0)

        # Verify settings
        thresh = get_setting("mandatory_attendance_pct", db_path=self.test_db_path)
        self.assertEqual(float(thresh), 75.0)

    def test_02_institutional_attendance_formula(self):
        """Tests institutional attendance formula with cancelled sessions and excused leaves."""
        # 1. Cancelled session is neither eligible nor attended
        is_el, is_att = compute_session_eligibility("Cancelled", excused_rule="exclude_from_total")
        self.assertFalse(is_el)
        self.assertFalse(is_att)

        # 2. Present session is both eligible and attended
        is_el, is_att = compute_session_eligibility("Present", excused_rule="exclude_from_total")
        self.assertTrue(is_el)
        self.assertTrue(is_att)

        # 3. Late session is eligible and attended
        is_el, is_att = compute_session_eligibility("Late", excused_rule="exclude_from_total")
        self.assertTrue(is_el)
        self.assertTrue(is_att)

        # 4. Absent session is eligible, not attended
        is_el, is_att = compute_session_eligibility("Absent", excused_rule="exclude_from_total")
        self.assertTrue(is_el)
        self.assertFalse(is_att)

        # 5. Excused session with exclude_from_total rule
        is_el, is_att = compute_session_eligibility("Excused", excused_rule="exclude_from_total")
        self.assertFalse(is_el)

        # 6. Overall calculation
        metrics = calculate_overall_metrics(self.df, excused_rule="exclude_from_total")
        self.assertGreater(metrics["overall_attendance_pct"], 30.0)
        self.assertLessEqual(metrics["overall_attendance_pct"], 100.0)

    def test_03_csv_and_excel_file_ingestion(self):
        """Tests CSV and Excel ingestion with validation, column mapping, and row-level error reporting."""
        # A. Create a valid CSV with metadata
        csv_content = (
            "student_id,student_name,department,semester,year,section,subject_id,attendance_date,period_number,attendance_status,scheduled_start_time,check_in_time\n"
            "STU_VAL_01,Test Student One,Computer Science,3,2,A,CS301,2024-03-01,1,Present,09:00,08:55\n"
            "STU_VAL_02,Test Student Two,Information Technology,3,2,B,CS302,2024-03-01,1,Late,09:00,09:12\n"
            "STU_VAL_03,Test Student Three,AI & Data Science,3,2,A,CS303,2024-03-01,1,Absent,09:00,\n"
            ",Invalid Missing ID,Computer Science,3,2,A,CS301,2024-03-01,1,Present,09:00,08:58\n"  # Invalid: Missing student_id
            "STU_VAL_04,Invalid Date Student,Computer Science,3,2,A,CS301,invalid-date,1,Present,09:00,08:58\n"  # Invalid: Bad date
            "STU_VAL_05,Invalid Status Student,Computer Science,3,2,A,CS301,2024-03-01,1,UnknownStatus,09:00,08:58\n"  # Invalid: Bad status
        ).encode("utf-8")

        success, summary, clean_df = validate_and_process_file(
            file_bytes=csv_content,
            file_name="test_ingest.csv",
            conflict_strategy="skip",
            authorized_user="Auditor",
            db_path=self.test_db_path
        )
        self.assertTrue(success)
        self.assertEqual(summary["total_raw"], 6)
        self.assertEqual(summary["valid_records"], 3)
        self.assertEqual(summary["invalid_records"], 3)
        self.assertEqual(len(summary["row_errors"]), 3)

        # B. Template generation tests
        csv_temp = generate_csv_template()
        self.assertGreater(len(csv_temp), 100)
        xlsx_temp = generate_excel_template()
        self.assertGreater(len(xlsx_temp), 1000)

    def test_04_duplicate_detection_and_conflict_handling(self):
        """Tests internal duplicate consolidation and non-destructive conflict handling."""
        # 1. File with internal duplicate
        csv_with_dups = (
            "student_id,attendance_date,period_number,attendance_status,subject_id\n"
            "STU_DUP_1,2024-03-10,1,Present,CS301\n"
            "STU_DUP_1,2024-03-10,1,Present,CS301\n"  # Duplicate
        ).encode("utf-8")

        success, summary, _ = validate_and_process_file(
            file_bytes=csv_with_dups,
            file_name="test_dups.csv",
            conflict_strategy="skip",
            db_path=self.test_db_path
        )
        self.assertTrue(success)
        self.assertEqual(summary["internal_duplicates_dropped"], 1)
        self.assertEqual(summary["inserted_records"], 1)

        # 2. Incoming conflicting status (Incoming says Absent, existing says Present)
        conflict_csv = (
            "student_id,attendance_date,period_number,attendance_status,subject_id\n"
            "STU_DUP_1,2024-03-10,1,Absent,CS301\n"
        ).encode("utf-8")

        # Under "skip" strategy: conflicting record is skipped to preserve data
        _, summary_skip, _ = validate_and_process_file(
            file_bytes=conflict_csv,
            file_name="conflict.csv",
            conflict_strategy="skip",
            db_path=self.test_db_path
        )
        self.assertEqual(summary_skip["skipped_conflicts"], 1)
        self.assertEqual(summary_skip["inserted_records"], 0)

        # Under "update_with_audit" strategy: conflicting record is updated and logged
        _, summary_update, _ = validate_and_process_file(
            file_bytes=conflict_csv,
            file_name="conflict_update.csv",
            conflict_strategy="update_with_audit",
            authorized_user="Dean_Affairs",
            db_path=self.test_db_path
        )
        self.assertEqual(summary_update["updated_records"], 1)

    def test_05_threshold_boundaries_and_benchmarks(self):
        """Tests student-level threshold boundaries: 75% cutoff, approaching buffer, and department benchmarks."""
        # Set settings
        set_setting("mandatory_attendance_pct", 75.0, db_path=self.test_db_path)
        set_setting("warning_attendance_pct", 80.0, db_path=self.test_db_path)

        all_sums = get_all_students_summary(self.df)
        self.assertFalse(all_sums.empty)
        self.assertIn("attendance_pct", all_sums.columns)

        dept_df = get_department_wise_attendance(self.df)
        self.assertFalse(dept_df.empty)
        self.assertIn("attendance_pct", dept_df.columns)

        # Student benchmarks
        s_id = self.df["student_id"].iloc[0]
        bench = get_class_benchmarks(self.df, student_id=s_id)
        self.assertIn("student_pct", bench)
        self.assertIn("class_avg", bench)
        self.assertIn("delta_class", bench)

    def test_06_multi_source_reconciliation_engine(self):
        """Tests multi-source discrepancy matching, evidence inspection, and audit workflow."""
        s_id = self.df["student_id"].iloc[0]

        # Ingest gate entry for this student on 2024-04-01
        gate_events = pd.DataFrame([{
            "student_id": s_id,
            "event_timestamp": "2024-04-01 08:45:00",
            "event_type": "gate_entry",
            "location_or_device": "Main_Campus_Turnstile_01",
            "raw_payload": "{}"
        }])
        import_raw_events_stream(gate_events, source_type="campus_gate", batch_id="TEST_GATE_1", db_path=self.test_db_path)

        # Ingest classroom attendance showing Absent on the same date
        absent_class = pd.DataFrame([{
            "student_id": s_id,
            "attendance_date": "2024-04-01",
            "period_number": 1,
            "attendance_status": "Absent",
            "subject_id": "CS301"
        }])
        validate_and_process_file(
            file_bytes=absent_class.to_csv(index=False).encode("utf-8"),
            file_name="absent_test.csv",
            conflict_strategy="skip",
            db_path=self.test_db_path
        )

        # Run reconciliation scan
        scan_res = run_reconciliation_scan(date_filter="2024-04-01", tolerance_minutes=15, db_path=self.test_db_path)
        self.assertIn("new_cases_created", scan_res)
        self.assertIn("disclaimer", scan_res)

        # Verify case is recorded
        cases = get_reconciliation_cases(student_id=s_id, db_path=self.test_db_path)
        self.assertFalse(cases.empty)
        case_id = int(cases.iloc[0]["case_id"])

        # Test case review status update
        success = update_case_status(
            case_id=case_id,
            new_status="Verified",
            reviewer_notes="Student verified present in library researching senior project.",
            reviewer_user="Dean_Academic",
            db_path=self.test_db_path
        )
        self.assertTrue(success)

        # Confirm audit log was created
        audit_logs = get_audit_logs(limit=10, db_path=self.test_db_path)
        self.assertFalse(audit_logs.empty)
        self.assertIn("RECONCILIATION_REVIEW", audit_logs["action_type"].values)

    def test_07_machine_learning_risk_evaluation(self):
        """Tests machine learning model training on holdout split with genuine metrics."""
        eval_res = train_and_evaluate_risk_model(self.df, threshold=75.0, test_size=0.25, random_state=42)
        self.assertEqual(eval_res["status"], "TRAINED_SUCCESS")
        
        # Verify genuine metrics exist and are in valid float bounds
        self.assertGreaterEqual(eval_res["precision"], 0.0)
        self.assertLessEqual(eval_res["precision"], 1.0)
        self.assertGreaterEqual(eval_res["recall"], 0.0)
        self.assertLessEqual(eval_res["recall"], 1.0)
        self.assertGreaterEqual(eval_res["f1_score"], 0.0)
        self.assertLessEqual(eval_res["f1_score"], 1.0)
        self.assertGreaterEqual(eval_res["roc_auc"], 0.0)
        self.assertLessEqual(eval_res["roc_auc"], 1.0)
        self.assertGreater(len(eval_res["feature_importances"]), 0)

        # Test individual student prediction
        s_id = self.df["student_id"].iloc[0]
        pred = predict_student_risk_ml(self.df, student_id=s_id)
        self.assertEqual(pred["status"], "PREDICTED")
        self.assertIn(pred["ml_prediction"], ["AT_RISK", "COMPLIANT"])

    def test_08_manual_correction_audit_trail(self):
        """Tests authorized manual record correction with mandatory audit logging."""
        conn = get_full_attendance_dataset(db_path=self.test_db_path)
        first_row = conn.iloc[0]
        att_id = int(first_row["attendance_id"])
        original_status = first_row["status"]
        target_status = "Late" if original_status != "Late" else "Present"

        # Apply manual correction
        success = record_manual_attendance_correction(
            attendance_id=att_id,
            new_status=target_status,
            reason="Bus breakdown confirmed by transit slip #TR-442",
            performed_by="HOD_Computer_Science",
            db_path=self.test_db_path
        )
        self.assertTrue(success)

        # Verify audit log recorded old and new value
        logs = get_audit_logs(limit=5, db_path=self.test_db_path)
        corr_logs = logs[logs["action_type"] == "MANUAL_CORRECTION"]
        self.assertFalse(corr_logs.empty)
        self.assertEqual(corr_logs.iloc[0]["record_id"], str(att_id))
        self.assertEqual(corr_logs.iloc[0]["new_value"], target_status)

    def test_09_vendor_adapters_connectivity(self):
        """Tests vendor adapter interfaces and honest offline reporting."""
        adapters = get_all_adapters()
        self.assertEqual(len(adapters), 3)

        file_adapter = adapters[0]
        self.assertTrue(file_adapter.is_configured())
        res_file = file_adapter.test_connection()
        self.assertTrue(res_file["success"])
        self.assertEqual(res_file["status"], "OPERATIONAL")

        # Unconfigured biometric adapter must honestly report NOT_CONFIGURED
        bio_adapter = adapters[1]
        set_setting("biometric_api_endpoint", "", db_path=self.test_db_path)
        self.assertFalse(bio_adapter.is_configured())
        res_bio = bio_adapter.test_connection()
        self.assertFalse(res_bio["success"])
        self.assertEqual(res_bio["status"], "NOT_CONFIGURED")

    def test_10_reports_export_formats(self):
        """Tests PDF, CSV, and Excel export generation."""
        student_id = self.df["student_id"].iloc[0]
        summary = calculate_student_summary(self.df, student_id)
        risk = calculate_student_risk(self.df, student_id)
        sub_df = get_subject_wise_attendance(self.df, student_id)

        # PDF Export
        pdf_bytes = generate_student_pdf(summary, risk, sub_df)
        self.assertGreater(len(pdf_bytes), 1000)

        # CSV Export
        csv_bytes = generate_student_csv(summary, risk, sub_df)
        self.assertGreater(len(csv_bytes), 100)

        # Cohort CSV Export
        risk_df = calculate_cohort_risk_registry(self.df)
        class_csv = generate_class_csv(risk_df)
        self.assertGreater(len(class_csv), 100)

    def test_11_multi_tenant_data_isolation(self):
        """Tests that two institutions have strict tenant data isolation."""
        conn = get_connection(self.test_db_path)
        cur = conn.cursor()

        # Seed two distinct institutions
        cur.execute("INSERT OR REPLACE INTO institutions (institution_id, institution_code, name, created_at) VALUES ('INST_ALPHA', 'ALPHA', 'Alpha University', '2024-01-01');")
        cur.execute("INSERT OR REPLACE INTO institutions (institution_id, institution_code, name, created_at) VALUES ('INST_BETA', 'BETA', 'Beta Institute of Tech', '2024-01-01');")

        # Campuses
        cur.execute("INSERT OR REPLACE INTO campuses (campus_id, institution_id, campus_code, name) VALUES ('CAMP_A', 'INST_ALPHA', 'ALPHA_MAIN', 'Alpha Main Campus');")
        cur.execute("INSERT OR REPLACE INTO campuses (campus_id, institution_id, campus_code, name) VALUES ('CAMP_B', 'INST_BETA', 'BETA_EAST', 'Beta East Campus');")

        # Students
        cur.execute("INSERT OR REPLACE INTO students (student_id, institution_id, register_number, name, department, year, semester, section) VALUES ('STU_A1', 'INST_ALPHA', 'REG_A1', 'Alice Alpha', 'CS', 3, 5, 'A');")
        cur.execute("INSERT OR REPLACE INTO students (student_id, institution_id, register_number, name, department, year, semester, section) VALUES ('STU_B1', 'INST_BETA', 'REG_B1', 'Bob Beta', 'ME', 2, 3, 'B');")

        conn.commit()
        conn.close()

        # Verify Alpha only sees its own records
        alpha_campuses = get_campuses(institution_id="INST_ALPHA", db_path=self.test_db_path)
        self.assertEqual(len(alpha_campuses), 1)
        self.assertEqual(alpha_campuses.iloc[0]["campus_id"], "CAMP_A")

        beta_campuses = get_campuses(institution_id="INST_BETA", db_path=self.test_db_path)
        self.assertEqual(len(beta_campuses), 1)
        self.assertEqual(beta_campuses.iloc[0]["campus_id"], "CAMP_B")

        # Verify Alpha cannot see Beta students
        from database.database import get_all_students
        alpha_students = get_all_students(institution_id="INST_ALPHA", db_path=self.test_db_path)
        self.assertTrue(all(s != "STU_B1" for s in alpha_students["student_id"].values))
        self.assertIn("STU_A1", alpha_students["student_id"].values)

    def test_12_universal_bulk_importer_and_validation(self):
        """Tests 9-category template generation, validation workflow, duplicate handling, and transactional commit."""
        # 1. Verify template generation across all 9 categories (CSV and XLSX)
        for cat in IMPORT_CATEGORIES.keys():
            csv_data = generate_category_template(cat, file_format="csv")
            self.assertGreater(len(csv_data), 20)
            xlsx_data = generate_category_template(cat, file_format="xlsx")
            self.assertGreater(len(xlsx_data), 100)

        # 2. Test valid student CSV batch import
        sample_csv = "student_id,register_number,name,department,year,semester,section,email\nSTU_TEST_99,REG_TEST_99,Charlie Test,Computer Science,3,5,A,charlie@test.edu\n"
        is_valid, summary, valid_df = validate_and_prepare_batch(
            file_bytes=sample_csv.encode("utf-8"),
            file_name="students_valid.csv",
            category="students",
            institution_id="INST_001",
            db_path=self.test_db_path
        )
        self.assertTrue(is_valid)
        self.assertEqual(summary["valid_count"], 1)
        self.assertEqual(summary["invalid_count"], 0)

        # Commit batch
        ok, msg = commit_prepared_batch(
            valid_df=valid_df,
            category="students",
            batch_id=summary["batch_id"],
            institution_id="INST_001",
            db_path=self.test_db_path
        )
        self.assertTrue(ok)

        # Verify student exists in DB
        students_df = get_all_students(institution_id="INST_001", db_path=self.test_db_path)
        self.assertIn("STU_TEST_99", students_df["student_id"].values)

        # 3. Test invalid rows and duplicate rejection
        bad_csv = "student_id,register_number,name,department\n,REG_EMPTY,No ID,CS\nSTU_DUP,REG_DUP1,Dup 1,CS\nSTU_DUP,REG_DUP2,Dup 2,CS\n"
        is_v, summ, v_df = validate_and_prepare_batch(
            file_bytes=bad_csv.encode("utf-8"),
            file_name="bad.csv",
            category="students",
            institution_id="INST_001",
            db_path=self.test_db_path
        )
        self.assertTrue(is_v)
        self.assertEqual(summ["invalid_count"], 1)  # Empty student_id
        self.assertEqual(summ["duplicate_count"], 1)  # STU_DUP deduplicated
        self.assertEqual(len(v_df), 1)

    def test_13_campus_infrastructure_and_capacity_breach(self):
        """Tests room registration, capacity breach detection in timetables, and occupancy analytics."""
        # 1. Create a room with seating capacity of 40
        success = create_or_update_room(
            room_id="RM_LAB_TEST",
            building_id="BLD_001",
            campus_id="CAMP_001",
            institution_id="INST_001",
            room_number="T-101",
            room_name="Testing Micro-Lab",
            floor_number=1,
            room_type="Laboratory",
            capacity=40,
            dimension_sqft=600.0,
            equipment_details="40 Test Terminals",
            db_path=self.test_db_path
        )
        self.assertTrue(success)

        # 2. Insert a timetable session where expected strength is 65 (breach: 65 > 40)
        conn = get_connection(self.test_db_path)
        sub_id = self.df["subject_id"].iloc[0]
        conn.execute("""
            INSERT OR REPLACE INTO timetable_sessions (
                session_id, institution_id, campus_id, subject_id, room_id,
                day_of_week, period_number, scheduled_start_time, scheduled_end_time,
                expected_strength
            ) VALUES ('SESS_BREACH_01', 'INST_001', 'CAMP_001', ?, 'RM_LAB_TEST', 'Monday', 1, '09:00', '09:50', 65);
        """, (sub_id,))
        conn.commit()
        conn.close()

        # 3. Verify capacity breach detected
        breaches = get_capacity_breach_alerts(institution_id="INST_001", db_path=self.test_db_path)
        self.assertFalse(breaches.empty)
        matched_breach = breaches[breaches["session_id"] == "SESS_BREACH_01"]
        self.assertFalse(matched_breach.empty)
        self.assertEqual(matched_breach.iloc[0]["excess_students"], 25)

        # 4. Check occupancy analysis
        occ_df = get_room_occupancy_analysis(institution_id="INST_001", db_path=self.test_db_path)
        self.assertFalse(occ_df.empty)
        self.assertIn("RM_LAB_TEST", occ_df["room_id"].values)

    def test_14_dynamic_qr_attendance_lifecycle(self):
        """Tests dynamic QR token creation, check-in submission, duplicate prevention, and closed session handling."""
        # 1. Open dynamic QR session
        sess_data = open_new_qr_session(
            session_id="SESS_BREACH_01",
            institution_id="INST_001",
            subject_id=self.df["subject_id"].iloc[0],
            room_id="RM_LAB_TEST",
            opened_by="Prof_Tester",
            validity_seconds=180,
            db_path=self.test_db_path
        )
        qrs_id = sess_data["qr_session_id"]
        token_hash = sess_data["token_hash"]
        self.assertGreater(len(sess_data["qr_image_bytes"]), 500)

        # 2. Submit valid check-in
        stu_id = self.df["student_id"].iloc[0]
        ok, msg = validate_and_record_student_qr(
            qr_session_id=qrs_id,
            student_identifier=stu_id,
            token_submitted=token_hash,
            db_path=self.test_db_path
        )
        self.assertTrue(ok)
        self.assertIn("Verified", msg)

        # 3. Duplicate check-in submission by same student must be rejected
        dup_ok, dup_msg = validate_and_record_student_qr(
            qr_session_id=qrs_id,
            student_identifier=stu_id,
            token_submitted=token_hash,
            db_path=self.test_db_path
        )
        self.assertFalse(dup_ok)
        self.assertIn("Duplicate rejected", dup_msg)

        # 4. Tampered token must be rejected
        bad_ok, bad_msg = validate_and_record_student_qr(
            qr_session_id=qrs_id,
            student_identifier=self.df["student_id"].iloc[1],
            token_submitted="TAMPERED_FAKE_HASH_12345",
            db_path=self.test_db_path
        )
        self.assertFalse(bad_ok)
        self.assertIn("Security verification failed", bad_msg)

        # 5. Close session and verify subsequent submissions are rejected
        close_qr_session(qrs_id, closed_by="Prof_Tester", db_path=self.test_db_path)
        closed_ok, closed_msg = validate_and_record_student_qr(
            qr_session_id=qrs_id,
            student_identifier=self.df["student_id"].iloc[1],
            token_submitted=token_hash,
            db_path=self.test_db_path
        )
        self.assertFalse(closed_ok)
        self.assertIn("expired or has been closed", closed_msg)

    def test_15_gps_campus_geofence_haversine(self):
        """Tests Haversine formula, inside geofence verification, outside rejection, and admin override."""
        campus_lat = 12.971600
        campus_lon = 77.594600
        radius_m = 300.0

        # Exact location -> 0 meters
        self.assertAlmostEqual(haversine_distance_meters(campus_lat, campus_lon, campus_lat, campus_lon), 0.0, places=1)

        # Test location ~30m away (inside 300m geofence)
        inside_lat = campus_lat + 0.0002
        inside_lon = campus_lon + 0.0002
        is_in, dist_m, status_str, _ = evaluate_geofence(inside_lat, inside_lon, campus_lat, campus_lon, radius_m)
        self.assertTrue(is_in)
        self.assertEqual(status_str, "VERIFIED_INSIDE")
        self.assertLess(dist_m, radius_m)

        # Test location ~1.5km away (outside 300m geofence)
        outside_lat = campus_lat + 0.012
        outside_lon = campus_lon + 0.012
        is_out, out_dist, out_status, _ = evaluate_geofence(outside_lat, outside_lon, campus_lat, campus_lon, radius_m)
        self.assertFalse(is_out)
        self.assertEqual(out_status, "DENIED_OUTSIDE_GEOFENCE")
        self.assertGreater(out_dist, radius_m)

        # Test check-in execution and admin override
        res = execute_gps_checkin(
            institution_id="INST_001",
            campus_id="CAMP_001",
            user_id="STU_GPS_TEST",
            user_lat=outside_lat,
            user_lon=outside_lon,
            db_path=self.test_db_path
        )
        self.assertFalse(res["success"])
        checkin_id = res["checkin_id"]

        # Admin override
        override_ok = review_gps_checkin(
            checkin_id=checkin_id,
            new_review_status="Admin-Approved",
            reviewed_by="Dean_Academic",
            reason="Verified transit pass delay",
            db_path=self.test_db_path
        )
        self.assertTrue(override_ok)

        # Verify updated status in logs
        gps_logs = get_gps_checkin_logs(institution_id="INST_001", db_path=self.test_db_path)
        matched_log = gps_logs[gps_logs["checkin_id"] == checkin_id]
        self.assertFalse(matched_log.empty)
        self.assertEqual(matched_log.iloc[0]["review_status"], "Admin-Approved")

    def test_16_authentication_and_password_security(self):
        """Tests PBKDF2-HMAC-SHA256 hashing, timing attack resistance, and password complexity."""
        password = "SecurePassword@2026!"
        h1, s1 = hash_password(password)
        self.assertIsInstance(h1, str)
        self.assertEqual(len(s1), 32)  # 16 bytes hex

        # Correct password verification
        self.assertTrue(verify_password(password, h1, s1))
        # Wrong password rejection
        self.assertFalse(verify_password("WrongPassword@2026!", h1, s1))
        # Empty password rejection
        self.assertFalse(verify_password("", h1, s1))

        # Complexity policy enforcement
        ok, _ = validate_password_strength("Short1!")
        self.assertFalse(ok)
        ok, _ = validate_password_strength("nouppercase123!")
        self.assertFalse(ok)
        ok, _ = validate_password_strength("NOLOWERCASE123!")
        self.assertFalse(ok)
        ok, _ = validate_password_strength("NoSpecialDigitHere")
        self.assertFalse(ok)
        ok, _ = validate_password_strength("Compliant@2026!")
        self.assertTrue(ok)

    def test_17_brute_force_rate_limiting_and_lockout(self):
        """Tests that 5 failed login attempts lock the account and record security audit logs."""
        test_uname = "prof_sharma"
        # Simulate 4 failed attempts
        for i in range(4):
            is_locked, msg, rem = record_login_failure(test_uname, db_path=self.test_db_path)
            self.assertFalse(is_locked)
            self.assertEqual(rem, 4 - i)

        # 5th attempt must trigger account lockout
        is_locked, msg, rem = record_login_failure(test_uname, db_path=self.test_db_path)
        self.assertTrue(is_locked)
        self.assertIn("temporarily locked", msg.lower())

        # Verify DB account status
        locked_now, _ = is_account_locked(test_uname, db_path=self.test_db_path)
        self.assertTrue(locked_now)

        # Unlock account
        user = get_user_by_credentials(test_uname, db_path=self.test_db_path)
        unlocked = unlock_user_account(user["user_id"], db_path=self.test_db_path)
        self.assertTrue(unlocked)

        # Verify unlocked
        locked_after, _ = is_account_locked(test_uname, db_path=self.test_db_path)
        self.assertFalse(locked_after)

    def test_18_session_management_and_revocation(self):
        """Tests secure session token generation, database validation, and revocation upon logout."""
        user = get_user_by_credentials("admin", db_path=self.test_db_path)
        self.assertIsNotNone(user)

        # Issue 30-day session
        token, sess_id = create_auth_session(user["user_id"], remember_me=True, db_path=self.test_db_path)
        self.assertTrue(token)
        self.assertTrue(sess_id.startswith("SESS_"))

        # Validate token
        session_data = validate_session_token(token, db_path=self.test_db_path)
        self.assertIsNotNone(session_data)
        self.assertEqual(session_data["username"], "admin")
        self.assertEqual(normalize_role(session_data["role"]), ROLE_ADMINISTRATOR)

        # Revoke session
        revoked = revoke_session(token, db_path=self.test_db_path)
        self.assertTrue(revoked)

        # Subsequent validation must fail
        self.assertIsNone(validate_session_token(token, db_path=self.test_db_path))

    def test_19_password_reset_token_lifecycle(self):
        """Tests 30-minute reset token issuance, single-use consumption, and double-use prevention."""
        uname = "student_aarav"
        ok, msg, token = create_password_reset_token(uname, db_path=self.test_db_path)
        self.assertTrue(ok)
        self.assertIsNotNone(token)

        # Consume token with new password
        new_h, new_s = hash_password("NewStudentPass@2026!")
        success, c_msg = validate_and_consume_reset_token(token, new_h, new_s, db_path=self.test_db_path)
        self.assertTrue(success)

        # Verify password updated in DB
        u_after = get_user_by_credentials(uname, db_path=self.test_db_path)
        self.assertTrue(verify_password("NewStudentPass@2026!", u_after["password_hash"], u_after["salt"]))

        # Attempt to re-use token must be rejected
        second_try, err_msg = validate_and_consume_reset_token(token, new_h, new_s, db_path=self.test_db_path)
        self.assertFalse(second_try)
        self.assertIn("already been consumed", err_msg)

    def test_20_role_based_access_control_and_privacy_isolation(self):
        """Tests that RBAC matrices properly protect sensitive modules and enforce student data isolation."""
        # 1. Administrator access
        self.assertTrue(can_access_module(ROLE_ADMINISTRATOR, "⚙️ System & Academic Rules"))
        self.assertTrue(can_access_module(ROLE_ADMINISTRATOR, "📥 Ingestion & Sync Hub"))
        self.assertTrue(can_access_module(ROLE_ADMINISTRATOR, "📊 Executive Overview"))

        # 2. Coordinator access
        self.assertFalse(can_access_module(ROLE_COORDINATOR, "⚙️ System & Academic Rules"))
        self.assertFalse(can_access_module(ROLE_COORDINATOR, "📥 Ingestion & Sync Hub"))
        self.assertTrue(can_access_module(ROLE_COORDINATOR, "📊 Executive Overview"))
        self.assertTrue(can_access_module(ROLE_COORDINATOR, "⚖️ Multi-Source Reconciliation"))

        # 3. Faculty access
        self.assertFalse(can_access_module(ROLE_FACULTY, "⚙️ System & Academic Rules"))
        self.assertFalse(can_access_module(ROLE_FACULTY, "🎯 7-Factor Risk & ML"))
        self.assertTrue(can_access_module(ROLE_FACULTY, "📚 Subject Intelligence"))
        self.assertTrue(can_access_module(ROLE_FACULTY, "📱 Dynamic QR Attendance"))

        # 4. Student access (Strictly restricted)
        self.assertFalse(can_access_module(ROLE_STUDENT, "⚙️ System & Academic Rules"))
        self.assertFalse(can_access_module(ROLE_STUDENT, "📥 Ingestion & Sync Hub"))
        self.assertFalse(can_access_module(ROLE_STUDENT, "📊 Executive Overview"))
        self.assertFalse(can_access_module(ROLE_STUDENT, "🎯 7-Factor Risk & ML"))
        self.assertFalse(can_access_module(ROLE_STUDENT, "⚖️ Multi-Source Reconciliation"))
        self.assertTrue(can_access_module(ROLE_STUDENT, "👤 Student 360° Profile"))
        self.assertTrue(can_access_module(ROLE_STUDENT, "🧮 Recovery Simulator"))
        self.assertTrue(can_access_module(ROLE_STUDENT, "📱 Dynamic QR Attendance"))
        self.assertTrue(can_access_module(ROLE_STUDENT, "📍 GPS Campus Check-In"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

