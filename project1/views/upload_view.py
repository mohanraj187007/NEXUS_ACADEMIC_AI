"""
Universal Bulk Data Upload Centre & Audit Management View
Academic Attendance Pattern & Risk Analytics System
Supports CSV and Excel (.xlsx) imports across 9 institutional categories with a 12-step validation
workflow: category selection, official template downloads, schema normalization, preview,
row-level validation, duplicate detection, cancel/confirm dialogs, and transactional commit.
"""

import streamlit as st
import pandas as pd
import io
import json
import datetime
from typing import Dict, Any, Optional
from database.database import (
    get_all_students, record_manual_attendance_correction,
    get_audit_logs, get_import_history, get_full_attendance_dataset, DB_PATH
)
from utils.importer import (
    IMPORT_CATEGORIES, CATEGORY_SCHEMAS, generate_category_template,
    validate_and_prepare_batch, commit_prepared_batch
)
from utils.auth_context import get_current_user, can_import_data
from utils.helpers import render_kpi_card, render_empty_state


def render_data_upload():
    """Renders the 9-category Bulk Data Upload Centre with full 12-step validation workflow."""
    current_user = get_current_user()
    inst_id = current_user.get("institution_id", "INST_001")
    user_role = current_user.get("role", "College Admin")
    user_name = current_user.get("user_name", "Academic Administrator")

    st.markdown('<div class="main-header-title">📥 Bulk Data Upload Centre & Provenance Management</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Import institutional data supporting CSV and Excel (.xlsx) across 9 categories with 12-step validation, preview, duplicate detection, and transactional commit</div>', unsafe_allow_html=True)

    tab_upload, tab_manual, tab_history, tab_audit = st.tabs([
        "📤 Universal Bulk Ingestion (CSV / XLSX)",
        "✏️ Authorized Manual Correction",
        "📜 Import Execution History",
        "🛡️ Immutable Audit Ledger"
    ])

    # =========================================================================
    # TAB 1: UNIVERSAL BULK INGESTION
    # =========================================================================
    with tab_upload:
        if not can_import_data():
            st.warning("⚠️ Insufficient permissions: Data ingestion is restricted to Super Admin, College Admin, and Campus Admin roles.")
            return

        # 1. Category Selection
        c_cat1, c_cat2 = st.columns([1.5, 1])
        with c_cat1:
            selected_category = st.selectbox(
                "1. Select Institutional Data Category to Ingest:",
                options=list(IMPORT_CATEGORIES.keys()),
                format_func=lambda x: f"📁 {IMPORT_CATEGORIES[x]}",
                key="bulk_upload_category"
            )

        with c_cat2:
            st.markdown("###### 📥 Download Official Sample Templates")
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                csv_bytes = generate_category_template(selected_category, file_format="csv")
                st.download_button(
                    label="📄 Sample CSV",
                    data=csv_bytes,
                    file_name=f"Template_{selected_category}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with c_d2:
                xlsx_bytes = generate_category_template(selected_category, file_format="xlsx")
                st.download_button(
                    label="📊 Sample Excel (.xlsx)",
                    data=xlsx_bytes,
                    file_name=f"Template_{selected_category}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        # Category Schema Description
        schema = CATEGORY_SCHEMAS.get(selected_category, {})
        req_cols = schema.get("required", [])
        all_cols = schema.get("columns", [])
        st.markdown(f"""
        <div class="analysis-card" style="margin-top: 0.5rem; margin-bottom: 1rem;">
            <b style="color: #38BDF8;">📋 Schema Specification for {IMPORT_CATEGORIES.get(selected_category, selected_category)}:</b><br>
            <span style="color: #CBD5E1; font-size: 0.85rem; line-height: 1.6;">
            <b>Mandatory Columns:</b> <code>{", ".join(req_cols)}</code><br>
            <b>Supported Columns:</b> <code>{", ".join(all_cols)}</code>
            </span>
        </div>
        """, unsafe_allow_html=True)

        # 2. File Upload Box
        uploaded_file = st.file_uploader(
            f"2. Upload {IMPORT_CATEGORIES.get(selected_category)} File (CSV or Excel):",
            type=["csv", "xlsx", "xls"],
            key=f"file_uploader_{selected_category}"
        )

        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            file_name = uploaded_file.name

            # Run 12-Step Validation Engine
            is_valid, summary, valid_df = validate_and_prepare_batch(
                file_bytes=file_bytes,
                file_name=file_name,
                category=selected_category,
                institution_id=inst_id,
                db_path=DB_PATH
            )

            # Store in session state for confirmation workflow
            st.session_state["pending_batch"] = {
                "valid": is_valid,
                "summary": summary,
                "valid_df": valid_df,
                "category": selected_category,
                "file_name": file_name
            }

            st.markdown("---")
            st.markdown("##### 🔍 12-Step Validation & Inspection Report")

            # KPI Summary Grid
            k1, k2, k3, k4, k5 = st.columns(5)
            with k1:
                render_kpi_card("Total Rows", f"{summary['total_raw']}", "In File", "blue")
            with k2:
                render_kpi_card("Valid Records", f"{summary['valid_count']}", "Passed Schema", "green")
            with k3:
                inv_color = "red" if summary["invalid_count"] > 0 else "green"
                render_kpi_card("Invalid Rows", f"{summary['invalid_count']}", "Failed Rules", inv_color)
            with k4:
                render_kpi_card("Duplicates", f"{summary['duplicate_count']}", "Deduplicated", "yellow")
            with k5:
                render_kpi_card("Ready to Commit", f"{len(valid_df)}", "Staged for DB", "purple")

            # Display Error Report if rows failed
            if summary["invalid_count"] > 0:
                st.markdown(f"###### ⚠️ Row-Level Validation Errors ({len(summary['row_errors'])})")
                err_df = pd.DataFrame(summary["row_errors"])
                st.dataframe(
                    err_df.rename(columns={
                        "row": "Row #",
                        "id": "Identifier",
                        "field": "Violated Field",
                        "error": "Error Description",
                        "raw_val": "Submitted Value"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

                # Download Error Report Button
                err_json = json.dumps(summary["row_errors"], indent=2)
                st.download_button(
                    label="📥 Download Detailed Error Report (JSON)",
                    data=err_json,
                    file_name=f"ErrorReport_{selected_category}_{summary['batch_id']}.json",
                    mime="application/json"
                )

            # Preview Valid Records
            if not valid_df.empty:
                st.markdown(f"###### 👁️ Preview Validated Records (Showing first {min(10, len(valid_df))} of {len(valid_df)} rows)")
                st.dataframe(valid_df.head(10), use_container_width=True, hide_index=True)

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("##### 🚦 Confirmation & Transactional Execution")

                c_confirm, c_cancel = st.columns([1.2, 1])
                with c_confirm:
                    if st.button(f"💾 Explicitly Confirm & Commit {len(valid_df)} Valid Records to Database", type="primary", use_container_width=True):
                        operator_sig = f"{user_name} ({user_role})"
                        success, commit_msg = commit_prepared_batch(
                            valid_df=valid_df,
                            category=selected_category,
                            batch_id=summary["batch_id"],
                            institution_id=inst_id,
                            performed_by=operator_sig,
                            file_name=file_name,
                            db_path=DB_PATH
                        )
                        if success:
                            st.success(f"🎉 Transaction committed successfully! {commit_msg}")
                            del st.session_state["pending_batch"]
                            st.rerun()
                        else:
                            st.error(f"❌ Transaction rolled back: {commit_msg}")

                with c_cancel:
                    if st.button("❌ Cancel Upload & Discard Staged Batch", use_container_width=True):
                        if "pending_batch" in st.session_state:
                            del st.session_state["pending_batch"]
                        st.info("Batch cancelled. No changes were committed.")
                        st.rerun()
            else:
                st.error("❌ No valid records remain to commit. Please review the row-level errors above, fix your file, and re-upload.")

    # =========================================================================
    # TAB 2: AUTHORIZED MANUAL RECORD CORRECTION
    # =========================================================================
    with tab_manual:
        st.markdown("##### ✏️ Authorized Attendance Record Correction")
        st.caption("Apply official corrections to individual attendance logs with mandatory justification and an immutable audit trail.")

        # Search existing attendance records
        att_df = get_full_attendance_dataset(filters={"institution_id": inst_id})
        if att_df.empty:
            render_empty_state("No Attendance Records Available to Correct", "Import attendance records using the bulk upload portal.")
        else:
            search_stu = st.text_input("Search by Register Number or Student Name:", "")
            filtered_att = att_df.copy()
            if search_stu.strip():
                q = search_stu.strip().lower()
                filtered_att = filtered_att[
                    filtered_att["register_number"].astype(str).str.lower().str.contains(q) |
                    filtered_att["student_name"].astype(str).str.lower().str.contains(q)
                ]

            if filtered_att.empty:
                st.info("No matching records found for search query.")
            else:
                st.dataframe(
                    filtered_att[[
                        "attendance_id", "date", "hour", "register_number",
                        "student_name", "subject_code", "status", "verification_method", "is_manually_corrected"
                    ]].head(25).rename(columns={
                        "attendance_id": "Log ID",
                        "date": "Date",
                        "hour": "Hour",
                        "register_number": "Reg #",
                        "student_name": "Student",
                        "subject_code": "Course",
                        "status": "Current Status",
                        "verification_method": "Method",
                        "is_manually_corrected": "Corrected?"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

                st.markdown("---")
                st.markdown("###### 📝 Submit Official Status Correction")
                with st.form("manual_correction_form"):
                    f_c1, f_c2, f_c3 = st.columns(3)
                    with f_c1:
                        target_log_id = st.number_input("Target Attendance Log ID:", min_value=1, value=int(filtered_att["attendance_id"].iloc[0]))
                    with f_c2:
                        new_status_val = st.selectbox("New Attendance Status:", ["Present", "Absent", "Late", "Excused", "Approved Leave"])
                    with f_c3:
                        reason_text = st.text_input("Mandatory Official Justification:", "Medical certificate approved by Department Head")

                    if st.form_submit_button("💾 Save Correction with Audit Trail", type="primary"):
                        if not reason_text.strip():
                            st.error("A justification is required for every manual correction.")
                        else:
                            operator_sig = f"{user_name} ({user_role})"
                            res = record_manual_attendance_correction(
                                attendance_id=int(target_log_id),
                                new_status=new_status_val,
                                reason=reason_text.strip(),
                                performed_by=operator_sig,
                                institution_id=inst_id,
                                db_path=DB_PATH
                            )
                            if res:
                                st.success(f"Log #{target_log_id} successfully updated to '{new_status_val}' with permanent audit trail!")
                                st.rerun()
                            else:
                                st.error("Failed to update record. Verify that the Log ID exists.")

    # =========================================================================
    # TAB 3: IMPORT EXECUTION HISTORY
    # =========================================================================
    with tab_history:
        st.markdown("##### 📜 Historical Bulk Upload Executions")
        hist_df = get_import_history(institution_id=inst_id, limit=50)
        if hist_df.empty:
            render_empty_state("No Import Executions Recorded", "Import executions and summaries will appear here once bulk files are committed.")
        else:
            st.dataframe(
                hist_df[[
                    "import_id", "data_category", "file_name", "total_rows",
                    "valid_rows", "invalid_rows", "duplicate_rows", "status", "performed_by", "timestamp"
                ]].rename(columns={
                    "import_id": "Import ID",
                    "data_category": "Category",
                    "file_name": "File Name",
                    "total_rows": "Total Rows",
                    "valid_rows": "Valid",
                    "invalid_rows": "Invalid",
                    "duplicate_rows": "Deduplicated",
                    "status": "Outcome",
                    "performed_by": "Operator",
                    "timestamp": "Execution Time"
                }),
                use_container_width=True,
                hide_index=True
            )

    # =========================================================================
    # TAB 4: IMMUTABLE AUDIT LEDGER
    # =========================================================================
    with tab_audit:
        st.markdown("##### 🛡️ Immutable Institutional Audit Trail")
        st.caption("Permanent record of all data modifications, bulk uploads, QR sessions, GPS validations, and manual corrections.")

        audit_df = get_audit_logs(institution_id=inst_id, limit=100)
        if audit_df.empty:
            render_empty_state("No Audit Events Logged", "Audit events will automatically accumulate as administrative actions occur.")
        else:
            st.dataframe(
                audit_df[[
                    "log_id", "action_type", "table_affected", "record_id",
                    "old_value", "new_value", "performed_by", "timestamp", "details"
                ]].rename(columns={
                    "log_id": "Audit ID",
                    "action_type": "Action",
                    "table_affected": "Entity",
                    "record_id": "Record ID",
                    "old_value": "Old State",
                    "new_value": "New State",
                    "performed_by": "Actor",
                    "timestamp": "Timestamp",
                    "details": "Details / Evidence"
                }),
                use_container_width=True,
                hide_index=True
            )
