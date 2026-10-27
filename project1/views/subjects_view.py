"""
Subject Analytics View
Course-wise attendance health comparisons, primary risk subject identification,
and faculty course performance benchmarking.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from analytics.attendance import get_subject_wise_attendance
from utils.helpers import render_kpi_card, format_plotly_theme, render_empty_state


def render_subject_analytics(df: pd.DataFrame):
    """Renders the subject analytics and course comparison page."""
    st.markdown('<div class="main-header-title">📚 Subject-Wise Analytics & Curriculum Health</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Evaluate course-level attendance discrepancies, identify high-risk subjects, and faculty course benchmarks</div>', unsafe_allow_html=True)

    if df.empty:
        render_empty_state("No attendance records available for subject health evaluation.")
        return

    subject_summary = get_subject_wise_attendance(df)
    if subject_summary.empty:
        st.info("No subject data found.")
        return

    # Top KPI Metrics
    total_subs = len(subject_summary)
    best_sub = subject_summary.sort_values(by="attendance_pct", ascending=False).iloc[0]
    worst_sub = subject_summary.sort_values(by="attendance_pct", ascending=True).iloc[0]
    cohort_sub_avg = subject_summary["attendance_pct"].mean()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Total Active Subjects", f"{total_subs}", "In current curriculum filter", border_color="#38BDF8")
    with col2:
        render_kpi_card("Average Course Attendance", f"{cohort_sub_avg:.1f}%", "Mean across all subjects", border_color="#818CF8")
    with col3:
        render_kpi_card("Highest Attended Subject", f"{best_sub['subject_code']}", f"{best_sub['attendance_pct']}% • {best_sub['subject_name']}", border_color="#10B981")
    with col4:
        render_kpi_card("Primary Risk Subject", f"{worst_sub['subject_code']}", f"{worst_sub['attendance_pct']}% • {worst_sub['subject_name']}", border_color="#EF4444")

    st.markdown("<br>", unsafe_allow_html=True)

    # Subject Bar Chart & Subject Risk Distribution
    c_left, c_right = st.columns([1.3, 1])

    with c_left:
        st.subheader("📊 Subject Attendance % Comparison")
        fig_subs = px.bar(
            subject_summary,
            x="subject_code",
            y="attendance_pct",
            color="attendance_pct",
            color_continuous_scale=["#EF4444", "#F59E0B", "#10B981"],
            text="attendance_pct",
            hover_data=["subject_name", "faculty_name", "total_classes"]
        )
        fig_subs.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_subs.add_hline(y=75, line_dash="dash", line_color="#EF4444", annotation_text="75% Statutory Line")
        fig_subs.update_xaxes(title="Subject Code")
        fig_subs.update_yaxes(title="Attendance %", range=[0, 105])
        format_plotly_theme(fig_subs, height=330)
        fig_subs.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_subs, use_container_width=True)

    with c_right:
        st.subheader("🎯 Subject Risk Health Tiers")
        risk_pie_df = subject_summary["risk_level"].value_counts().reset_index()
        risk_pie_df.columns = ["Risk Tier", "Count"]
        fig_r_pie = px.pie(
            risk_pie_df,
            values="Count",
            names="Risk Tier",
            hole=0.5,
            color="Risk Tier",
            color_discrete_map={
                "Low Risk": "#10B981",
                "Moderate Risk": "#F59E0B",
                "High Risk": "#EF4444",
                "Critical Risk": "#991B1B"
            }
        )
        format_plotly_theme(fig_r_pie, height=330)
        st.plotly_chart(fig_r_pie, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Comprehensive Subject Breakdown Table
    st.subheader("📋 Comprehensive Subject Registry")
    display_sub = subject_summary[[
        "subject_code", "subject_name", "faculty_name", "total_classes", "attended", "missed", "attendance_pct", "risk_level"
    ]].copy()
    display_sub.columns = ["Code", "Subject Name", "Course Instructor", "Total Classes", "Attended", "Absences", "Attendance %", "Risk Tier"]

    st.dataframe(
        display_sub.style.map(
            lambda v: "color: #EF4444; font-weight: bold;" if v == "Critical Risk" else ("color: #F59E0B; font-weight: bold;" if v == "High Risk" else "color: #10B981;"),
            subset=["Risk Tier"]
        ).map(
            lambda v: "color: #EF4444; font-weight: bold;" if str(v).endswith("%") and float(str(v).replace("%","")) < 75 else "",
            subset=["Attendance %"]
        ),
        use_container_width=True,
        height=280
    )
