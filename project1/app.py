"""
Academic Attendance Pattern & Risk Analytics System
Master Application Entry Point & Navigation Controller
Operates on verified college attendance records without automatic synthetic seeding in production.
"""

import streamlit as st
import pandas as pd
import os
import datetime

# 1. Page Configuration
st.set_page_config(
    page_title="Nexus Academic Analytics | Enterprise Risk Intelligence",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Database & Styles Initialization
from database.database import init_db, get_full_attendance_dataset, get_database_summary, get_setting
from utils.helpers import load_custom_css, render_enterprise_top_bar
from analytics.risk_engine import calculate_cohort_risk_registry

# Initialize Database Schema without auto-seeding synthetic data
init_db()
db_summary = get_database_summary()

# Load Custom Theme CSS
load_custom_css()

# Import Modular Page Views
from views.dashboard_view import render_dashboard
from views.student_analysis_view import render_student_analysis
from views.risk_analytics_view import render_risk_analytics
from views.patterns_view import render_pattern_detection
from views.early_warning_view import render_early_warning
from views.recovery_view import render_recovery_simulator
from views.subjects_view import render_subject_analytics
from views.alerts_view import render_alert_center
from views.upload_view import render_data_upload
from views.reconciliation_view import render_reconciliation_center
from views.integrations_view import render_integrations_center
from views.reports_view import render_reports_center
from views.settings_view import render_settings_center
from views.infrastructure_view import render_infrastructure_center
from views.qr_attendance_view import render_qr_attendance_center
from views.gps_checkin_view import render_gps_checkin_center
from utils.auth_context import (
    render_tenant_and_role_switcher, get_current_user, is_authenticated,
    can_access_module, filter_navigation_for_role, is_student
)
from views.auth_view import render_auth_portal, render_unauthorized_access_page

# 2.5 Strict Authentication Gate & Session Enforcement
if not is_authenticated():
    render_auth_portal()
    st.stop()

current_auth_user = get_current_user()
user_role = current_auth_user.get("role", "Student")

# 3. Navigation Hierarchy Definition
NAVIGATION_SUITES = {
    "📊 Executive & Analytics": {
        "icon": "📊",
        "items": {
            "📊 Executive Overview": {"view": "dashboard", "func": render_dashboard, "mode": "filtered"},
            "👤 Student 360° Profile": {"view": "student_analysis", "func": render_student_analysis, "mode": "student_direct"},
            "📚 Subject Intelligence": {"view": "subjects", "func": render_subject_analytics, "mode": "filtered"}
        }
    },
    "🧠 Predictive AI & Risk": {
        "icon": "🧠",
        "items": {
            "🎯 7-Factor Risk & ML": {"view": "risk", "func": render_risk_analytics, "mode": "filtered"},
            "🔍 Absence Pattern Intelligence": {"view": "patterns", "func": render_pattern_detection, "mode": "filtered"},
            "⚠️ Early Warning Forecast": {"view": "early_warning", "func": render_early_warning, "mode": "filtered"}
        }
    },
    "🏛️ Campus & Attendance Ops": {
        "icon": "🏛️",
        "items": {
            "🏛️ Campus Infrastructure": {"view": "infrastructure", "func": render_infrastructure_center, "mode": "standalone"},
            "📱 Dynamic QR Attendance": {"view": "qr_attendance", "func": render_qr_attendance_center, "mode": "standalone"},
            "📍 GPS Campus Check-In": {"view": "gps_checkin", "func": render_gps_checkin_center, "mode": "standalone"}
        }
    },
    "⚖️ Audit & Reconciliation": {
        "icon": "⚖️",
        "items": {
            "⚖️ Multi-Source Reconciliation": {"view": "reconciliation", "func": render_reconciliation_center, "mode": "standalone"},
            "🧮 Recovery Simulator": {"view": "recovery", "func": render_recovery_simulator, "mode": "fallback_all"},
            "🚨 Action & Alert Center": {"view": "alerts", "func": render_alert_center, "mode": "filtered"}
        }
    },
    "⚙️ Operations & Hardware": {
        "icon": "⚙️",
        "items": {
            "📥 Ingestion & Sync Hub": {"view": "upload", "func": render_data_upload, "mode": "standalone"},
            "🔌 Hardware & Vendor Integrations": {"view": "integrations", "func": render_integrations_center, "mode": "standalone"},
            "📄 Audit & Reports Hub": {"view": "reports", "func": render_reports_center, "mode": "fallback_all"},
            "⚙️ System & Academic Rules": {"view": "settings", "func": render_settings_center, "mode": "standalone"}
        }
    }
}

# 4. Sidebar Controller
with st.sidebar:
    # Enterprise Branding Card
    st.markdown("""
    <div class="sidebar-brand-card">
        <div class="brand-title">🎓 NEXUS ANALYTICS AI</div>
        <div class="brand-tag">Academic Pattern & Risk Platform</div>
    </div>
    """, unsafe_allow_html=True)

    # Multi-Tenant & Role Switcher
    render_tenant_and_role_switcher()
    current_auth_user = get_current_user()
    active_inst_id = current_auth_user.get("institution_id", "INST_001")

    # Fetch baseline dataset scoped by institution tenant
    all_unfiltered_df = get_full_attendance_dataset(filters={"institution_id": active_inst_id})
    total_cohort_students = all_unfiltered_df["student_id"].nunique() if not all_unfiltered_df.empty else 0
    total_records_count = len(all_unfiltered_df)

    # Calculate high-risk count for sidebar pulse
    try:
        if not all_unfiltered_df.empty:
            quick_risk = calculate_cohort_risk_registry(all_unfiltered_df)
            at_risk_count = ((quick_risk["risk_level"] == "HIGH") | (quick_risk["risk_level"] == "CRITICAL")).sum() if not quick_risk.empty else 0
        else:
            at_risk_count = 0
    except Exception:
        at_risk_count = 0

    # Live Cohort Pulse Strip
    records_display = f"{total_records_count // 1000}k" if total_records_count >= 1000 else f"{total_records_count}"
    st.markdown(f"""
    <div class="sidebar-pulse-strip">
        <div class="pulse-box">
            <div class="val">{total_cohort_students}</div>
            <div class="lbl">Students</div>
        </div>
        <div class="pulse-box">
            <div class="val">{records_display}</div>
            <div class="lbl">Logs</div>
        </div>
        <div class="pulse-box" style="border-color: rgba(239, 68, 68, 0.4);">
            <div class="val" style="color: #F87171;">{at_risk_count}</div>
            <div class="lbl" style="color: #FCA5A5;">At Risk</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Quick Student 360 Direct Jump (Hidden for Student role to preserve privacy)
    quick_search_id = ""
    if not is_student():
        if not all_unfiltered_df.empty:
            unique_students = all_unfiltered_df[["student_id", "register_number", "student_name"]].drop_duplicates().sort_values(by="register_number")
            search_map = {row["student_id"]: f"{row['register_number']} - {row['student_name']}" for _, row in unique_students.iterrows()}
        else:
            search_map = {}

        quick_search_id = st.selectbox(
            "🔍 Quick Student Search:",
            options=[""] + list(search_map.keys()),
            format_func=lambda x: "Select student to inspect..." if x == "" else search_map.get(x, x),
            key="quick_student_search",
            help="Quickly jump to a student's 360° behavioral diagnostics"
        )
    else:
        quick_search_id = current_auth_user.get("student_id", "")

    st.markdown('<div class="nav-category-header">PLATFORM SUITES</div>', unsafe_allow_html=True)

    # Suite Filter Selector (Filtered by RBAC Role Permissions)
    permitted_suites = filter_navigation_for_role(NAVIGATION_SUITES, user_role)
    suite_names = ["All Modules"] + list(permitted_suites.keys())
    selected_suite = st.selectbox(
        "Select Suite Filter:",
        options=suite_names,
        index=0,
        label_visibility="collapsed",
        key="suite_selector"
    )

    # Build available navigation options based on selected suite
    flat_nav_options = []
    item_to_suite_map = {}
    item_meta_map = {}

    for suite_title, suite_data in permitted_suites.items():
        if selected_suite == "All Modules" or selected_suite == suite_title:
            for item_label, item_meta in suite_data["items"].items():
                flat_nav_options.append(item_label)
                item_to_suite_map[item_label] = suite_title
                item_meta_map[item_label] = item_meta

    # If student quick search was triggered, prioritize Student 360 Profile
    default_nav_idx = 0
    if (quick_search_id != "" or is_student()) and "👤 Student 360° Profile" in flat_nav_options:
        default_nav_idx = flat_nav_options.index("👤 Student 360° Profile")

    selected_nav = st.radio(
        "NAVIGATION_RADIO",
        flat_nav_options if flat_nav_options else ["👤 Student 360° Profile"],
        index=default_nav_idx if flat_nav_options else 0,
        key="main_navigation",
        label_visibility="collapsed"
    )

    st.markdown('<div class="nav-category-header">COHORT SCOPE & FILTERS</div>', unsafe_allow_html=True)

    if is_student():
        st.markdown(f"""
        <div style="padding: 0.6rem 0.8rem; background: rgba(15, 23, 42, 0.6); border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.72rem; color: #94A3B8;">
            <span style="color: #38BDF8; font-weight: 700;">👤 Student ID:</span> {current_auth_user.get('student_id', 'STU_1001')}<br>
            <span style="color: #10B981; font-weight: 700;">🔒 Privacy Scope:</span> Enrolled Record
        </div>
        """, unsafe_allow_html=True)
        selected_dept = "All"
        selected_year = "All"
        selected_sem = "All"
        selected_sec = "All"
        selected_sub = "All"
    else:
        # Cohort Scope Filter Card in Accordion
        with st.expander("🎛️ Filter Cohort Scope", expanded=False):
            if not all_unfiltered_df.empty:
                dept_list = ["All"] + sorted(all_unfiltered_df["department"].dropna().unique().tolist())
                selected_dept = st.selectbox("Department:", dept_list, index=0, key="scope_dept")

                year_list = ["All"] + sorted([str(y) for y in all_unfiltered_df["year"].dropna().unique().tolist()])
                selected_year = st.selectbox("Academic Year:", year_list, index=0, key="scope_year")

                sem_list = ["All"] + sorted([str(s) for s in all_unfiltered_df["semester"].dropna().unique().tolist()]) if "semester" in all_unfiltered_df.columns else ["All"]
                selected_sem = st.selectbox("Semester:", sem_list, index=0, key="scope_sem")

                sec_list = ["All"] + sorted(all_unfiltered_df["section"].dropna().unique().tolist())
                selected_sec = st.selectbox("Section:", sec_list, index=0, key="scope_sec")

                sub_df = all_unfiltered_df[["subject_id", "subject_code", "subject_name"]].drop_duplicates()
                sub_options = {"All": "All Subjects"}
                for _, row in sub_df.iterrows():
                    sub_options[row["subject_id"]] = f"{row['subject_code']} - {row['subject_name']}"
                selected_sub = st.selectbox("Subject:", list(sub_options.keys()), format_func=lambda x: sub_options[x], index=0, key="scope_sub")
            else:
                selected_dept = "All"
                selected_year = "All"
                selected_sem = "All"
                selected_sec = "All"
                selected_sub = "All"
                st.caption("Filters will activate once institutional records are imported.")

    # Assemble active filters dictionary
    active_filters = {
        "institution_id": active_inst_id,
        "department": selected_dept,
        "year": selected_year,
        "semester": selected_sem,
        "section": selected_sec,
        "subject_id": selected_sub
    }

    # Fetch Filtered Attendance Dataset
    filtered_df = get_full_attendance_dataset(filters=active_filters) if not all_unfiltered_df.empty else pd.DataFrame()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="padding: 0.6rem; background: rgba(15, 23, 42, 0.6); border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.72rem; color: #64748B; text-align: center;">
        <span style="color: #38BDF8; font-weight: 700;">● Active Scope:</span> {len(filtered_df):,} records &bull; {filtered_df['student_id'].nunique() if not filtered_df.empty else 0} students
    </div>
    """, unsafe_allow_html=True)


# 5. Top Executive Bar Rendering
current_suite_title = item_to_suite_map.get(selected_nav, "Executive Suite")
render_enterprise_top_bar(
    current_nav=selected_nav,
    category_name=current_suite_title,
    active_filters=active_filters,
    total_students=filtered_df["student_id"].nunique() if not filtered_df.empty else 0,
    total_records=len(filtered_df)
)


# 6. Page View Execution with Server-Side Authorization Enforcement
if not can_access_module(user_role, selected_nav):
    render_unauthorized_access_page(user_role, selected_nav)
else:
    current_item = item_meta_map.get(selected_nav)
    if current_item:
        mode = current_item.get("mode")
        func = current_item["func"]

        if mode == "filtered":
            func(filtered_df)
        elif mode == "student_direct":
            target_stu_id = current_auth_user.get("student_id") if is_student() else (quick_search_id if quick_search_id != "" else None)
            func(filtered_df if not filtered_df.empty else all_unfiltered_df, default_student_id=target_stu_id)
        elif mode == "fallback_all":
            func(filtered_df if not filtered_df.empty else all_unfiltered_df)
        elif mode == "standalone":
            func()
