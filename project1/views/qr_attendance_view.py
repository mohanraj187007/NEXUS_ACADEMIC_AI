"""
Dynamic QR Attendance Management View
Academic Attendance Pattern & Risk Analytics System
Provides instructor-controlled dynamic QR attendance session generation,
real-time projection displays with rotating cryptographically-secure tokens,
student check-in validation portal, anti-duplication enforcement, and live roster monitoring.
"""

import streamlit as st
import pandas as pd
import datetime
from typing import Dict, Any, Optional
from database.database import (
    get_timetable_sessions, get_qr_sessions, get_active_qr_session,
    close_qr_session, get_qr_session_roster, submit_qr_attendance, DB_PATH
)
from analytics.qr_engine import open_new_qr_session, validate_and_record_student_qr
from utils.auth_context import get_current_user, can_start_qr_session
from utils.helpers import render_kpi_card, render_empty_state


def render_qr_attendance_center():
    """Renders the Dynamic QR Attendance session controller and student check-in portal."""
    current_user = get_current_user()
    inst_id = current_user.get("institution_id", "INST_001")
    user_role = current_user.get("role", "Faculty")
    user_name = current_user.get("user_name", "Course Instructor")

    st.markdown('<div class="main-header-title">📱 Dynamic QR Attendance System</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Instructor-governed short-lived QR token sessions with cryptographic verification, duplicate rejection, and real-time roster tracking</div>', unsafe_allow_html=True)

    tab_instructor, tab_student_client, tab_history = st.tabs([
        "👨‍🏫 Instructor Session Controller",
        "📲 Student Check-In Portal",
        "📋 Active Sessions & Audit History"
    ])

    # TAB 1: INSTRUCTOR CONTROLLER
    with tab_instructor:
        col_ctrl, col_qr = st.columns([1.1, 1])

        with col_ctrl:
            st.markdown("##### 🚀 Launch New Attendance Session")
            if not can_start_qr_session():
                st.warning("⚠️ Insufficient permissions: Only Faculty, HODs, and Administrators can launch QR attendance sessions.")
            else:
                # Load scheduled timetable sessions
                tt_df = get_timetable_sessions(institution_id=inst_id)
                sess_options = {}
                if not tt_df.empty:
                    for _, row in tt_df.iterrows():
                        sess_options[row["session_id"]] = f"{row['day_of_week']} P{row['period_number']} | {row['subject_code']} - {row['subject_name']} (Room {row.get('room_number', 'N/A')})"
                sess_options["ADHOC_001"] = "➕ Ad-Hoc / Special Lecture Session"

                selected_sess_id = st.selectbox(
                    "Select Scheduled Class:",
                    options=list(sess_options.keys()),
                    format_func=lambda x: sess_options.get(x, x),
                    key="qr_target_session"
                )

                validity_seconds = st.slider(
                    "QR Code Validity Window (Seconds):",
                    min_value=30,
                    max_value=600,
                    value=180,
                    step=30,
                    help="Tokens expire automatically after this duration to prevent out-of-classroom sharing."
                )

                # Get details of selected session
                matched_row = tt_df[tt_df["session_id"] == selected_sess_id] if not tt_df.empty else pd.DataFrame()
                sub_id = matched_row["subject_id"].values[0] if not matched_row.empty else "SUB_CS301"
                rm_id = matched_row["room_id"].values[0] if (not matched_row.empty and pd.notna(matched_row["room_id"].values[0])) else "RM_101"

                c_launch, c_close = st.columns(2)
                with c_launch:
                    if st.button("▶️ Generate & Open QR Session", use_container_width=True, type="primary"):
                        sess_result = open_new_qr_session(
                            session_id=selected_sess_id,
                            institution_id=inst_id,
                            subject_id=sub_id,
                            room_id=rm_id,
                            opened_by=f"{user_name} ({user_role})",
                            validity_seconds=validity_seconds
                        )
                        st.session_state["active_qr_session"] = sess_result
                        st.success(f"Dynamic QR session opened! Session ID: {sess_result['qr_session_id']}")
                        st.rerun()

                with c_close:
                    if "active_qr_session" in st.session_state:
                        if st.button("⏹️ Close Active Session", use_container_width=True):
                            close_qr_session(st.session_state["active_qr_session"]["qr_session_id"], closed_by=user_name)
                            del st.session_state["active_qr_session"]
                            st.info("Attendance session closed successfully.")
                            st.rerun()

        with col_qr:
            st.markdown("##### 📡 Live Classroom Projection Display")
            active_sess = st.session_state.get("active_qr_session")
            if active_sess:
                # Query fresh session status from DB to verify not expired
                db_sess = get_active_qr_session(active_sess["qr_session_id"])
                if db_sess and db_sess["is_active"] and not db_sess["is_expired"]:
                    st.image(active_sess["qr_image_bytes"], caption="Scan with Authorized Campus App to Check In", width=280)
                    rem_sec = db_sess["remaining_seconds"]
                    st.markdown(f"""
                    <div style="padding: 0.75rem; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 8px;">
                        <span style="color: #34D399; font-weight: 700;">🟢 ACTIVE SESSION</span> &bull; <b>{db_sess['subject_code']}</b><br>
                        <span style="color: #94A3B8; font-size: 0.8rem;">Room: {db_sess['room_number']} &bull; Time Remaining: <b style="color: #FBBF24;">{rem_sec}s</b></span><br>
                        <span style="color: #64748B; font-size: 0.75rem;">Token Hash: <code>{db_sess['token_hash'][:16]}...</code></span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="padding: 1.5rem; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 8px; text-align: center;">
                        <span style="color: #F87171; font-weight: 700; font-size: 1.1rem;">🔴 SESSION EXPIRED / CLOSED</span><br>
                        <span style="color: #CBD5E1; font-size: 0.85rem;">The configured validity window has elapsed. Click 'Generate & Open' to launch a fresh token.</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="padding: 3rem 1.5rem; background: rgba(15, 23, 42, 0.4); border: 1px dashed rgba(255, 255, 255, 0.15); border-radius: 10px; text-align: center;">
                    <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📱</div>
                    <div style="color: #94A3B8; font-size: 0.9rem;">No active QR attendance session running.<br>Select a scheduled class on the left and click <b>Generate & Open QR Session</b>.</div>
                </div>
                """, unsafe_allow_html=True)

        # Real-time Live Roster for current session
        if active_sess:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 👥 Real-Time Verified Attendee Roster")
            roster_df = get_qr_session_roster(active_sess["qr_session_id"])
            if roster_df.empty:
                st.caption("Waiting for student QR check-ins...")
            else:
                st.dataframe(
                    roster_df[["student_id", "register_number", "student_name", "department", "check_in_time", "status"]].rename(columns={
                        "student_id": "Student ID",
                        "register_number": "Reg #",
                        "student_name": "Student Name",
                        "department": "Department",
                        "check_in_time": "Check-In Time",
                        "status": "Verification Status"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

    # TAB 2: STUDENT CHECK-IN PORTAL (Simulator / Web Scanner Client)
    with tab_student_client:
        st.markdown("##### 📲 Student Check-In Interface")
        st.markdown("""
        <div style="padding: 0.75rem 1rem; background: rgba(56, 189, 248, 0.1); border-left: 3px solid #38BDF8; border-radius: 4px; font-size: 0.82rem; color: #E2E8F0; margin-bottom: 1rem;">
            <b>Security Enforcement:</b> Check-ins require an active session, valid token hash, student enrollment verification in this college, and rejects duplicate submissions.
        </div>
        """, unsafe_allow_html=True)

        c_st1, c_st2 = st.columns(2)
        with c_st1:
            active_sessions_df = get_qr_sessions(institution_id=inst_id, active_only=True)
            if active_sessions_df.empty:
                st.warning("⚠️ No active QR attendance sessions currently accepting check-ins in this institution.")
                sel_qrs_id = None
            else:
                qrs_opts = {
                    r["qr_session_id"]: f"{r['subject_code']} - {r['subject_name']} (Room {r.get('room_number', 'N/A')})"
                    for _, r in active_sessions_df.iterrows()
                }
                sel_qrs_id = st.selectbox(
                    "Target Active Session:",
                    options=list(qrs_opts.keys()),
                    format_func=lambda x: qrs_opts.get(x, x),
                    key="student_target_qr_sess"
                )

            stu_reg = st.text_input("Enter Student ID or Register Number:", placeholder="e.g. STU_1001 or 21CS101")
            
            # Auto-fill token if teacher has active session for easy testing
            default_tok = ""
            if "active_qr_session" in st.session_state:
                default_tok = st.session_state["active_qr_session"]["token_hash"]

            token_input = st.text_input("Scanned Token Hash (from Camera / QR):", value=default_tok, placeholder="Paste or scan cryptographic token")

            if st.button("✅ Submit Verified Check-In", use_container_width=True, type="primary"):
                if not sel_qrs_id:
                    st.error("No active session selected.")
                elif not stu_reg.strip():
                    st.error("Please enter your Student ID or Register Number.")
                elif not token_input.strip():
                    st.error("Please provide the scanned QR token signature.")
                else:
                    success, message = validate_and_record_student_qr(
                        qr_session_id=sel_qrs_id,
                        student_identifier=stu_reg.strip(),
                        token_submitted=token_input.strip()
                    )
                    if success:
                        st.success(f"🎉 {message}")
                    else:
                        st.error(f"❌ {message}")

        with c_st2:
            st.markdown("###### 🔍 Verification Integrity Checklist")
            st.markdown("""
            - ⏱️ **Token Expiration**: Checked against server-side timestamp.
            - 🔐 **Cryptographic Signature**: SHA-256 verification against session secret.
            - 🚫 **Duplicate Prevention**: Rejects multiple check-ins by same student for the same session.
            - 🏢 **Multi-Tenant Isolation**: Prevents check-in if student belongs to another institution.
            - 🛡️ **Audit Logging**: Logs device IP/client metadata into immutable audit ledger.
            """)

    # TAB 3: ACTIVE SESSIONS & AUDIT HISTORY
    with tab_history:
        st.markdown("##### 📋 Historical QR Attendance Sessions")
        all_sessions_df = get_qr_sessions(institution_id=inst_id, active_only=False)
        if all_sessions_df.empty:
            render_empty_state("No QR Attendance Sessions Recorded", "Generate a new QR attendance session using the Instructor Controller tab.")
        else:
            st.dataframe(
                all_sessions_df[[
                    "qr_session_id", "session_id", "subject_code", "subject_name",
                    "room_number", "opened_by", "opened_at", "expires_at", "is_active", "attendee_count"
                ]].rename(columns={
                    "qr_session_id": "QR Session ID",
                    "session_id": "Timetable Session",
                    "subject_code": "Course Code",
                    "subject_name": "Course Title",
                    "room_number": "Room",
                    "opened_by": "Instructor",
                    "opened_at": "Opened At",
                    "expires_at": "Expires At",
                    "is_active": "Status (1=Active)",
                    "attendee_count": "Verified Attendees"
                }),
                use_container_width=True,
                hide_index=True
            )
