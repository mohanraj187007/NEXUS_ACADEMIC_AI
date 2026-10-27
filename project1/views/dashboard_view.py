"""
Dashboard View
Executive-level academic monitoring dashboard displaying top KPI cards,
multi-campus infrastructure counts, capacity breach alerts, risk distribution,
trend trajectories, at-risk rosters with search and pagination, department comparisons,
and recent import execution history.
"""

import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go
from analytics.attendance import (
    calculate_overall_metrics, get_weekly_attendance_trend, 
    get_subject_wise_attendance, get_department_wise_attendance
)
from analytics.risk_engine import calculate_cohort_risk_registry
from analytics.trend_analysis import get_cohort_trend_distribution
from analytics.anomaly_detection import scan_cohort_anomalies
from database.database import (
    get_setting, get_database_summary, get_capacity_breach_alerts,
    get_import_history, get_timetable_sessions, get_campuses, get_rooms, get_departments
)
from utils.auth_context import get_current_user
from utils.helpers import render_kpi_card, get_risk_badge, format_plotly_theme, render_empty_state


def render_dashboard(df: pd.DataFrame):
    """Renders the executive dashboard page."""
    current_user = get_current_user()
    inst_id = current_user.get("institution_id", "INST_001")

    st.markdown('<div class="main-header-title">📊 Academic Attendance & Institutional Risk Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Real-time multi-campus attendance health, facility capacity oversight, predictive risk distribution, and import provenance</div>', unsafe_allow_html=True)

    # 1. Fetch Multi-Campus Infrastructure Context
    campuses_df = get_campuses(institution_id=inst_id)
    rooms_df = get_rooms(institution_id=inst_id)
    depts_df = get_departments(institution_id=inst_id)
    tt_df = get_timetable_sessions(institution_id=inst_id)
    breach_df = get_capacity_breach_alerts(institution_id=inst_id)
    history_df = get_import_history(institution_id=inst_id, limit=5)

    total_campuses = len(campuses_df)
    total_rooms = len(rooms_df)
    total_depts = len(depts_df)
    total_breaches = len(breach_df)

    # Today's scheduled classes count
    today_name = datetime.date.today().strftime("%A")
    today_sessions = tt_df[tt_df["day_of_week"] == today_name] if not tt_df.empty and "day_of_week" in tt_df.columns else pd.DataFrame()
    today_classes_count = len(today_sessions) if not today_sessions.empty else len(tt_df)

    # 2. Institutional Infrastructure & Operations Strip
    c_inf1, c_inf2, c_inf3, c_inf4 = st.columns(4)
    with c_inf1:
        render_kpi_card("Active Campuses", f"{total_campuses}", "Institutional Branches", "blue")
    with c_inf2:
        render_kpi_card("Classrooms & Labs", f"{total_rooms}", "Seating Capacity Managed", "purple")
    with c_inf3:
        render_kpi_card("Departments", f"{total_depts}", "Academic Units", "green")
    with c_inf4:
        breach_color = "red" if total_breaches > 0 else "green"
        render_kpi_card("Capacity Warnings", f"{total_breaches}", "Strength > Room Seating", breach_color)

    # 3. Capacity Breach Alert Banner
    if total_breaches > 0:
        st.markdown(f"""
        <div style="margin: 1rem 0; padding: 0.9rem 1.2rem; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 8px;">
            <span style="color: #F87171; font-weight: 700;">⚠️ Room Capacity Warning:</span>
            <span style="color: #CBD5E1; font-size: 0.85rem;">{total_breaches} scheduled class session(s) exceed room seating limits. Reallocate rooms in <b>Campus Infrastructure</b>.</span>
        </div>
        """, unsafe_allow_html=True)

    # 4. Handle Empty Attendance State Gracefully
    if df.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        render_empty_state(
            "No Attendance Records Found in Active Scope",
            "Institutional structure is initialized. Import authorized attendance records via the Bulk Data Upload Centre or Dynamic QR Attendance to activate real-time analytics."
        )

        # Show Recent Import History and Timetable in Empty State
        if not history_df.empty:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 📜 Recent Ingestion History")
            st.dataframe(
                history_df[["data_category", "file_name", "total_rows", "valid_rows", "status", "timestamp"]].rename(columns={
                    "data_category": "Category",
                    "file_name": "File",
                    "total_rows": "Rows",
                    "valid_rows": "Valid",
                    "status": "Outcome",
                    "timestamp": "Timestamp"
                }),
                use_container_width=True,
                hide_index=True
            )
        return

    # Configuration thresholds
    thresh = float(get_setting("mandatory_attendance_pct", 75.0))
    warn_thresh = float(get_setting("warning_attendance_pct", 80.0))

    # Calculate core cohort registries
    metrics = calculate_overall_metrics(df, threshold=thresh)
    risk_df = calculate_cohort_risk_registry(df)
    trend_df = get_cohort_trend_distribution(df)
    anomaly_df = scan_cohort_anomalies(df)

    # Top KPI Metrics Calculations
    total_students = metrics["total_students"]
    avg_att = metrics["overall_attendance_pct"]
    
    low_risk_count = (risk_df["risk_level"] == "LOW").sum() if not risk_df.empty else 0
    med_risk_count = (risk_df["risk_level"] == "MEDIUM").sum() if not risk_df.empty else 0
    high_risk_count = (risk_df["risk_level"] == "HIGH").sum() if not risk_df.empty else 0
    crit_risk_count = (risk_df["risk_level"] == "CRITICAL").sum() if not risk_df.empty else 0
    immediate_attention = high_risk_count + crit_risk_count

    declining_count = (trend_df["trend_direction"].isin(["Declining", "Critical Decline"])).sum() if not trend_df.empty else 0
    anomaly_count = len(anomaly_df)
    approaching_count = metrics["students_approaching_threshold"]
    below_thresh_count = metrics["students_below_threshold"]

    # Row 1: Primary Cohort Attendance Rate Cards
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Total Enrolled Students", f"{total_students}", f"Across {metrics['total_subjects']} subjects", border_color="#38BDF8")
    with col2:
        att_color = "#10B981" if avg_att >= warn_thresh else ("#F59E0B" if avg_att >= thresh else "#EF4444")
        render_kpi_card("Cohort Attendance Rate", f"{avg_att}%", f"Attended: {metrics['attended_eligible']:,} / {metrics['eligible_sessions']:,}", border_color=att_color)
    with col3:
        render_kpi_card(f"Below Threshold (<{thresh:.0f}%)", f"{below_thresh_count}", "Non-compliant cohort", border_color="#EF4444")
    with col4:
        render_kpi_card(f"Warning Buffer ({thresh:.0f}-{warn_thresh:.0f}%)", f"{approaching_count}", "Watchlist threshold buffer", border_color="#F59E0B")

    # Row 2: Secondary Risk & Operational Metrics
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        render_kpi_card("High & Critical Risk", f"{immediate_attention}", f"{crit_risk_count} Critical &bull; {high_risk_count} High", border_color="#F87171")
    with col6:
        render_kpi_card("Declining Trajectory", f"{declining_count}", "Negative 4-week slope", border_color="#F59E0B")
    with col7:
        render_kpi_card("Late Arrivals Logged", f"{metrics['total_late']}", "Timestamp verified", border_color="#818CF8")
    with col8:
        render_kpi_card("Sudden Drop Anomalies", f"{anomaly_count}", "Statistical Z-score drops", border_color="#A855F7")

    st.markdown("<br>", unsafe_allow_html=True)

    # Visual Analytics Row: Risk Distribution Donut & Weekly Attendance Trend
    c_chart1, c_chart2 = st.columns([1, 1.4])

    with c_chart1:
        st.subheader("🎯 Risk Score Distribution")
        risk_counts = pd.DataFrame({
            "Risk Category": ["Low Risk (0-30)", "Medium Risk (31-60)", "High Risk (61-80)", "Critical (81-100)"],
            "Count": [low_risk_count, med_risk_count, high_risk_count, crit_risk_count]
        })
        fig_donut = px.pie(
            risk_counts,
            values="Count",
            names="Risk Category",
            hole=0.55,
            color="Risk Category",
            color_discrete_map={
                "Low Risk (0-30)": "#10B981",
                "Medium Risk (31-60)": "#F59E0B",
                "High Risk (61-80)": "#EF4444",
                "Critical (81-100)": "#991B1B"
            }
        )
        fig_donut.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#0F172A', width=2)))
        format_plotly_theme(fig_donut, height=340)
        st.plotly_chart(fig_donut, use_container_width=True)

    with c_chart2:
        st.subheader("📈 Cohort Weekly Attendance Trend")
        weekly_trend = get_weekly_attendance_trend(df)
        if not weekly_trend.empty:
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(
                x=weekly_trend["week"],
                y=weekly_trend["attendance_pct"],
                mode="lines+markers",
                name="Cohort Attendance %",
                line=dict(color="#38BDF8", width=3, shape="spline"),
                marker=dict(size=7, color="#818CF8")
            ))
            # Statutory Benchmark Line
            fig_trend.add_hline(
                y=thresh,
                line_dash="dash",
                line_color="#EF4444",
                annotation_text=f"{thresh:.0f}% Statutory Benchmark",
                annotation_position="bottom right",
                annotation_font_color="#EF4444"
            )
            fig_trend.update_xaxes(title="Academic Week", dtick=1)
            fig_trend.update_yaxes(title="Attendance %", range=[30, 100])
            format_plotly_theme(fig_trend, height=340)
            st.plotly_chart(fig_trend, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Department & Subject Performance Overview
    c_dept, c_sub = st.columns([1, 1.2])

    with c_dept:
        st.subheader("🏢 Department Attendance Benchmark")
        dept_df = get_department_wise_attendance(df)
        if not dept_df.empty:
            fig_dept = px.bar(
                dept_df,
                x="department",
                y="attendance_pct",
                color="attendance_pct",
                color_continuous_scale=["#EF4444", "#F59E0B", "#10B981"],
                range_color=[50, 95],
                text="attendance_pct"
            )
            fig_dept.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_dept.add_hline(y=thresh, line_dash="dash", line_color="#EF4444")
            fig_dept.update_yaxes(title="Avg Attendance %", range=[0, 105])
            fig_dept.update_xaxes(title="Department")
            format_plotly_theme(fig_dept, height=320)
            fig_dept.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig_dept, use_container_width=True)

    with c_sub:
        st.subheader("📚 Subject Performance Overview")
        sub_df = get_subject_wise_attendance(df)
        if not sub_df.empty:
            fig_sub = px.bar(
                sub_df,
                x="attendance_pct",
                y="subject_code",
                orientation="h",
                color="attendance_pct",
                color_continuous_scale=["#EF4444", "#F59E0B", "#10B981"],
                range_color=[50, 95],
                text="attendance_pct",
                hover_data=["subject_name", "faculty_name"]
            )
            fig_sub.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_sub.add_vline(x=thresh, line_dash="dash", line_color="#EF4444")
            fig_sub.update_xaxes(title="Avg Attendance %", range=[0, 105])
            fig_sub.update_yaxes(title="Subject Code")
            format_plotly_theme(fig_sub, height=320)
            fig_sub.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig_sub, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Priority At-Risk Students with Search & Sorting
    st.subheader("🚨 Priority Students Requiring Attendance Review")
    if not risk_df.empty:
        search_query = st.text_input("🔍 Search Student Name, Register Number, or Department:", placeholder="Type to filter at-risk list...", key="dash_search")
        
        display_risk = risk_df.copy()
        if search_query.strip():
            q = search_query.strip().lower()
            display_risk = display_risk[
                display_risk["name"].str.lower().str.contains(q) |
                display_risk["register_number"].str.lower().str.contains(q) |
                display_risk["department"].str.lower().str.contains(q)
            ]

        # Pagination controls
        page_size = 10
        total_items = len(display_risk)
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        
        p_col1, p_col2 = st.columns([1, 4])
        with p_col1:
            page_num = st.number_input("Page:", min_value=1, max_value=total_pages, value=1, step=1, key="dash_page")
        with p_col2:
            st.markdown(f"<div style='margin-top: 1.8rem; font-size: 0.85rem; color: #94A3B8;'>Showing {(page_num-1)*page_size + 1}–{min(page_num*page_size, total_items)} of {total_items} students</div>", unsafe_allow_html=True)

        start_idx = (page_num - 1) * page_size
        end_idx = start_idx + page_size
        paged_df = display_risk.iloc[start_idx:end_idx]

        out_table = paged_df[[
            "register_number", "name", "department", "attendance_pct", "risk_score", "risk_level", "trend", "primary_reason", "recommended_action"
        ]].copy()
        out_table.columns = ["Reg No", "Student Name", "Department", "Attendance %", "Risk Score", "Risk Tier", "Trend", "Explainable Reason", "Prescribed Intervention"]

        st.dataframe(
            out_table.style.map(
                lambda v: "color: #EF4444; font-weight: bold;" if v in ["CRITICAL", "HIGH"] else ("color: #F59E0B; font-weight: bold;" if v == "MEDIUM" else ""),
                subset=["Risk Tier"]
            ).map(
                lambda v: "color: #EF4444; font-weight: bold;" if isinstance(v, (int, float)) and v < thresh else "",
                subset=["Attendance %"]
            ),
            use_container_width=True,
            height=360
        )
    else:
        st.info("No at-risk students identified.")

    # 5. Recent Import History Strip
    if not history_df.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📜 Recent Import Execution History")
        st.dataframe(
            history_df[["data_category", "file_name", "total_rows", "valid_rows", "duplicate_rows", "status", "performed_by", "timestamp"]].rename(columns={
                "data_category": "Data Category",
                "file_name": "Source File",
                "total_rows": "Total Rows",
                "valid_rows": "Valid",
                "duplicate_rows": "Deduplicated",
                "status": "Outcome",
                "performed_by": "Operator",
                "timestamp": "Timestamp"
            }),
            use_container_width=True,
            hide_index=True
        )
