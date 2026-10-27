"""
Alert Center View
Unified operational hub aggregating prioritized alerts across Critical Risk, High Risk,
Declining Velocity, Attendance Anomalies, and Consecutive Absence Streaks.
"""

import streamlit as st
import pandas as pd
from analytics.risk_engine import calculate_cohort_risk_registry
from analytics.trend_analysis import get_cohort_trend_distribution
from analytics.anomaly_detection import scan_cohort_anomalies
from utils.helpers import render_kpi_card, render_empty_state


def render_alert_center(df: pd.DataFrame):
    """Renders the centralized Alert Center."""
    st.markdown('<div class="main-header-title">🚨 Academic Alert & Intervention Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Real-time operational alerts classified by severity for immediate faculty triage and intervention</div>', unsafe_allow_html=True)

    if df.empty:
        render_empty_state("No attendance records available for alert processing.")
        return

    risk_df = calculate_cohort_risk_registry(df)
    trend_df = get_cohort_trend_distribution(df)
    anomaly_df = scan_cohort_anomalies(df)

    # Build Unified Alert Stream
    alerts = []

    # 1. Critical Risk Alerts
    crit_students = risk_df[risk_df["risk_level"] == "CRITICAL"]
    for _, s in crit_students.iterrows():
        alerts.append({
            "severity": "CRITICAL",
            "badge": "🔴 CRITICAL RISK",
            "priority": 1,
            "student_id": s["student_id"],
            "reg_no": s["register_number"],
            "name": s["name"],
            "dept": s["department"],
            "metric": f"Score: {s['risk_score']}/100 ({s['attendance_pct']}%)",
            "detail": s["primary_reason"],
            "action": s["recommended_action"]
        })

    # 2. High Risk Alerts
    high_students = risk_df[risk_df["risk_level"] == "HIGH"]
    for _, s in high_students.iterrows():
        alerts.append({
            "severity": "HIGH",
            "badge": "🟠 HIGH RISK",
            "priority": 2,
            "student_id": s["student_id"],
            "reg_no": s["register_number"],
            "name": s["name"],
            "dept": s["department"],
            "metric": f"Score: {s['risk_score']}/100 ({s['attendance_pct']}%)",
            "detail": s["primary_reason"],
            "action": s["recommended_action"]
        })

    # 3. Anomaly Alerts
    for _, a in anomaly_df.iterrows():
        alerts.append({
            "severity": "ANOMALY",
            "badge": "⚠️ SUDDEN ANOMALY",
            "priority": 3,
            "student_id": a["student_id"],
            "reg_no": a["register_number"],
            "name": a["name"],
            "dept": a["department"],
            "metric": f"Plunge: Δ {a['delta_pct']}% (Z={a['z_score']})",
            "detail": a["description"],
            "action": "Investigate immediate personal or medical hardship."
        })

    # 4. Declining Velocity Alerts (students not already critical/high)
    declining_students = trend_df[trend_df["trend_direction"] == "Critical Decline"]
    already_flagged = [a["student_id"] for a in alerts]
    for _, t in declining_students.iterrows():
        if t["student_id"] not in already_flagged:
            alerts.append({
                "severity": "DECLINE",
                "badge": "🔵 CRITICAL DECLINE",
                "priority": 4,
                "student_id": t["student_id"],
                "reg_no": t["register_number"],
                "name": t["name"],
                "dept": t["department"],
                "metric": f"Drop: Δ {t['change_pct']}% in last 4 wks",
                "detail": f"Recent average plunged to {t['recent_avg']}% vs previous {t['previous_avg']}%.",
                "action": "Review sudden decline in engagement."
            })

    alerts_df = pd.DataFrame(alerts)

    # Top Alert Counters
    crit_count = len([a for a in alerts if a["severity"] == "CRITICAL"])
    high_count = len([a for a in alerts if a["severity"] == "HIGH"])
    anomaly_count = len([a for a in alerts if a["severity"] == "ANOMALY"])
    decline_count = len([a for a in alerts if a["severity"] == "DECLINE"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Critical Alerts", f"{crit_count}", "Immediate HOD escalation", border_color="#991B1B")
    with c2:
        render_kpi_card("High Risk Alerts", f"{high_count}", "1-on-1 counseling required", border_color="#EF4444")
    with c3:
        render_kpi_card("Statistical Anomalies", f"{anomaly_count}", "Sudden unexpected drops", border_color="#A855F7")
    with c4:
        render_kpi_card("Steep Decline Alerts", f"{decline_count}", "Active negative velocity", border_color="#38BDF8")

    st.markdown("<br>", unsafe_allow_html=True)

    if alerts_df.empty:
        st.success("🎉 No active critical or high-risk alerts detected in the cohort.")
        return

    # Filter and Search Alerts
    col_af1, col_af2 = st.columns([1, 2])
    with col_af1:
        filter_sev = st.selectbox("Filter Alert Severity:", ["ALL", "CRITICAL", "HIGH", "ANOMALY", "DECLINE"])
    with col_af2:
        search_alert = st.text_input("Search student in alert roster:")

    filtered_alerts = alerts_df.copy()
    if filter_sev != "ALL":
        filtered_alerts = filtered_alerts[filtered_alerts["severity"] == filter_sev]
    if search_alert:
        q = search_alert.strip().lower()
        filtered_alerts = filtered_alerts[
            filtered_alerts["name"].str.lower().str.contains(q) |
            filtered_alerts["reg_no"].str.lower().str.contains(q)
        ]

    filtered_alerts = filtered_alerts.sort_values(by="priority").reset_index(drop=True)

    st.markdown(f"**Showing {len(filtered_alerts)} Active Priority Alerts**")

    # Render Alerts Stream
    for _, alt in filtered_alerts.iterrows():
        border_c = "#991B1B" if alt["severity"] == "CRITICAL" else ("#EF4444" if alt["severity"] == "HIGH" else ("#A855F7" if alt["severity"] == "ANOMALY" else "#38BDF8"))
        st.markdown(f"""
        <div style="background: rgba(15, 23, 42, 0.85); border-left: 5px solid {border_c}; border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 0.8rem; border-top: 1px solid rgba(255,255,255,0.05); border-right: 1px solid rgba(255,255,255,0.05); border-bottom: 1px solid rgba(255,255,255,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                <span style="font-size: 0.82rem; font-weight: 800; color: {border_c};">{alt['badge']}</span>
                <span style="font-size: 0.8rem; color: #94A3B8; font-weight: 600;">{alt['dept']}</span>
            </div>
            <div style="font-size: 1.1rem; font-weight: 800; color: #F8FAFC;">{alt['name']} <span style="font-size: 0.85rem; color: #38BDF8; font-weight: 500;">({alt['reg_no']})</span></div>
            <div style="font-size: 0.88rem; color: #E2E8F0; margin: 4px 0;"><b>Observation:</b> {alt['metric']} — {alt['detail']}</div>
            <div style="font-size: 0.85rem; color: #60A5FA; margin-top: 6px;"><b>▶ Prescribed Action:</b> {alt['action']}</div>
        </div>
        """, unsafe_allow_html=True)
