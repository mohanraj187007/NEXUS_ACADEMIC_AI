"""
Settings, Academic Rules & User Management View
Academic Attendance Pattern & Risk Analytics System (NEXUS ACADEMIC AI)

Provides SQLite database health statistics, institutional threshold policy configuration,
excused absence calculation rules, authorized user & RBAC management, authentication audit logs,
database purge controls, and an explicit benchmark dataset generator.
"""

import streamlit as st
import pandas as pd
from database.database import (
    get_database_summary, get_setting, set_setting, clear_attendance_records,
    reset_database, get_all_registered_users, create_new_user, unlock_user_account,
    update_user_password, get_auth_audit_logs_df, get_all_students
)
from data.generator import generate_and_seed_database
from utils.helpers import render_kpi_card
from utils.security import validate_password_strength, hash_password
from utils.auth_context import CANONICAL_ROLES, ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY, ROLE_STUDENT


def render_settings_center():
    """Renders the settings, institutional policy, and user management interface."""
    st.markdown('<div class="main-header-title">⚙️ System Configuration & Academic Rules</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Configure institutional attendance rules, threshold parameters, manage authorized users, and review security audit logs</div>', unsafe_allow_html=True)

    summary = get_database_summary()

    # 1. Database Health Overview KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Students Registered", f"{summary['total_students']}", "In students table", border_color="#38BDF8")
    with c2:
        render_kpi_card("Academic Subjects", f"{summary['total_subjects']}", "In subjects table", border_color="#818CF8")
    with c3:
        render_kpi_card("Attendance Logs", f"{summary['total_attendance_records']:,}", "Indexed records", border_color="#10B981")
    with c4:
        render_kpi_card("Pending Discrepancies", f"{summary.get('pending_reconciliations', 0)}", "In review queue", border_color="#EF4444" if summary.get('pending_reconciliations', 0) > 0 else "#10B981")

    st.markdown("<br>", unsafe_allow_html=True)

    # Main Tabs
    tab_policies, tab_users, tab_audit, tab_maintenance = st.tabs([
        "🎯 Academic Rules & Policies",
        "👥 Authorized Users & RBAC",
        "🛡️ Authentication & Audit Logs",
        "🧹 Database Maintenance & Sandbox"
    ])

    # TAB 1: ACADEMIC RULES & POLICIES
    with tab_policies:
        st.subheader("🎯 Institutional Attendance & Risk Policies")
        st.markdown("All analytical engines, early warning forecasts, and reports use these persisted parameters.")

        cur_thresh = float(get_setting("mandatory_attendance_pct", 75.0))
        cur_warn = float(get_setting("warning_attendance_pct", 80.0))
        cur_risk_crit = int(get_setting("critical_risk_score", 80))
        cur_late_tol = int(get_setting("late_arrival_tolerance_mins", 10))
        cur_excused_rule = str(get_setting("excused_absence_rule", "exclude_from_total"))

        t1, t2, t3 = st.columns(3)
        with t1:
            new_thresh = st.number_input(
                "Mandatory Statutory Minimum (%):",
                min_value=50.0, max_value=90.0, value=cur_thresh, step=1.0,
                help="Institutional threshold below which students are officially debarred or flagged for disciplinary action."
            )
        with t2:
            new_warn = st.number_input(
                "Proactive Watchlist Buffer Margin (%):",
                min_value=60.0, max_value=95.0, value=cur_warn, step=1.0,
                help="Threshold above mandatory minimum where students are put on warning before breaching the cutoff."
            )
        with t3:
            new_crit = st.number_input(
                "Critical Risk Score Cutoff (0-100):",
                min_value=60, max_value=95, value=cur_risk_crit, step=5
            )

        t4, t5 = st.columns(2)
        with t4:
            new_late_tol = st.number_input(
                "Late Arrival Grace Period (Minutes):",
                min_value=0, max_value=45, value=cur_late_tol, step=5,
                help="Minutes after scheduled class start before a check-in is flagged as Late."
            )
        with t5:
            new_excused_rule = st.selectbox(
                "Excused Absence / Approved Leave Institutional Rule:",
                options=["exclude_from_total", "count_as_attended", "count_as_neutral"],
                index=["exclude_from_total", "count_as_attended", "count_as_neutral"].index(cur_excused_rule) if cur_excused_rule in ["exclude_from_total", "count_as_attended", "count_as_neutral"] else 0,
                format_func=lambda x: {
                    "exclude_from_total": "Exclude from Total Scheduled Sessions (Reduces Denominator - Standard)",
                    "count_as_attended": "Count as Attended Session (Grants Attendance Credit on Medical/Duty Proof)",
                    "count_as_neutral": "Treat as Neutral Waiver (No Effect on Average)"
                }[x]
            )

        if st.button("💾 Persist Policy Settings", type="primary"):
            set_setting("mandatory_attendance_pct", new_thresh, "Statutory minimum attendance requirement (%)")
            set_setting("warning_attendance_pct", new_warn, "Proactive early warning benchmark threshold (%)")
            set_setting("critical_risk_score", new_crit, "Cutoff score for Critical Risk Tier")
            set_setting("late_arrival_tolerance_mins", new_late_tol, "Grace period in minutes before marked Late")
            set_setting("excused_absence_rule", new_excused_rule, "Policy for excused absence calculation")
            st.success("✅ Institutional attendance policies persisted successfully to SQLite system_settings!")
            st.rerun()

    # TAB 2: AUTHORIZED USERS & RBAC MANAGEMENT
    with tab_users:
        st.subheader("👥 Authorized Institutional Users & Role-Based Access")
        st.markdown("Manage system administrators, academic coordinators, faculty members, and student user accounts.")

        users_df = get_all_registered_users(limit=100)
        if not users_df.empty:
            display_cols = ["username", "full_name", "role", "email", "account_status", "failed_login_attempts", "last_login_at"]
            st.dataframe(
                users_df[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "username": "Username",
                    "full_name": "Full Name",
                    "role": "Assigned Role",
                    "email": "Institutional Email",
                    "account_status": "Account Status",
                    "failed_login_attempts": "Failed Logins",
                    "last_login_at": "Last Login Timestamp"
                }
            )
        else:
            st.info("No users registered.")

        st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 1.5rem 0;'>", unsafe_allow_html=True)

        col_new_user, col_unlock_user = st.columns(2)

        # Form: Create New Authorized User
        with col_new_user:
            with st.expander("➕ Register New Authorized User", expanded=False):
                u_name = st.text_input("Username (unique):", key="new_user_uname")
                u_fullname = st.text_input("Full Name:", key="new_user_fullname")
                u_email = st.text_input("Institutional Email:", key="new_user_email")
                u_role = st.selectbox("Role Assignment:", options=CANONICAL_ROLES, index=2, key="new_user_role")

                # If student, link student_id
                u_stu_id = None
                if u_role == ROLE_STUDENT:
                    students_list = get_all_students()
                    stu_map = {row["student_id"]: f"{row['register_number']} - {row['name']}" for _, row in students_list.iterrows()} if not students_list.empty else {}
                    u_stu_id = st.selectbox("Link to Student Profile:", options=list(stu_map.keys()), format_func=lambda x: stu_map.get(x, x), key="new_user_stu_link")

                u_pass = st.text_input("Initial Password:", type="password", key="new_user_pass")
                u_must_change = st.checkbox("Require password change upon first login", value=False, key="new_user_change_first")

                if st.button("Create User Account", type="primary", key="btn_create_user_submit"):
                    is_valid, msg = validate_password_strength(u_pass)
                    if not is_valid:
                        st.error(f"Password does not meet enterprise policy: {msg}")
                    else:
                        ok, resp, _ = create_new_user({
                            "username": u_name,
                            "full_name": u_fullname,
                            "email": u_email,
                            "role": u_role,
                            "password": u_pass,
                            "student_id": u_stu_id,
                            "must_change_password": u_must_change
                        })
                        if ok:
                            st.success(resp)
                            st.rerun()
                        else:
                            st.error(resp)

        # Form: Account Lockout & Password Reset
        with col_unlock_user:
            with st.expander("🔓 Unlock Account / Admin Password Reset", expanded=False):
                if not users_df.empty:
                    u_options = {row["user_id"]: f"{row['username']} - {row['full_name']} ({row['account_status']})" for _, row in users_df.iterrows()}
                    sel_user_id = st.selectbox("Select Target User:", options=list(u_options.keys()), format_func=lambda x: u_options[x], key="sel_user_manage")

                    cu1, cu2 = st.columns(2)
                    with cu1:
                        if st.button("🔓 Unlock Account", key="btn_unlock_account_admin"):
                            unlocked = unlock_user_account(sel_user_id)
                            if unlocked:
                                st.success("Account status restored to ACTIVE with zero failed login attempts.")
                                st.rerun()
                            else:
                                st.error("Failed to unlock account.")

                    with cu2:
                        admin_new_pw = st.text_input("Set New Password:", type="password", key="admin_set_new_pw")
                        if st.button("Reset User Password", key="btn_reset_user_pw_admin"):
                            is_v, m = validate_password_strength(admin_new_pw)
                            if not is_v:
                                st.error(m)
                            else:
                                n_h, n_s = hash_password(admin_new_pw)
                                updated = update_user_password(sel_user_id, n_h, n_s)
                                if updated:
                                    st.success("User password updated and all existing sessions revoked.")
                                    st.rerun()
                                else:
                                    st.error("Failed to update user password.")

    # TAB 3: AUTHENTICATION AUDIT TRAIL
    with tab_audit:
        st.subheader("🛡️ Security & Authentication Audit Logs")
        st.markdown("Chronological record of authentication attempts, session creations, account lockouts, and administrative overrides.")

        audit_df = get_auth_audit_logs_df(limit=100)
        if not audit_df.empty:
            st.dataframe(
                audit_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "event_id": "Event ID",
                    "timestamp": "Timestamp (ISO)",
                    "event_type": "Security Event",
                    "username": "Account Identifier",
                    "user_id": "User ID",
                    "ip_address": "Client IP",
                    "details": "Audit Evidence"
                }
            )
        else:
            st.info("No authentication audit events recorded yet.")

    # TAB 4: DATABASE MAINTENANCE & BENCHMARK SANDBOX
    with tab_maintenance:
        st.subheader("🧹 Production Database Maintenance")
        st.markdown("Safely purge attendance records when preparing for a new semester or importing a fresh institutional dataset.")

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if st.button("🗑️ Clear Attendance & Reconciliation Logs", help="Removes all attendance logs while keeping registered students & subjects."):
                cleared = clear_attendance_records()
                st.warning(f"Cleared {cleared:,} attendance and reconciliation records. Ready for clean institutional import.")
                st.rerun()

        with col_p2:
            if st.button("⚠️ Complete Factory Reset Database", help="Wipes all tables and re-initializes fresh empty schema."):
                reset_database()
                st.success("Database cleanly re-initialized to initial factory state.")
                st.rerun()

        st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 2rem 0;'>", unsafe_allow_html=True)

        st.subheader("🧪 Synthetic Benchmark Sandbox (Developer / Testing Only)")
        st.markdown("""
        <div style="background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #C7D2FE;">
            <b>⚠️ BENCHMARK SANDBOX DISCLAIMER:</b><br>
            This tool generates synthetic simulation records for 104 students across 4 departments for software testing and demonstration of behavioral archetypes (High performers, Chronic absentees, Monday/Friday skippers). 
            <b>Never present synthetic benchmark data as real college records.</b>
        </div>
        """, unsafe_allow_html=True)

        if st.button("⚡ Seed 104-Student Synthetic Benchmark Dataset (Sandbox Mode)"):
            with st.spinner("Generating reproducible archetypes and seeding database..."):
                new_summary = generate_and_seed_database()
            st.success(f"Benchmark sandbox populated with {new_summary['total_students']} students and {new_summary['total_attendance_records']:,} simulation records.")
            st.rerun()
