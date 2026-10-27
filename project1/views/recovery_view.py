"""
Attendance Recovery Simulator & What-If Scenario Analysis View
Interactive mathematical simulator calculating consecutive classes required to reach 75%/80%/85%,
maximum semester potential, and hypothetical scenario state transitions.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from analytics.attendance import calculate_student_summary
from analytics.risk_engine import calculate_student_risk
from analytics.recovery_simulator import calculate_recovery_roadmap, simulate_what_if_scenario, generate_standard_scenario_matrix
from utils.helpers import render_kpi_card, format_plotly_theme, render_empty_state
from utils.auth_context import get_current_user, is_student


def render_recovery_simulator(df: pd.DataFrame):
    """Renders the Attendance Recovery Simulator & What-If Analysis page."""
    current_auth_user = get_current_user() or {}
    user_is_student = is_student()

    st.markdown('<div class="main-header-title">🧮 Attendance Recovery Simulator & What-If Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Evaluate mathematical recovery roadmaps, consecutive attendance targets, and simulate future hypothetical scenarios</div>', unsafe_allow_html=True)

    if df.empty:
        render_empty_state("No attendance records available for recovery simulation.")
        return

    # Student Selection Dropdown
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
            st.info(f"👤 Personalized Recovery Target Roadmap for: **{s_options.get(selected_id, selected_id)}**")
    else:
        selected_id = st.selectbox(
            "Select Student for Recovery Modeling:",
            options=list(s_options.keys()),
            format_func=lambda x: s_options[x]
        )

    if not selected_id:
        return

    summary = calculate_student_summary(df, selected_id)
    risk_res = calculate_student_risk(df, selected_id)

    total_classes = summary["total_classes"]
    attended_classes = summary["attended_classes"]
    current_pct = summary["attendance_pct"]
    current_risk_score = risk_res["risk_score"]

    # Recovery Roadmap Calculation
    roadmap = calculate_recovery_roadmap(total_classes, attended_classes, remaining_classes=40)

    st.markdown("<br>", unsafe_allow_html=True)

    # 1. Current Status & Recovery Roadmap Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        att_c = "#10B981" if current_pct >= 75 else "#EF4444"
        render_kpi_card("Current Attendance", f"{current_pct}%", f"{attended_classes} of {total_classes} attended", border_color=att_c)
    with c2:
        k75 = roadmap["req_consecutive_75"]
        k75_c = "#10B981" if k75 == 0 else ("#F59E0B" if k75 <= 8 else "#EF4444")
        k75_txt = f"{k75} classes" if k75 > 0 else "Compliant (0 req)"
        render_kpi_card("Consecutive for 75%", k75_txt, "Minimum needed to achieve 75.0%", border_color=k75_c)
    with c3:
        k80 = roadmap["req_consecutive_80"]
        render_kpi_card("Consecutive for 80%", f"{k80} classes", "Buffer zone target", border_color="#38BDF8")
    with c4:
        max_pot = roadmap["max_potential_pct"]
        render_kpi_card("Max Achievable Potential", f"{max_pot}%", "If 100% of remaining 40 classes attended", border_color="#A855F7")

    # Mathematical Roadmap Insights Callout
    if current_pct < 75.0:
        if roadmap["is_75_achievable"]:
            st.markdown(f"""
            <div style="background: rgba(245, 158, 11, 0.15); border-left: 4px solid #F59E0B; border-radius: 8px; padding: 1rem 1.2rem; margin: 1rem 0;">
                <b style="color: #FBBF24;">📌 Mathematical Recovery Roadmap:</b> Student is currently at <b>{current_pct}%</b>. 
                To reach the mandatory <b>75.0%</b> threshold, the student must maintain <b>100% attendance in the next {roadmap['req_consecutive_75']} consecutive classes</b> without missing any.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: rgba(239, 68, 68, 0.2); border-left: 4px solid #EF4444; border-radius: 8px; padding: 1rem 1.2rem; margin: 1rem 0;">
                <b style="color: #F87171;">🚨 Recovery Mathematically Unattainable:</b> Even with 100% attendance in all 40 remaining classes, 
                the maximum possible semester attendance is <b>{roadmap['max_potential_pct']}%</b> (below 75%). Special academic condonation required.
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background: rgba(16, 185, 129, 0.15); border-left: 4px solid #10B981; border-radius: 8px; padding: 1rem 1.2rem; margin: 1rem 0;">
            <b style="color: #34D399;">✅ Student is currently compliant:</b> The student can afford to miss up to <b>{roadmap['safe_missable_classes']} upcoming classes</b> before falling below the 75.0% threshold.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Interactive What-If Simulator
    st.subheader("🧪 Interactive What-If Scenario Builder")
    st.markdown("Simulate custom upcoming attendance scenarios to calculate projected percentage and risk transition:")

    col_sim_in, col_sim_out = st.columns([1.2, 1.2])

    with col_sim_in:
        st.markdown("##### ⚙️ Scenario Inputs")
        upcoming_total = st.slider("Total Upcoming Classes to Simulate:", min_value=1, max_value=40, value=10, step=1)
        upcoming_attended = st.slider("Number of Classes Student Will Attend:", min_value=0, max_value=upcoming_total, value=min(upcoming_total, 8), step=1)
        sim_pct = (upcoming_attended / upcoming_total * 100.0)
        st.caption(f"Simulated Attendance Rate in next {upcoming_total} classes: **{sim_pct:.1f}%**")

    sim_res = simulate_what_if_scenario(
        total_classes=total_classes,
        attended_classes=attended_classes,
        upcoming_classes=upcoming_total,
        upcoming_attended=upcoming_attended,
        current_risk_score=current_risk_score
    )

    with col_sim_out:
        st.markdown("##### 🔮 Simulated Outcome")
        out_c1, out_c2 = st.columns(2)
        with out_c1:
            render_kpi_card(
                "Projected Attendance",
                f"{sim_res['projected_pct']}%",
                f"{'+' if sim_res['pct_delta'] >= 0 else ''}{sim_res['pct_delta']}% delta",
                border_color="#38BDF8"
            )
        with out_c2:
            render_kpi_card(
                "Projected Risk Score",
                f"{sim_res['projected_risk_score']}/100",
                f"Transition to: {sim_res['projected_risk_level']}",
                border_color=sim_res["projected_color"]
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. Standard Scenario Matrix Comparison
    st.subheader("📊 Comparative Scenario Matrix")
    scenario_matrix_df = generate_standard_scenario_matrix(total_classes, attended_classes, current_risk_score)

    c_mat_table, c_mat_bar = st.columns([1.2, 1])

    with c_mat_table:
        st.dataframe(scenario_matrix_df, use_container_width=True, height=270)

    with c_mat_bar:
        # Plot comparative projection
        fig_sc = px.bar(
            scenario_matrix_df,
            x="Scenario",
            y="Projected Attendance %",
            color="Projected Risk Level",
            color_discrete_map={
                "LOW": "#10B981",
                "MEDIUM": "#F59E0B",
                "HIGH": "#EF4444",
                "CRITICAL": "#991B1B"
            },
            text="Projected Attendance %"
        )
        fig_sc.add_hline(y=75, line_dash="dash", line_color="#EF4444", annotation_text="75% Line")
        fig_sc.update_yaxes(range=[0, 105])
        format_plotly_theme(fig_sc, height=270)
        st.plotly_chart(fig_sc, use_container_width=True)
