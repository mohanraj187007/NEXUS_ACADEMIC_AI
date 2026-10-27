"""
Reports & Export View
Generates downloadable PDF dossiers, CSV reports, and Excel (.xlsx) spreadsheets
for individual students and whole-class risk registries.
"""

import streamlit as st
import pandas as pd
import io
from analytics.attendance import calculate_student_summary, get_subject_wise_attendance
from analytics.risk_engine import calculate_student_risk, calculate_cohort_risk_registry
from reports.report_generator import generate_student_pdf, generate_student_csv, generate_class_csv
from utils.helpers import render_kpi_card, render_empty_state
from utils.auth_context import get_current_user, is_student


def render_reports_center(df: pd.DataFrame):
    """Renders the official reports and export center."""
    current_auth_user = get_current_user() or {}
    user_is_student = is_student()

    st.markdown('<div class="main-header-title">📄 Academic Reports & Export Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Export official PDF Dossiers, Excel spreadsheets, and CSV risk registries for accreditation and academic auditing</div>', unsafe_allow_html=True)

    if df.empty:
        render_empty_state("No attendance records available for report generation.")
        return

    # If Student role, hide class-wide risk registry export
    if user_is_student:
        tab_student = st.container()
        tab_class = None
    else:
        tab_student, tab_class = st.tabs(["👤 Student 360 PDF & CSV Dossier", "🏫 Class / Cohort Risk Registry Export"])

    # 1. Student Dossier Tab
    with tab_student:
        st.subheader("Generate Student Attendance & Risk Dossier")
        students_df = df[["student_id", "register_number", "student_name", "department"]].drop_duplicates().sort_values(by="register_number")
        s_options = {row["student_id"]: f"{row['register_number']} - {row['student_name']} ({row['department']})" for _, row in students_df.iterrows()}

        if user_is_student:
            stu_bound_id = current_auth_user.get("student_id")
            if stu_bound_id and stu_bound_id in s_options:
                selected_id = stu_bound_id
            elif list(s_options.keys()):
                selected_id = list(s_options.keys())[0]
            else:
                selected_id = None
            if selected_id:
                st.info(f"👤 Generating verified personal dossier for: **{s_options.get(selected_id, selected_id)}**")
        else:
            selected_id = st.selectbox(
                "Select Target Student for Report Generation:",
                options=list(s_options.keys()),
                format_func=lambda x: s_options[x],
                key="report_student_select"
            )

        if selected_id:
            summary = calculate_student_summary(df, selected_id)
            risk_res = calculate_student_risk(df, selected_id)
            subject_df = get_subject_wise_attendance(df, student_id=selected_id)

            col_rp1, col_rp2 = st.columns([1.2, 1])

            with col_rp1:
                st.markdown(f"""
                <div class="analysis-card">
                    <div style="font-size: 0.8rem; color: #94A3B8; font-weight: 600;">REPORT SUMMARY PREVIEW</div>
                    <div style="font-size: 1.2rem; font-weight: 800; color: #F8FAFC; margin-top: 4px;">{summary['student_name']}</div>
                    <div style="font-size: 0.85rem; color: #38BDF8;">{summary['register_number']} • {summary['department']}</div>
                    <hr style="border-color: rgba(255,255,255,0.08); margin: 8px 0;">
                    <div style="font-size: 0.85rem; color: #CBD5E1;">
                        <b>Attendance:</b> {summary['attendance_pct']}% ({summary['attended_classes']}/{summary['total_classes']} Classes)<br>
                        <b>Risk Score:</b> {risk_res['risk_score']}/100 ({risk_res['risk_level']})<br>
                        <b>Primary Risk Factor:</b> {risk_res['reasons'][0] if risk_res['reasons'] else 'None'}<br>
                        <b>Prescribed Action:</b> {risk_res['recommendations'][0] if risk_res['recommendations'] else 'Monitor'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col_rp2:
                st.markdown("##### 📥 Download Dossier Formats")
                
                # Generate PDF Bytes
                pdf_bytes = generate_student_pdf(summary, risk_res, subject_df)
                st.download_button(
                    label="📕 Download Official Student PDF Dossier",
                    data=pdf_bytes,
                    file_name=f"Attendance_Risk_Dossier_{summary['register_number']}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )

                # Generate CSV Bytes
                csv_bytes = generate_student_csv(summary, risk_res, subject_df)
                st.download_button(
                    label="📄 Download Student Data (CSV)",
                    data=csv_bytes,
                    file_name=f"Attendance_Data_{summary['register_number']}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

    # 2. Class / Cohort Registry Tab
    with tab_class:
        st.subheader("Export Complete Cohort Attendance & Risk Registry")
        risk_df = calculate_cohort_risk_registry(df)

        st.markdown(f"Generate full consolidated academic report containing **{len(risk_df)} students** across the filtered cohort.")

        col_c_dl1, col_c_dl2 = st.columns(2)
        with col_c_dl1:
            class_csv_bytes = generate_class_csv(risk_df)
            st.download_button(
                label="📊 Download Full Cohort Risk Registry (CSV)",
                data=class_csv_bytes,
                file_name="Cohort_Attendance_Risk_Registry.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True
            )

        with col_c_dl2:
            # Generate Excel Bytes
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                risk_df.to_excel(writer, index=False, sheet_name="Cohort_Risk_Registry")
            excel_bytes = excel_buffer.getvalue()

            st.download_button(
                label="📗 Download Cohort Risk Registry (Excel .xlsx)",
                data=excel_bytes,
                file_name="Cohort_Attendance_Risk_Registry.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### 🔍 Cohort Registry Preview:")
        st.dataframe(risk_df.head(10), use_container_width=True)
