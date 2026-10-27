"""
Student 360 Analysis View
Comprehensive individual student drilldown: profile, streaks, gauge risk score,
weekly trend line, subject breakdown, class benchmarking, ML risk attribution,
and chronological session attendance history with filters and pagination.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from analytics.attendance import (
    calculate_student_summary, get_subject_wise_attendance, 
    get_weekly_attendance_trend, get_class_benchmarks
)
from analytics.risk_engine import calculate_student_risk
from analytics.trend_analysis import analyze_student_trend
from analytics.pattern_detection import get_all_student_patterns
from analytics.anomaly_detection import detect_student_anomaly
from analytics.ml_risk_model import predict_student_risk_ml
from database.database import get_setting
from utils.helpers import render_kpi_card, get_risk_badge, format_plotly_theme, render_empty_state
from utils.importer import (
    parse_student_roster_file, generate_student_sample_template, save_students_and_seed_attendance
)
from utils.auth_context import get_current_user, is_student


def _render_student_upload_portal():
    """Renders the bulk and quick student enrollment portal for administrators and faculty."""
    with st.expander("📤 Upload & Register Students (Excel / CSV / PDF) | ➕ Quick Add Student", expanded=False):
        st.markdown("""
        <div style="font-size: 0.88rem; color: #CBD5E1; margin-bottom: 0.8rem;">
            Upload your college student list from an <b>Excel spreadsheet (.xlsx, .xls)</b>, <b>CSV file (.csv)</b>, or <b>PDF document (.pdf)</b>.
            The system automatically registers them to <b>VSB Engineering College, Karur</b> and seeds attendance logs so their complete 360° analytics, streaks, and risk scores are instantly visible.
        </div>
        """, unsafe_allow_html=True)

        tab_bulk, tab_quick = st.tabs(["📁 Bulk Upload (Excel / PDF / CSV)", "➕ Quick Add Student"])

        with tab_bulk:
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                sample_xlsx = generate_student_sample_template("xlsx")
                st.download_button(
                    label="📥 Download Sample Excel Template (.xlsx)",
                    data=sample_xlsx,
                    file_name="vsb_student_roster_sample.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with c_d2:
                sample_csv = generate_student_sample_template("csv")
                st.download_button(
                    label="📥 Download Sample CSV Template (.csv)",
                    data=sample_csv,
                    file_name="vsb_student_roster_sample.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            uploaded_roster = st.file_uploader(
                "Select Student List File (.xlsx, .xls, .csv, .pdf):",
                type=["xlsx", "xls", "csv", "pdf"],
                key="student_roster_uploader"
            )

            if uploaded_roster is not None:
                success, parsed_df, parse_msg = parse_student_roster_file(
                    uploaded_roster.getvalue(),
                    uploaded_roster.name
                )
                if not success:
                    st.error(f"❌ {parse_msg}")
                else:
                    st.success(f"✅ {parse_msg}")
                    st.markdown(f"<b>Preview of Extracted Students ({len(parsed_df)} records):</b>", unsafe_allow_html=True)
                    st.dataframe(parsed_df, use_container_width=True, height=180)

                    c_opt1, c_opt2 = st.columns(2)
                    with c_opt1:
                        target_profile = st.selectbox(
                            "Baseline Attendance Profile to Initialize:",
                            options=[
                                ("REGULAR", "REGULAR (Healthy ~88% Attendance)"),
                                ("HIGH", "HIGH (Honors ~95% Attendance)"),
                                ("WARNING", "WARNING (Borderline ~72% Attendance)"),
                                ("CRITICAL", "CRITICAL (At-Risk ~54% Attendance)")
                            ],
                            format_func=lambda x: x[1],
                            index=0,
                            key="roster_profile_choice"
                        )
                    with c_opt2:
                        seed_attendance = st.checkbox(
                            "Generate multi-week baseline attendance records",
                            value=True,
                            help="Generates historical session records across subjects so streak analytics, trend lines, and risk metrics display immediately."
                        )

                    if st.button("🚀 Register & Activate Students in 360° Profile", key="btn_commit_roster", use_container_width=True):
                        with st.spinner("Registering students and seeding institutional attendance dataset..."):
                            count_s, count_a, res_msg = save_students_and_seed_attendance(
                                parsed_df,
                                institution_id="INST_001",
                                generate_attendance=seed_attendance,
                                attendance_profile=target_profile[0]
                            )
                            if count_s > 0:
                                st.session_state["target_student_id"] = parsed_df.iloc[0]["student_id"]
                                st.success(res_msg)
                                st.rerun()
                            else:
                                st.error(res_msg)

        with tab_quick:
            st.markdown("<div style='font-size: 0.85rem; color: #94A3B8; margin-bottom: 0.6rem;'>Quickly enroll a student into VSB Engineering College and jump straight to their 360° profile:</div>", unsafe_allow_html=True)
            qc1, qc2 = st.columns(2)
            with qc1:
                q_name = st.text_input("Student Name:", value="Monish K", key="q_student_name")
                q_reg = st.text_input("Register Number:", value="22CS101", key="q_student_reg")
                q_dept = st.selectbox(
                    "Department:",
                    options=[
                        "Computer Science & Engineering",
                        "Information Technology",
                        "Artificial Intelligence & Data Science",
                        "Electronics & Communication Engineering",
                        "Mechanical Engineering",
                        "Civil Engineering"
                    ],
                    index=0,
                    key="q_student_dept"
                )
            with qc2:
                q_year = st.selectbox("Academic Year:", [1, 2, 3, 4], index=1, key="q_student_year")
                q_sem = st.selectbox("Semester:", [1, 2, 3, 4, 5, 6, 7, 8], index=2, key="q_student_sem")
                q_sec = st.selectbox("Section:", ["A", "B", "C"], index=0, key="q_student_sec")
                q_profile = st.selectbox(
                    "Initial Attendance Health:",
                    options=[
                        ("REGULAR", "REGULAR (Healthy ~88%)"),
                        ("HIGH", "HIGH (Honors ~95%)"),
                        ("WARNING", "WARNING (Borderline ~72%)"),
                        ("CRITICAL", "CRITICAL (At-Risk ~54%)")
                    ],
                    format_func=lambda x: x[1],
                    index=0,
                    key="q_profile_choice"
                )

            if st.button("➕ Register Single Student & Inspect 360°", key="btn_quick_register", use_container_width=True):
                clean_reg = q_reg.strip().upper()
                clean_name = q_name.strip()
                if not clean_reg or not clean_name:
                    st.error("Please enter both Student Name and Register Number.")
                else:
                    single_stu_id = f"STU_{clean_reg}"
                    df_single = pd.DataFrame([{
                        "student_id": single_stu_id,
                        "register_number": clean_reg,
                        "name": clean_name,
                        "department": q_dept,
                        "year": q_year,
                        "semester": q_sem,
                        "section": q_sec,
                        "email": f"{clean_name.split()[0].lower()}.{clean_reg.lower()}@vsbec.com"
                    }])
                    with st.spinner(f"Registering {clean_name} to VSB Engineering College..."):
                        count_s, count_a, res_msg = save_students_and_seed_attendance(
                            df_single,
                            institution_id="INST_001",
                            generate_attendance=True,
                            attendance_profile=q_profile[0]
                        )
                        st.session_state["target_student_id"] = single_stu_id
                        st.success(res_msg)
                        st.rerun()


def render_student_analysis(df: pd.DataFrame, default_student_id: str = None):
    """Renders the comprehensive Student 360 Analysis page."""
    current_auth_user = get_current_user() or {}
    user_is_student = is_student()

    st.markdown('<div class="main-header-title">👤 Student 360 Attendance & Risk Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">In-depth behavioral diagnostics, streak intelligence, subject vulnerabilities, and recovery requirements</div>', unsafe_allow_html=True)

    # 0. College Student Ingestion & Management Portal (Hidden from Student persona for privacy & governance)
    if not user_is_student:
        _render_student_upload_portal()


    if df.empty:
        render_empty_state("No attendance records available for individual student inspection. Use the upload panel above to import students from Excel or PDF.")
        return

    thresh = float(get_setting("mandatory_attendance_pct", 75.0))

    # Student Selection List
    students_df = df[["student_id", "register_number", "student_name", "department"]].drop_duplicates().sort_values(by="register_number")
    student_options = {
        row["student_id"]: f"{row['register_number']} - {row['student_name']} ({row['department']})"
        for _, row in students_df.iterrows()
    }
    
    student_ids = list(student_options.keys())

    if user_is_student:
        # Student is strictly locked to their own assigned student_id
        stu_bound_id = current_auth_user.get("student_id")
        if stu_bound_id and stu_bound_id in student_ids:
            selected_student_id = stu_bound_id
        elif student_ids:
            selected_student_id = student_ids[0]
        else:
            selected_student_id = None

        if selected_student_id:
            st.markdown(f"""
            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 0.7rem 1rem; margin-bottom: 1.2rem; display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <span style="font-size: 0.72rem; font-weight: 700; color: #34D399; text-transform: uppercase; letter-spacing: 0.08em;">STUDENT PRIVACY BOUNDARY ACTIVE</span>
                    <div style="font-size: 0.95rem; font-weight: 800; color: #F8FAFC;">{student_options.get(selected_student_id, selected_student_id)}</div>
                </div>
                <div style="font-size: 0.72rem; color: #A7F3D0; background: rgba(16, 185, 129, 0.2); padding: 4px 10px; border-radius: 20px;">
                    🔒 Private Dossier
                </div>
            </div>
            """, unsafe_allow_html=True)
        st.session_state["target_student_id"] = selected_student_id
    else:
        target_id = st.session_state.get("target_student_id") or default_student_id
        default_idx = 0
        if target_id and target_id in student_ids:
            default_idx = student_ids.index(target_id)

        selected_student_id = st.selectbox(
            "🔍 Select or Search Student:",
            options=student_ids,
            index=default_idx,
            format_func=lambda x: student_options[x]
        )

        if selected_student_id != target_id:
            st.session_state["target_student_id"] = selected_student_id

    if not selected_student_id:
        return

    # Fetch all analytical dimensions for selected student
    student_records = df[df["student_id"] == selected_student_id]
    summary = calculate_student_summary(df, selected_student_id)
    risk_res = calculate_student_risk(df, selected_student_id, target_threshold=thresh)
    trend_res = analyze_student_trend(df, selected_student_id)
    patterns = get_all_student_patterns(student_records)
    benchmarks = get_class_benchmarks(df, selected_student_id)
    anomaly_res = detect_student_anomaly(df, selected_student_id)
    subject_df = get_subject_wise_attendance(df, student_id=selected_student_id)
    ml_pred = predict_student_risk_ml(df, selected_student_id)

    st.markdown("<br>", unsafe_allow_html=True)

    # 1. Student Profile & High-Level KPIs
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.2])

    with c1:
        st.markdown(f"""
        <div class="analysis-card">
            <div style="font-size: 0.8rem; color: #94A3B8; font-weight: 600;">STUDENT PROFILE</div>
            <div style="font-size: 1.3rem; font-weight: 800; color: #F8FAFC; margin: 4px 0;">{summary['student_name']}</div>
            <div style="font-size: 0.85rem; color: #38BDF8; font-weight: 600;">{summary['register_number']}</div>
            <div style="font-size: 0.8rem; color: #94A3B8; margin-top: 6px;">
                {summary['department']} • Year {summary['year']} (Sem {summary.get('semester', 1)})
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        att_pct = summary["attendance_pct"]
        border_c = "#10B981" if att_pct >= 80 else ("#F59E0B" if att_pct >= thresh else "#EF4444")
        render_kpi_card(
            "Attendance %",
            f"{att_pct}%",
            f"{summary['attended_classes']}/{summary['total_classes']} Eligible Sessions",
            border_color=border_c
        )

    with c3:
        render_kpi_card(
            "Risk Score",
            f"{risk_res['risk_score']}/100",
            f"Category: {risk_res['risk_level']}",
            border_color=risk_res["risk_color"]
        )

    with c4:
        trend_dir = trend_res["trend_direction"]
        trend_c = "#10B981" if trend_dir == "Improving" else ("#EF4444" if "Decline" in trend_dir else "#38BDF8")
        render_kpi_card(
            "Trend Intelligence",
            trend_dir,
            f"Δ {trend_res['change_pct']:+.1f}% vs prior baseline",
            border_color=trend_c
        )

    # 2. Streak Cards Row
    st.markdown("#### ⚡ Attendance Streaks & Operational Health")
    streaks = patterns["streaks"]
    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    with s_col1:
        render_kpi_card("Current Present Streak", f"{streaks['current_present_streak']} classes", "Active presence streak", border_color="#10B981")
    with s_col2:
        render_kpi_card("Current Absence Streak", f"{streaks['current_absence_streak']} classes", "Active consecutive absence", border_color="#EF4444" if streaks['current_absence_streak'] > 0 else "#64748B")
    with s_col3:
        render_kpi_card("Late Arrivals Logged", f"{summary.get('late_classes', 0)} sessions", "Arrived after grace period", border_color="#818CF8")
    with s_col4:
        render_kpi_card("Excused Leaves", f"{summary.get('excused_classes', 0)} sessions", "Approved medical/duty leaves", border_color="#A855F7")

    # 3. Anomaly Notification Banner (if any)
    if anomaly_res["has_anomaly"]:
        st.markdown(f"""
        <div style="background: rgba(153, 27, 27, 0.25); border: 1px solid #EF4444; border-radius: 10px; padding: 0.8rem 1.2rem; margin-bottom: 1.2rem;">
            <b style="color: #F87171;">⚠️ Attendance Anomaly Detected:</b> {anomaly_res['description']}
        </div>
        """, unsafe_allow_html=True)

    # 4. Weekly Trend Line & Class Benchmarking Charts
    col_chart_left, col_chart_right = st.columns([1.3, 1])

    with col_chart_left:
        st.subheader("📈 Historical Weekly Trajectory")
        weekly_df = trend_res["weekly_data"]
        if not weekly_df.empty:
            fig_w = go.Figure()
            fig_w.add_trace(go.Scatter(
                x=weekly_df["week"],
                y=weekly_df["attendance_pct"],
                mode="lines+markers",
                name="Student Attendance %",
                line=dict(color="#38BDF8", width=3, shape="spline"),
                marker=dict(size=8, color="#818CF8")
            ))
            fig_w.add_hline(
                y=thresh,
                line_dash="dash",
                line_color="#EF4444",
                annotation_text=f"{thresh:.0f}% Mandatory Benchmark",
                annotation_position="bottom right"
            )
            fig_w.update_xaxes(title="Academic Week", dtick=1)
            fig_w.update_yaxes(title="Attendance %", range=[0, 105])
            format_plotly_theme(fig_w, height=300)
            st.plotly_chart(fig_w, use_container_width=True)

    with col_chart_right:
        st.subheader("📊 Cohort Peer Benchmarks")
        b_labels = ["Student", "Section Avg", "Dept Avg", "Class Avg"]
        b_vals = [benchmarks["student_pct"], benchmarks["section_avg"], benchmarks["dept_avg"], benchmarks["class_avg"]]
        b_colors = ["#38BDF8" if benchmarks["student_pct"] >= thresh else "#EF4444", "#818CF8", "#A855F7", "#64748B"]

        fig_b = go.Figure(go.Bar(
            x=b_labels,
            y=b_vals,
            marker_color=b_colors,
            text=[f"{v:.1f}%" for v in b_vals],
            textposition="outside"
        ))
        fig_b.add_hline(y=thresh, line_dash="dash", line_color="#EF4444")
        fig_b.update_yaxes(range=[0, 105], title="Attendance %")
        format_plotly_theme(fig_b, height=300)
        st.plotly_chart(fig_b, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Explainable Risk Diagnostics & Interventions
    c_diag1, c_diag2 = st.columns(2)

    with c_diag1:
        st.markdown(f"""
        <div class="analysis-card">
            <div style="font-size: 0.95rem; font-weight: 700; color: #F59E0B; margin-bottom: 0.6rem;">
                EXPLAINABLE RISK DRIVERS
            </div>
            <ul style="margin: 0; padding-left: 1.2rem; color: #CBD5E1; font-size: 0.88rem; line-height: 1.6;">
                {"".join([f"<li style='margin-bottom: 0.3rem;'>{r}</li>" for r in risk_res['reasons']])}
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with c_diag2:
        st.markdown(f"""
        <div class="action-card">
            <div style="font-size: 0.95rem; font-weight: 700; color: #60A5FA; margin-bottom: 0.6rem;">
                RECOMMENDED SUPPORTIVE INTERVENTIONS
            </div>
            <ul style="margin: 0; padding-left: 1.2rem; color: #E2E8F0; font-size: 0.88rem; line-height: 1.6;">
                {"".join([f"<li style='margin-bottom: 0.3rem;'>{rec}</li>" for rec in risk_res['recommendations']])}
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # ML Model Attribution Card
    if ml_pred.get("status") == "PREDICTED":
        st.markdown("<br>", unsafe_allow_html=True)
        prob = ml_pred["ml_risk_probability"]
        pred_label = ml_pred["ml_prediction"]
        pred_color = "#EF4444" if pred_label == "AT_RISK" else "#10B981"
        st.markdown(f"""
        <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 1rem 1.2rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <b style="color: #A855F7;">🤖 Machine Learning Risk Attribution (Random Forest Classifier)</b>
                <span style="background: rgba(255,255,255,0.06); padding: 0.2rem 0.6rem; border-radius: 6px; font-weight: 700; font-size: 0.8rem; color: {pred_color};">
                    Predicted: {pred_label} (Probability: {prob}%)
                </span>
            </div>
            <div style="color: #94A3B8; font-size: 0.82rem; margin-top: 6px;">
                <b>Top Model Factors for this student:</b> {", ".join(ml_pred['contributing_reasons']) if ml_pred['contributing_reasons'] else 'Metrics indicate standard compliant trajectory.'}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 6. Subject-Wise Breakdown Table
    st.subheader("📚 Subject-Wise Attendance Breakdown")
    if not subject_df.empty:
        c_sub_table, c_sub_bar = st.columns([1.3, 1])
        with c_sub_table:
            display_sub = subject_df[[
                "subject_code", "subject_name", "faculty_name", "total_classes", "attended", "missed", "attendance_pct", "risk_level"
            ]].copy()
            display_sub.columns = ["Code", "Subject Name", "Faculty", "Total", "Attended", "Missed", "Att %", "Risk Tier"]
            st.dataframe(
                display_sub.style.map(
                    lambda v: "color: #EF4444; font-weight: bold;" if v == "Critical Risk" else ("color: #F59E0B; font-weight: bold;" if v == "High Risk" else "color: #10B981;"),
                    subset=["Risk Tier"]
                ),
                use_container_width=True,
                height=260
            )

        with c_sub_bar:
            fig_s = px.bar(
                subject_df,
                x="attendance_pct",
                y="subject_code",
                orientation="h",
                color="risk_level",
                color_discrete_map={
                    "Low Risk": "#10B981",
                    "Moderate Risk": "#F59E0B",
                    "High Risk": "#EF4444",
                    "Critical Risk": "#991B1B"
                },
                text="attendance_pct",
                hover_data=["subject_name"]
            )
            fig_s.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_s.add_vline(x=thresh, line_dash="dash", line_color="#EF4444")
            fig_s.update_xaxes(title="Attendance %", range=[0, 105])
            fig_s.update_yaxes(title="Subject")
            format_plotly_theme(fig_s, height=260)
            st.plotly_chart(fig_s, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 7. Chronological Session Attendance Log with Filtering & Pagination
    st.subheader("📅 Chronological Session Attendance Log")
    col_hist_f1, col_hist_f2 = st.columns(2)
    with col_hist_f1:
        hist_sub = st.selectbox("Filter Subject:", ["All"] + sorted(student_records["subject_code"].dropna().unique().tolist()))
    with col_hist_f2:
        hist_status = st.selectbox("Filter Status:", ["All"] + sorted(student_records["status"].dropna().unique().tolist()))

    filtered_hist = student_records.copy()
    if hist_sub != "All":
        filtered_hist = filtered_hist[filtered_hist["subject_code"] == hist_sub]
    if hist_status != "All":
        filtered_hist = filtered_hist[filtered_hist["status"] == hist_status]

    hist_total = len(filtered_hist)
    h_page_size = 15
    h_pages = max(1, (hist_total + h_page_size - 1) // h_page_size)
    h_col1, h_col2 = st.columns([1, 4])
    with h_col1:
        h_page = st.number_input("Log Page:", min_value=1, max_value=h_pages, value=1, step=1, key="hist_page")
    with h_col2:
        st.markdown(f"<div style='margin-top: 1.8rem; font-size: 0.85rem; color: #94A3B8;'>Showing {(h_page-1)*h_page_size + 1}–{min(h_page*h_page_size, hist_total)} of {hist_total} session records</div>", unsafe_allow_html=True)

    h_start = (h_page - 1) * h_page_size
    h_end = h_start + h_page_size
    paged_hist = filtered_hist.iloc[h_start:h_end]

    cols_to_show = ["date", "hour", "subject_code", "subject_name", "status"]
    for opt_c in ["scheduled_start_time", "check_in_time", "source_system", "is_manually_corrected"]:
        if opt_c in paged_hist.columns:
            cols_to_show.append(opt_c)

    st.dataframe(
        paged_hist[cols_to_show].style.map(
            lambda v: "color: #10B981; font-weight: bold;" if v == "Present" else ("color: #EF4444; font-weight: bold;" if v == "Absent" else "color: #F59E0B;"),
            subset=["status"]
        ),
        use_container_width=True,
        height=320
    )
