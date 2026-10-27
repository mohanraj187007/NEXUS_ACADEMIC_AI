"""
Absence Pattern Detection & Behavioral Intelligence View
Visualizes temporal, day-of-week, hour-of-day, and subject-clustering absence patterns.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from analytics.pattern_detection import analyze_day_of_week_pattern, analyze_hour_pattern, get_all_student_patterns
from utils.helpers import render_kpi_card, format_plotly_theme, render_empty_state


def render_pattern_detection(df: pd.DataFrame):
    """Renders the behavioral absence pattern intelligence page."""
    st.markdown('<div class="main-header-title">🔍 Absence Pattern & Behavioral Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Detect hidden temporal biases, day-of-week dropouts, morning punctuality issues, and avoidance clustering</div>', unsafe_allow_html=True)

    if df.empty:
        render_empty_state("No attendance records available for behavioral pattern detection.")
        return

    # 1. Cohort-Wide Day of Week & Hour Analysis
    df_aug = df.copy()
    df_aug["date_dt"] = pd.to_datetime(df_aug["date"])
    df_aug["day_name"] = df_aug["date_dt"].dt.day_name()
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    # Day of Week Aggregation
    day_cohort = df_aug.groupby("day_name").agg(
        total=("status", "count"),
        absent=("status", lambda s: (s == "Absent").sum())
    ).reset_index()
    day_cohort["day_name"] = pd.Categorical(day_cohort["day_name"], categories=day_order, ordered=True)
    day_cohort = day_cohort.sort_values("day_name").reset_index(drop=True)
    day_cohort["absence_rate"] = (day_cohort["absent"] / day_cohort["total"] * 100.0).round(1)

    # Hour of Day Aggregation
    hour_cohort = df_aug.groupby("hour").agg(
        total=("status", "count"),
        absent=("status", lambda s: (s == "Absent").sum())
    ).reset_index()
    hour_cohort["absence_rate"] = (hour_cohort["absent"] / hour_cohort["total"] * 100.0).round(1)

    # Day x Hour Absence Rate Matrix (Heatmap)
    matrix_df = df_aug.groupby(["day_name", "hour"]).agg(
        total=("status", "count"),
        absent=("status", lambda s: (s == "Absent").sum())
    ).reset_index()
    matrix_df["absence_rate"] = (matrix_df["absent"] / matrix_df["total"] * 100.0).round(1)
    pivot_matrix = matrix_df.pivot(index="day_name", columns="hour", values="absence_rate").reindex(day_order)

    # Top Pattern KPIs
    worst_day_row = day_cohort.sort_values(by="absence_rate", ascending=False).iloc[0]
    worst_hour_row = hour_cohort.sort_values(by="absence_rate", ascending=False).iloc[0]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Peak Absence Day", f"{worst_day_row['day_name']}", f"{worst_day_row['absence_rate']}% Absence Rate", border_color="#EF4444")
    with col2:
        render_kpi_card("Peak Absence Hour", f"Hour {worst_hour_row['hour']}", f"{worst_hour_row['absence_rate']}% Absence Rate", border_color="#F59E0B")
    with col3:
        render_kpi_card("Monday vs Mid-Week", f"{day_cohort[day_cohort['day_name']=='Monday']['absence_rate'].values[0]}%", "Monday absenteeism rate", border_color="#38BDF8")
    with col4:
        render_kpi_card("Friday Absenteeism", f"{day_cohort[day_cohort['day_name']=='Friday']['absence_rate'].values[0]}%", "Weekend-adjacent rate", border_color="#A855F7")

    st.markdown("<br>", unsafe_allow_html=True)

    # Row 2: Heatmap & Hour Distribution
    c_hm, c_hr = st.columns([1.3, 1])

    with c_hm:
        st.subheader("🗓️ Day × Hour Absence Heatmap (% Absent)")
        fig_hm = px.imshow(
            pivot_matrix,
            labels=dict(x="Class Hour / Period", y="Day of Week", color="Absence %"),
            x=[f"Hour {c}" for c in pivot_matrix.columns],
            y=pivot_matrix.index,
            color_continuous_scale="Reds",
            aspect="auto",
            text_auto=True
        )
        format_plotly_theme(fig_hm, height=330)
        st.plotly_chart(fig_hm, use_container_width=True)

    with c_hr:
        st.subheader("⏰ Hour-of-Day Absenteeism Rate")
        fig_hr = px.bar(
            hour_cohort,
            x="hour",
            y="absence_rate",
            color="absence_rate",
            color_continuous_scale=["#10B981", "#F59E0B", "#EF4444"],
            text="absence_rate"
        )
        fig_hr.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_hr.update_xaxes(title="Class Hour (Period)", dtick=1)
        fig_hr.update_yaxes(title="Absence Rate %", range=[0, max(50, hour_cohort['absence_rate'].max() + 15)])
        format_plotly_theme(fig_hr, height=330)
        fig_hr.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_hr, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Individual Student Pattern Inspector
    st.subheader("🔎 Individual Student Pattern Inspector")
    students_df = df[["student_id", "register_number", "student_name"]].drop_duplicates().sort_values(by="register_number")
    s_map = {row["student_id"]: f"{row['register_number']} - {row['student_name']}" for _, row in students_df.iterrows()}
    
    inspect_id = st.selectbox(
        "Select student to inspect individual behavioral anomalies:",
        options=list(s_map.keys()),
        format_func=lambda x: s_map[x]
    )

    if inspect_id:
        stu_records = df[df["student_id"] == inspect_id]
        pat_data = get_all_student_patterns(stu_records)
        
        c_pat_left, c_pat_right = st.columns([1, 1])

        with c_pat_left:
            st.markdown("##### 📌 Detected Behavioral Anomalies")
            if pat_data["patterns"]:
                for pat in pat_data["patterns"]:
                    st.markdown(f"""
                    <div style="background: rgba(30, 41, 59, 0.7); border-left: 4px solid #F59E0B; border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.6rem;">
                        <b style="color: #FBBF24;">{pat['tag']}</b><br>
                        <span style="color: #CBD5E1; font-size: 0.85rem;">{pat['detail']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No statistically significant day or hour biases detected for this student.")

        with c_pat_right:
            st.markdown("##### 📊 Student Day-of-Week Absence Profile")
            if not pat_data["day_stats"].empty:
                fig_s_day = px.bar(
                    pat_data["day_stats"],
                    x="day_name",
                    y="absence_rate",
                    color="absence_rate",
                    color_continuous_scale=["#10B981", "#EF4444"],
                    text="absence_rate"
                )
                fig_s_day.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_s_day.update_xaxes(title="Day")
                fig_s_day.update_yaxes(title="Absence %", range=[0, 105])
                format_plotly_theme(fig_s_day, height=260)
                fig_s_day.update_layout(coloraxis_showscale=False)
                st.plotly_chart(fig_s_day, use_container_width=True)
