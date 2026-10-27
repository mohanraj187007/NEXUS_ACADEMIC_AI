"""
GPS Campus Check-In Management View
Academic Attendance Pattern & Risk Analytics System
Provides on-demand GPS check-in validation against campus boundaries using Haversine calculation,
administrator geofence boundary configuration, non-continuous privacy protection,
and an administrative review and override portal.
"""

import streamlit as st
import pandas as pd
import uuid
from typing import Dict, Any, Optional
from database.database import (
    get_campuses, get_gps_checkin_logs, review_gps_checkin, get_connection, DB_PATH
)
from analytics.gps_engine import execute_gps_checkin, evaluate_geofence
from utils.auth_context import get_current_user
from utils.helpers import render_kpi_card, render_empty_state, render_disclaimer_card


def render_gps_checkin_center():
    """Renders the GPS Campus Check-In portal, boundary configuration, and review center."""
    current_user = get_current_user()
    inst_id = current_user.get("institution_id", "INST_001")
    user_role = current_user.get("role", "Student")
    user_name = current_user.get("user_name", "Student User")

    st.markdown('<div class="main-header-title">📍 GPS Campus Boundary & Geofence Check-In</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Permission-based campus presence verification with boundary radius enforcement, zero background tracking, and administrative review</div>', unsafe_allow_html=True)

    # Privacy & Non-Continuous Tracking Disclaimer
    render_disclaimer_card(
        "Privacy & Boundary Notice: GPS coordinates are processed strictly on-demand when you explicitly initiate check-in. "
        "The system does not track background locations or continuous movements. Furthermore, campus boundary check-in indicates physical "
        "presence on campus premises and is not treated as proof of classroom attendance without session verification.",
        title="🛡️ On-Demand Geofence Privacy Policy"
    )

    tab_checkin, tab_review, tab_config = st.tabs([
        "📍 Student / Staff Campus Check-In",
        "⚖️ Administrative Review & Overrides",
        "⚙️ Campus Boundary & Geofence Settings"
    ])

    campuses_df = get_campuses(institution_id=inst_id)

    # TAB 1: CAMPUS CHECK-IN
    with tab_checkin:
        col_form, col_map = st.columns([1.1, 1])

        with col_form:
            st.markdown("##### 📍 Initiate Campus Geofence Check-In")

            if campuses_df.empty:
                st.warning("⚠️ No active campuses registered for this institution.")
            else:
                camp_map = {
                    r["campus_id"]: f"{r['name']} ({r['city']}) - Radius: {r['geofence_radius_meters']}m"
                    for _, r in campuses_df.iterrows()
                }
                selected_campus_id = st.selectbox(
                    "Select Target Campus / Branch:",
                    options=list(camp_map.keys()),
                    format_func=lambda x: camp_map.get(x, x),
                    key="gps_target_campus"
                )

                user_identifier = st.text_input("User / Student ID:", value="STU_1001", key="gps_user_id")

                # Get selected campus center coords
                target_camp = campuses_df[campuses_df["campus_id"] == selected_campus_id].iloc[0]
                center_lat = float(target_camp["latitude"])
                center_lon = float(target_camp["longitude"])
                radius_m = float(target_camp["geofence_radius_meters"])

                # Sync check-in inputs when selected campus changes
                if st.session_state.get("last_active_campus_id") != selected_campus_id:
                    st.session_state["last_active_campus_id"] = selected_campus_id
                    st.session_state["gps_in_lat"] = center_lat
                    st.session_state["gps_in_lon"] = center_lon

                # Inline Location Customizer & Preset Changer
                with st.expander("📍 Change / Customize Campus Location & Coordinates", expanded=False):
                    st.caption("Update physical coordinates, select institutional presets, or register new college campuses.")
                    
                    loc_preset = st.selectbox(
                        "Quick Location Presets:",
                        [
                            "-- Current Selected Coordinates --",
                            "VSB Engineering College, Karur (10.954850, 77.954630)",
                            "VSB Technical Campus, Coimbatore (10.835000, 77.012000)",
                            "Apex Central Campus, Chennai (13.082700, 80.270700)",
                            "Metro Tech Campus, Bangalore (12.971600, 77.594600)"
                        ],
                        key="loc_preset_select"
                    )

                    p_lat, p_lon = center_lat, center_lon
                    p_name = target_camp["name"]
                    p_city = target_camp["city"]

                    if "Karur" in loc_preset:
                        p_lat, p_lon, p_name, p_city = 10.954850, 77.954630, "VSB Engineering College - Main Campus", "Karur"
                    elif "Coimbatore" in loc_preset:
                        p_lat, p_lon, p_name, p_city = 10.835000, 77.012000, "VSB Technical Campus", "Coimbatore"
                    elif "Chennai" in loc_preset:
                        p_lat, p_lon, p_name, p_city = 13.082700, 80.270700, "Apex Central Campus", "Chennai"
                    elif "Bangalore" in loc_preset:
                        p_lat, p_lon, p_name, p_city = 12.971600, 77.594600, "Metro Tech Campus", "Bangalore"

                    col_n1, col_n2 = st.columns(2)
                    with col_n1:
                        edit_name = st.text_input("Campus Name:", value=p_name, key=f"edit_c_name_{selected_campus_id}")
                    with col_n2:
                        edit_city = st.text_input("City / Region:", value=p_city, key=f"edit_c_city_{selected_campus_id}")

                    col_e1, col_e2, col_e3 = st.columns([1, 1, 1])
                    with col_e1:
                        edit_lat = st.number_input("Center Latitude:", value=float(p_lat), format="%.6f", key=f"edit_c_lat_{selected_campus_id}")
                    with col_e2:
                        edit_lon = st.number_input("Center Longitude:", value=float(p_lon), format="%.6f", key=f"edit_c_lon_{selected_campus_id}")
                    with col_e3:
                        edit_rad = st.number_input("Allowed Radius (m):", value=float(radius_m), min_value=50.0, max_value=5000.0, step=25.0, key=f"edit_c_rad_{selected_campus_id}")

                    c_save, c_add_new = st.columns(2)
                    with c_save:
                        if st.button("💾 Apply & Update Current Campus Location", use_container_width=True, type="primary"):
                            conn = get_connection(DB_PATH)
                            conn.execute("""
                                UPDATE campuses
                                SET name = ?, city = ?, latitude = ?, longitude = ?, geofence_radius_meters = ?
                                WHERE campus_id = ?;
                            """, (edit_name, edit_city, edit_lat, edit_lon, edit_rad, selected_campus_id))
                            conn.commit()
                            conn.close()
                            st.session_state["gps_in_lat"] = edit_lat
                            st.session_state["gps_in_lon"] = edit_lon
                            st.success(f"Campus updated: {edit_name} ({edit_city})!")
                            st.rerun()

                    with c_add_new:
                        if st.button("➕ Add as New Campus Location", use_container_width=True):
                            new_c_id = f"CAMP_{uuid.uuid4().hex[:6].upper()}"
                            conn = get_connection(DB_PATH)
                            conn.execute("""
                                INSERT INTO campuses (campus_id, institution_id, campus_code, name, city, latitude, longitude, geofence_radius_meters, is_active)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1);
                            """, (new_c_id, inst_id, f"CODE_{uuid.uuid4().hex[:4].upper()}", edit_name, edit_city, edit_lat, edit_lon, edit_rad))
                            conn.commit()
                            conn.close()
                            st.session_state["gps_target_campus"] = new_c_id
                            st.session_state["gps_in_lat"] = edit_lat
                            st.session_state["gps_in_lon"] = edit_lon
                            st.success(f"Added new campus: {edit_name} ({edit_city})!")
                            st.rerun()

                st.markdown(f"""
                <div style="padding: 0.6rem 0.8rem; background: rgba(30, 41, 59, 0.4); border-radius: 6px; font-size: 0.8rem; color: #94A3B8; margin-bottom: 0.8rem;">
                    🏛️ <b>Active Campus:</b> <span style="color: #38BDF8; font-weight: 700;">{target_camp['name']}</span> ({target_camp['city']})<br>
                    <b>Coordinates:</b> {center_lat:.6f}, {center_lon:.6f} &bull; <b>Allowed Radius:</b> {radius_m:.0f}m
                </div>
                """, unsafe_allow_html=True)

                st.markdown("###### 🌐 Provide Check-In Coordinates")
                c_lat, c_lon = st.columns(2)
                with c_lat:
                    user_lat = st.number_input("Latitude:", value=st.session_state.get("gps_in_lat", center_lat), format="%.6f", key="gps_in_lat")
                with c_lon:
                    user_lon = st.number_input("Longitude:", value=st.session_state.get("gps_in_lon", center_lon), format="%.6f", key="gps_in_lon")

                # Preset buttons for testing both inside & outside scenarios
                st.caption("Quick Scenario Test:")
                c_inside, c_outside = st.columns(2)
                with c_inside:
                    if st.button("🎯 Simulate Inside Campus (~30m)", use_container_width=True):
                        st.session_state["gps_in_lat"] = center_lat + 0.0002
                        st.session_state["gps_in_lon"] = center_lon + 0.0002
                        st.rerun()
                with c_outside:
                    if st.button("🚫 Simulate Outside Campus (~1.5km)", use_container_width=True):
                        st.session_state["gps_in_lat"] = center_lat + 0.015
                        st.session_state["gps_in_lon"] = center_lon + 0.015
                        st.rerun()

                device_note = st.selectbox(
                    "Device Client Source:",
                    ["Campus Mobile App (Android)", "Campus Mobile App (iOS)", "Authorized Web Browser", "Kiosk Terminal"]
                )

                if st.button("📡 Verify & Record Geofence Check-In", use_container_width=True, type="primary"):
                    if not user_identifier.strip():
                        st.error("Please enter a valid User / Student ID.")
                    else:
                        result = execute_gps_checkin(
                            institution_id=inst_id,
                            campus_id=selected_campus_id,
                            user_id=user_identifier.strip(),
                            user_lat=user_lat,
                            user_lon=user_lon,
                            device_info=device_note
                        )
                        if result["success"]:
                            st.success(f"✅ {result['message']}")
                        else:
                            st.error(f"❌ {result['message']}")

        with col_map:
            st.markdown("##### 🗺️ Campus Boundary Inspection")
            if not campuses_df.empty:
                map_rows = [{
                    "lat": center_lat,
                    "lon": center_lon
                }]
                if abs(user_lat - center_lat) > 0.00001 or abs(user_lon - center_lon) > 0.00001:
                    map_rows.append({
                        "lat": user_lat,
                        "lon": user_lon
                    })
                map_data = pd.DataFrame(map_rows)
                st.map(map_data, zoom=15)
                st.markdown(f"""
                <div style="font-size: 0.82rem; color: #94A3B8; margin-top: 0.5rem; line-height: 1.5;">
                    🏛️ <b>Configured Campus:</b> <span style="color: #38BDF8; font-weight: 700;">{target_camp['name']}</span> ({target_camp['city']})<br>
                    📍 <b>Center:</b> <code>{center_lat:.6f}, {center_lon:.6f}</code> &bull; <b>Radius:</b> <code>{radius_m:.0f}m</code>
                </div>
                """, unsafe_allow_html=True)

    # TAB 2: ADMINISTRATIVE REVIEW & OVERRIDES
    with tab_review:
        st.markdown("##### ⚖️ Administrative Review of GPS Check-Ins")
        st.caption("Review check-in attempts, inspect out-of-boundary flags, and apply manual administrative overrides.")

        logs_df = get_gps_checkin_logs(institution_id=inst_id, limit=50)
        if logs_df.empty:
            render_empty_state("No GPS Check-In Logs Recorded", "Check-in logs will appear here once users submit on-demand geofence validations.")
        else:
            st.dataframe(
                logs_df[[
                    "checkin_id", "campus_name", "user_id", "distance_from_center_meters",
                    "verification_status", "device_info", "timestamp", "review_status", "reviewed_by"
                ]].rename(columns={
                    "checkin_id": "Check-In ID",
                    "campus_name": "Campus",
                    "user_id": "User / Student ID",
                    "distance_from_center_meters": "Distance (m)",
                    "verification_status": "Geofence Status",
                    "device_info": "Device Client",
                    "timestamp": "Timestamp",
                    "review_status": "Review Status",
                    "reviewed_by": "Reviewed By"
                }),
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")
            st.markdown("###### ✏️ Manual Adjudication / Override")
            c_rev1, c_rev2, c_rev3 = st.columns(3)
            with c_rev1:
                target_checkin = st.selectbox("Select Check-In to Review:", options=logs_df["checkin_id"].tolist())
            with c_rev2:
                new_status = st.selectbox("New Adjudication Status:", ["Admin-Approved", "Admin-Rejected", "Pending Field Review"])
            with c_rev3:
                reason = st.text_input("Review Justification:", "Authorized network lag / verified presence via physical gate")

            if st.button("💾 Apply Adjudication Override", type="primary"):
                admin_name = f"{current_user['user_name']} ({current_user['role']})"
                success = review_gps_checkin(
                    checkin_id=target_checkin,
                    new_review_status=new_status,
                    reviewed_by=admin_name,
                    reason=reason
                )
                if success:
                    st.success(f"Check-In '{target_checkin}' updated to status '{new_status}' with audit trail!")
                    st.rerun()

    # TAB 3: BOUNDARY & GEOFENCE CONFIGURATION
    with tab_config:
        st.markdown("##### ⚙️ Campus Boundary & Geofence Coordinates")
        if campuses_df.empty:
            st.info("No campuses found.")
        else:
            for idx, c_row in campuses_df.iterrows():
                with st.expander(f"📍 {c_row['name']} ({c_row['campus_code']}) - {c_row['city']}", expanded=False):
                    with st.form(f"campus_geo_form_{c_row['campus_id']}"):
                        f_name, f_city = st.columns(2)
                        with f_name:
                            new_name = st.text_input("Campus Name:", value=str(c_row["name"]), key=f"name_{c_row['campus_id']}")
                        with f_city:
                            new_city = st.text_input("City / Region:", value=str(c_row["city"]), key=f"city_{c_row['campus_id']}")
                        f_c1, f_c2, f_c3 = st.columns(3)
                        with f_c1:
                            new_lat = st.number_input("Campus Center Latitude:", value=float(c_row["latitude"]), format="%.6f", key=f"lat_{c_row['campus_id']}")
                        with f_c2:
                            new_lon = st.number_input("Campus Center Longitude:", value=float(c_row["longitude"]), format="%.6f", key=f"lon_{c_row['campus_id']}")
                        with f_c3:
                            new_rad = st.number_input("Geofence Radius (Meters):", min_value=50.0, max_value=5000.0, value=float(c_row["geofence_radius_meters"]), step=25.0, key=f"rad_{c_row['campus_id']}")

                        if st.form_submit_button("💾 Save Campus Coordinates & Name"):
                            conn = get_connection(DB_PATH)
                            conn.execute("""
                                UPDATE campuses
                                SET name = ?, city = ?, latitude = ?, longitude = ?, geofence_radius_meters = ?
                                WHERE campus_id = ?;
                            """, (new_name, new_city, new_lat, new_lon, new_rad, c_row["campus_id"]))
                            conn.commit()
                            conn.close()
                            st.success(f"Boundary and details updated for {new_name}!")
                            st.rerun()
