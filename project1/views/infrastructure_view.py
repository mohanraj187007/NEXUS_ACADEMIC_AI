"""
Campus Infrastructure Management View
Academic Attendance Pattern & Risk Analytics System
Provides comprehensive oversight of colleges, campuses, buildings, floors,
classrooms, laboratories, seminar halls, HOD offices, equipment, room capacity
validation against scheduled classes, and real check-in occupancy estimates.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional
from database.database import (
    get_all_institutions, get_campuses, get_buildings, get_rooms,
    get_timetable_sessions, get_room_occupancy_analysis, get_capacity_breach_alerts,
    create_or_update_room, DB_PATH
)
from utils.auth_context import get_current_user, can_manage_infrastructure
from utils.helpers import render_kpi_card, render_empty_state


def render_infrastructure_center():
    """Renders the comprehensive multi-campus infrastructure management portal."""
    current_user = get_current_user()
    inst_id = current_user.get("institution_id", "INST_001")

    st.markdown('<div class="main-header-title">🏛️ Campus Infrastructure & Facility Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Manage multi-campus facilities, buildings, floors, laboratories, seating capacities, and detect timetable capacity breaches</div>', unsafe_allow_html=True)

    # 1. Fetch live data
    inst_df = get_all_institutions()
    campuses_df = get_campuses(institution_id=inst_id)
    buildings_df = get_buildings(institution_id=inst_id)
    rooms_df = get_rooms(institution_id=inst_id)
    breach_df = get_capacity_breach_alerts(institution_id=inst_id)
    occupancy_df = get_room_occupancy_analysis(institution_id=inst_id)

    total_rooms = len(rooms_df)
    total_buildings = len(buildings_df)
    total_campuses = len(campuses_df)
    total_breaches = len(breach_df)

    # 2. Executive KPI Header
    kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
    with kpi_c1:
        render_kpi_card("Campuses & Branches", f"{total_campuses}", "Configured Locations", "blue")
    with kpi_c2:
        render_kpi_card("Academic Buildings", f"{total_buildings}", "Blocks & Pavilions", "purple")
    with kpi_c3:
        render_kpi_card("Classrooms & Labs", f"{total_rooms}", "Total Managed Facilities", "green")
    with kpi_c4:
        breach_color = "red" if total_breaches > 0 else "green"
        render_kpi_card("Capacity Breaches", f"{total_breaches}", "Class Strength > Seating", breach_color)

    # 3. Capacity Breach Warning Banner
    if total_breaches > 0:
        st.markdown(f"""
        <div style="margin: 1.2rem 0; padding: 1rem 1.25rem; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 10px;">
            <div style="font-weight: 700; color: #FCA5A5; font-size: 1rem; margin-bottom: 0.3rem;">
                ⚠️ Room Capacity Breach Detected: {total_breaches} Scheduled Class(es) Exceed Room Seating
            </div>
            <div style="color: #CBD5E1; font-size: 0.85rem;">
                The scheduled student strength for one or more timetable sessions exceeds the certified room capacity.
                Review the breaches below to reallocate larger lecture halls or split cohorts.
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. Functional Sub-Portals (Tabs)
    tab_rooms, tab_breaches, tab_occupancy, tab_campuses, tab_add_room = st.tabs([
        "🏢 Classrooms & Facilities",
        f"⚠️ Capacity Breaches ({total_breaches})",
        "📊 Live Check-in Occupancy",
        "🗺️ Campuses & Buildings",
        "➕ Register / Edit Room"
    ])

    # TAB 1: CLASSROOMS & FACILITIES DIRECTORY
    with tab_rooms:
        st.markdown("##### 🏛️ Institutional Room Directory")
        if rooms_df.empty:
            render_empty_state("No Classrooms or Laboratories Found", "Import buildings and rooms through the Bulk Data Upload Centre or use the 'Register Room' tab.")
        else:
            # Filter bar
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                bldg_options = ["All"] + sorted(rooms_df["building_name"].dropna().unique().tolist())
                sel_bldg = st.selectbox("Filter Building:", bldg_options, index=0)
            with f_col2:
                type_options = ["All"] + sorted(rooms_df["room_type"].dropna().unique().tolist())
                sel_type = st.selectbox("Filter Room Type:", type_options, index=0)
            with f_col3:
                search_query = st.text_input("Search Room Name / Number:", "")

            filtered_rooms = rooms_df.copy()
            if sel_bldg != "All":
                filtered_rooms = filtered_rooms[filtered_rooms["building_name"] == sel_bldg]
            if sel_type != "All":
                filtered_rooms = filtered_rooms[filtered_rooms["room_type"] == sel_type]
            if search_query.strip():
                q = search_query.strip().lower()
                filtered_rooms = filtered_rooms[
                    filtered_rooms["room_number"].astype(str).str.lower().str.contains(q) |
                    filtered_rooms["room_name"].astype(str).str.lower().str.contains(q)
                ]

            st.dataframe(
                filtered_rooms[[
                    "room_number", "room_name", "building_name", "floor_number",
                    "room_type", "capacity", "dimension_sqft", "equipment_details"
                ]].rename(columns={
                    "room_number": "Room #",
                    "room_name": "Facility Name",
                    "building_name": "Building",
                    "floor_number": "Floor",
                    "room_type": "Type",
                    "capacity": "Seating Capacity",
                    "dimension_sqft": "Area (Sq. Ft)",
                    "equipment_details": "Installed Equipment"
                }),
                use_container_width=True,
                hide_index=True
            )

    # TAB 2: CAPACITY BREACH WARNINGS
    with tab_breaches:
        st.markdown("##### ⚠️ Timetable Seating Capacity Breaches")
        if breach_df.empty:
            st.success("✅ Certified Safe: No scheduled classes currently exceed room seating capacity.")
        else:
            st.markdown(f"Found **{len(breach_df)}** class session(s) scheduled in rooms with insufficient seating capacity:")
            st.dataframe(
                breach_df[[
                    "session_id", "day_of_week", "period_number", "scheduled_start_time",
                    "subject_code", "subject_name", "room_number", "room_type",
                    "room_capacity", "expected_strength", "excess_students"
                ]].rename(columns={
                    "session_id": "Session ID",
                    "day_of_week": "Day",
                    "period_number": "Period",
                    "scheduled_start_time": "Time",
                    "subject_code": "Course Code",
                    "subject_name": "Course Title",
                    "room_number": "Allocated Room",
                    "room_type": "Room Type",
                    "room_capacity": "Seating Capacity",
                    "expected_strength": "Cohort Strength",
                    "excess_students": "Deficit (Overflow)"
                }),
                use_container_width=True,
                hide_index=True
            )

    # TAB 3: OCCUPANCY ESTIMATES
    with tab_occupancy:
        st.markdown("##### 📊 Estimated Room Occupancy Based on Check-Ins")
        st.caption("Calculated by comparing validated attendance check-ins recorded in each facility against certified room seating capacity.")
        if occupancy_df.empty:
            render_empty_state("No Check-in or Room Records Available", "Occupancy metrics will calculate automatically once rooms are mapped to timetables and attendance records are logged.")
        else:
            st.dataframe(
                occupancy_df[[
                    "room_number", "room_name", "building_name", "room_type",
                    "room_capacity", "checkins_count", "scheduled_sessions_count",
                    "max_scheduled_strength", "occupancy_pct"
                ]].rename(columns={
                    "room_number": "Room #",
                    "room_name": "Facility Name",
                    "building_name": "Building",
                    "room_type": "Type",
                    "room_capacity": "Capacity",
                    "checkins_count": "Attendance Check-Ins",
                    "scheduled_sessions_count": "Sessions Scheduled",
                    "max_scheduled_strength": "Max Scheduled Strength",
                    "occupancy_pct": "Occupancy Rate (%)"
                }),
                use_container_width=True,
                hide_index=True
            )

    # TAB 4: CAMPUSES & BUILDINGS
    with tab_campuses:
        st.markdown("##### 🗺️ Registered Campuses & Academic Blocks")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("###### 🏫 Campuses & Branches")
            if campuses_df.empty:
                st.info("No campuses registered yet.")
            else:
                for _, camp in campuses_df.iterrows():
                    st.markdown(f"""
                    <div class="analysis-card" style="margin-bottom: 0.75rem;">
                        <b style="color: #38BDF8; font-size: 1rem;">{camp['name']} ({camp['campus_code']})</b><br>
                        <span style="color: #94A3B8; font-size: 0.82rem;">City: {camp['city']} &bull; Lat/Lon: {camp['latitude']}, {camp['longitude']} &bull; Geofence: {camp['geofence_radius_meters']}m</span>
                    </div>
                    """, unsafe_allow_html=True)
        with col_c2:
            st.markdown("###### 🏢 Academic Blocks & Buildings")
            if buildings_df.empty:
                st.info("No buildings registered yet.")
            else:
                for _, bldg in buildings_df.iterrows():
                    st.markdown(f"""
                    <div class="analysis-card" style="margin-bottom: 0.75rem;">
                        <b style="color: #818CF8; font-size: 1rem;">{bldg['building_name']} ({bldg['building_code']})</b><br>
                        <span style="color: #94A3B8; font-size: 0.82rem;">Floors: {bldg['total_floors']} floors &bull; Campus ID: {bldg['campus_id']}</span>
                    </div>
                    """, unsafe_allow_html=True)

    # TAB 5: REGISTER / EDIT ROOM
    with tab_add_room:
        st.markdown("##### ➕ Register or Update Facility")
        if not can_manage_infrastructure():
            st.warning("⚠️ Insufficient permissions: Facility registration is restricted to College and Campus Administrators.")
        else:
            with st.form("room_entry_form", clear_on_submit=False):
                r_c1, r_c2 = st.columns(2)
                with r_c1:
                    r_id = st.text_input("Room ID (Unique Key):", "RM_201")
                    r_num = st.text_input("Room Number:", "201")
                    r_name = st.text_input("Room / Lab Name:", "Advanced Computing Lab")
                    r_floor = st.number_input("Floor Number:", min_value=0, max_value=20, value=2)
                    r_type = st.selectbox("Room Type:", ["Classroom", "Laboratory", "Seminar Hall", "Library", "HOD Office", "Faculty Room"])
                with r_c2:
                    # Choose building
                    b_opts = {b["building_id"]: f"{b['building_name']} ({b['building_code']})" for _, b in buildings_df.iterrows()} if not buildings_df.empty else {"BLDG_001": "Main Academic Block"}
                    sel_bldg_id = st.selectbox("Associated Building:", list(b_opts.keys()), format_func=lambda x: b_opts.get(x, x))
                    
                    # Choose campus
                    c_opts = {c["campus_id"]: f"{c['name']} ({c['campus_code']})" for _, c in campuses_df.iterrows()} if not campuses_df.empty else {"CAMP_001": "Main Campus"}
                    sel_camp_id = st.selectbox("Associated Campus:", list(c_opts.keys()), format_func=lambda x: c_opts.get(x, x))

                    r_cap = st.number_input("Seating Capacity:", min_value=5, max_value=1000, value=60)
                    r_area = st.number_input("Area (Sq. Ft):", min_value=100.0, max_value=50000.0, value=750.0)
                    r_equip = st.text_input("Installed Equipment:", "Interactive Smartboard, Projector, Wi-Fi 6")

                submit_btn = st.form_submit_button("💾 Save Facility Record", use_container_width=True)
                if submit_btn:
                    success = create_or_update_room(
                        room_id=r_id.strip(),
                        building_id=sel_bldg_id,
                        campus_id=sel_camp_id,
                        institution_id=inst_id,
                        room_number=r_num.strip(),
                        room_name=r_name.strip(),
                        floor_number=int(r_floor),
                        room_type=r_type,
                        capacity=int(r_cap),
                        dimension_sqft=float(r_area),
                        equipment_details=r_equip.strip()
                    )
                    if success:
                        st.success(f"Facility '{r_name}' ({r_num}) successfully registered!")
                        st.rerun()
                    else:
                        st.error("Failed to register facility. Please check the inputs.")
