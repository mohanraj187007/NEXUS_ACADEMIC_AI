"""
Early Warning System View
Predictive trajectory modeling and proactive identification of students
at imminent risk of breaching academic compliance thresholds.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from analytics.prediction import get_early_warning_registry, predict_student_trajectory
from utils.helpers import render_kpi_card, format_plotly_theme, render_empty_state


def render_early_warning(df: pd.DataFrame):
    """Renders the Early Warning and Predictive Trajectory page."""
    st.markdown('<div class="main-header-title">⚠️ Early Warning & Trajectory Forecasting</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Proactively intercept attendance decay before statutory 75% breaches occur</div>', unsafe_allow_html=True)

    if df.empty:
        render_empty_state("No attendance records available for predictive trajectory forecasting.")
        return

    # Simulation Controls
    c_ctrl1, c_ctrl2 = st.columns([1.5, 2.5])
    with c_ctrl1:
        lookahead = st.slider("Select Forecast Horizon (Weeks Ahead):", min_value=1, max_value=6, value=3)
    with c_ctrl2:
        st.info(f"🔮 Predicting forward trajectory across **Week {df['week'].max() + 1} to Week {df['week'].max() + lookahead}** based on recent velocity decay.")

    warning_df = get_early_warning_registry(df, lookahead_weeks=lookahead)
    if warning_df.empty:
        st.info("No predictive trajectory data available.")
        return

    # Aggregate Watchlist Metrics
    imminent_crit = (warning_df["warning_status"] == "CRITICAL_RISK_IMMINENT").sum()
    imminent_75 = (warning_df["warning_status"] == "BREACH_WARNING").sum()
    watchlist_borderline = (warning_df["warning_status"] == "BORDERLINE_WATCHLIST").sum()
    safe_count = (warning_df["warning_status"] == "SAFE_TRAJECTORY").sum()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Imminent Critical Breach", f"{imminent_crit}", "Projected < 70% in horizon", border_color="#991B1B")
    with col2:
        render_kpi_card("Imminent 75% Breach", f"{imminent_75}", "Currently safe, but will fail", border_color="#EF4444")
    with col3:
        render_kpi_card("Borderline Watchlist", f"{watchlist_borderline}", "Hovering 75-80% with decline", border_color="#F59E0B")
    with col4:
        render_kpi_card("Safe Trajectories", f"{safe_count}", "Stable attendance projected", border_color="#10B981")

    st.markdown("<br>", unsafe_allow_html=True)

    # Visual Forecast Scatter: Current % vs Projected %
    c_scatter, c_status_pie = st.columns([1.4, 1])

    with c_scatter:
        st.subheader("🎯 Current Attendance vs. Projected Trajectory")
        fig_proj = px.scatter(
            warning_df,
            x="current_pct",
            y="projected_pct",
            color="warning_tag",
            hover_data=["register_number", "name", "department", "trend"],
            color_discrete_map={
                "🚨 Imminent Critical Breach": "#991B1B",
                "⚠️ Imminent 75% Breach": "#EF4444",
                "📉 Borderline Watchlist": "#F59E0B",
                "✅ Safe Trajectory": "#10B981"
            },
            size=[10] * len(warning_df)
        )
        # Reference diagonal line (y=x)
        fig_proj.add_shape(
            type="line", line=dict(dash="dot", color="#64748B", width=1.5),
            x0=0, y0=0, x1=100, y1=100
        )
        # 75% horizontal and vertical markers
        fig_proj.add_hline(y=75, line_dash="dash", line_color="#EF4444", annotation_text="Projected 75% Line")
        fig_proj.add_vline(x=75, line_dash="dash", line_color="#64748B", annotation_text="Current 75% Line")
        
        fig_proj.update_xaxes(title="Current Attendance %", range=[30, 102])
        fig_proj.update_yaxes(title=f"Projected Attendance % (after {lookahead} wks)", range=[20, 102])
        format_plotly_theme(fig_proj, height=340)
        st.plotly_chart(fig_proj, use_container_width=True)

    with c_status_pie:
        st.subheader("📊 Forecast Status Composition")
        pie_data = warning_df["warning_tag"].value_counts().reset_index()
        pie_data.columns = ["Status", "Count"]
        fig_pie = px.pie(
            pie_data,
            values="Count",
            names="Status",
            hole=0.5,
            color="Status",
            color_discrete_map={
                "🚨 Imminent Critical Breach": "#991B1B",
                "⚠️ Imminent 75% Breach": "#EF4444",
                "📉 Borderline Watchlist": "#F59E0B",
                "✅ Safe Trajectory": "#10B981"
            }
        )
        format_plotly_theme(fig_pie, height=340)
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Detailed Early Warning Watchlist
    st.subheader(f"📋 Early Warning Priority Watchlist ({lookahead}-Week Lookahead)")
    filter_warn = st.selectbox("Filter by Warning Category:", ["ALL", "🚨 Imminent Critical Breach", "⚠️ Imminent 75% Breach", "📉 Borderline Watchlist", "✅ Safe Trajectory"])
    
    view_df = warning_df.copy()
    if filter_warn != "ALL":
        view_df = view_df[view_df["warning_tag"] == filter_warn]

    display_warn = view_df[[
        "register_number", "name", "department", "current_pct", "projected_pct", "current_risk", "trend", "warning_tag", "warning_desc"
    ]].copy()
    display_warn.columns = ["Reg No", "Student Name", "Dept", "Current %", f"Proj % ({lookahead}w)", "Risk Tier", "Trend", "Warning Status", "Forecasting Diagnostic"]

    st.dataframe(
        display_warn.style.map(
            lambda v: "color: #EF4444; font-weight: bold;" if "Breach" in str(v) else ("color: #F59E0B; font-weight: bold;" if "Borderline" in str(v) else "color: #10B981;"),
            subset=["Warning Status"]
        ),
        use_container_width=True,
        height=380
    )
