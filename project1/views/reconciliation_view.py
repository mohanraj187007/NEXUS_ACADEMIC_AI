"""
Attendance Reconciliation & Discrepancy Review View
Provides an interactive multi-source discrepancy review queue cross-referencing
timetable schedules, faculty classroom rosters, biometric door sensors, and campus gates.
Features evidence inspectors, confidence indicators, status workflows, and audit history.
"""

import streamlit as st
import pandas as pd
import datetime
from analytics.reconciliation import (
    run_reconciliation_scan, get_reconciliation_cases, update_case_status, 
    import_raw_events_stream, DISCLAIMER_TEXT
)
from utils.helpers import render_kpi_card, render_disclaimer_card


def render_reconciliation_center():
    """Renders the Attendance Reconciliation and Discrepancy Review page."""
    st.markdown('<div class="main-header-title">⚖️ Multi-Source Attendance Reconciliation</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Cross-reference timetables, faculty attendance, biometric logs, campus gates, and QR check-ins to detect operational discrepancies with evidence inspection</div>', unsafe_allow_html=True)

    # Mandatory Ethical Disclaimer
    render_disclaimer_card()

    tab_review, tab_stream = st.tabs([
        "📋 Discrepancy Review Queue", 
        "📡 Sensor Stream Ingestion & Simulator"
    ])

    # TAB 1: DISCREPANCY REVIEW QUEUE
    with tab_review:
        # Scan Controller Strip
        c_scan1, c_scan2, c_scan3 = st.columns([1.5, 1.2, 1])
        with c_scan1:
            tolerance_mins = st.slider("Late Arrival Tolerance Window (minutes):", min_value=5, max_value=45, value=15, step=5)
        with c_scan2:
            date_filter = st.date_input("Filter Scan Date (Optional):", value=None)
        with c_scan3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Run Reconciliation Scan", type="primary", use_container_width=True):
                with st.spinner("Correlating multi-source streams, checking timetable schedules, and scoring discrepancies..."):
                    d_str = str(date_filter) if date_filter else None
                    scan_res = run_reconciliation_scan(date_filter=d_str, tolerance_minutes=tolerance_mins)
                st.success(f"Scan complete: {scan_res['new_cases_created']} new discrepancy cases detected!")
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # Filters for Review Queue
        all_cases = get_reconciliation_cases()
        
        # Summary KPI Cards
        total_cases = len(all_cases)
        pending_count = (all_cases["review_status"] == "Pending").sum() if not all_cases.empty else 0
        verified_count = (all_cases["review_status"] == "Verified").sum() if not all_cases.empty else 0
        corrected_count = (all_cases["review_status"] == "Corrected").sum() if not all_cases.empty else 0
        dismissed_count = (all_cases["review_status"] == "Dismissed").sum() if not all_cases.empty else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            render_kpi_card("Total Discrepancies", f"{total_cases}", "All detected cases", border_color="#38BDF8")
        with k2:
            render_kpi_card("Pending Review", f"{pending_count}", "Action required", border_color="#EF4444")
        with k3:
            render_kpi_card("Verified Presences", f"{verified_count}", "Corroborated by staff", border_color="#10B981")
        with k4:
            render_kpi_card("Corrected / Dismissed", f"{corrected_count + dismissed_count}", "Resolved cases", border_color="#A855F7")

        st.markdown("<br>", unsafe_allow_html=True)

        # Filter Selectors
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            status_filter = st.selectbox("Filter by Review Status:", options=["All", "Pending", "Verified", "Corrected", "Dismissed"], index=1)
        with f_col2:
            disc_types = ["All"] + sorted(all_cases["discrepancy_type"].dropna().unique().tolist()) if not all_cases.empty else ["All"]
            type_filter = st.selectbox("Filter by Discrepancy Type:", options=disc_types, index=0)

        filtered_cases = get_reconciliation_cases(
            status=status_filter if status_filter != "All" else None,
            discrepancy_type=type_filter if type_filter != "All" else None
        )

        if filtered_cases.empty:
            st.info("No reconciliation discrepancy cases found matching current filters.")
        else:
            st.markdown(f"**Showing {len(filtered_cases)} Reconciliation Discrepancy Cases:**")
            
            # Interactive Case Inspector
            case_options = {
                row["case_id"]: f"Case #{row['case_id']}: {row['student_name']} ({row['student_id']}) — {row['discrepancy_type']} [{row['review_status']}]"
                for _, row in filtered_cases.iterrows()
            }
            selected_case_id = st.selectbox(
                "Select Discrepancy Case to Inspect & Review:",
                options=list(case_options.keys()),
                format_func=lambda x: case_options[x]
            )

            if selected_case_id:
                case_row = filtered_cases[filtered_cases["case_id"] == selected_case_id].iloc[0]

                c_info1, c_action = st.columns([1.6, 1.2])

                with c_info1:
                    conf = case_row["confidence_score"]
                    conf_color = "#10B981" if conf >= 80 else ("#F59E0B" if conf >= 60 else "#EF4444")

                    st.markdown(f"""
                    <div class="analysis-card">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <span style="font-size: 0.8rem; color: #94A3B8; font-weight: 700;">CASE DETAILS #{case_row['case_id']}</span>
                            <span style="background: rgba(255,255,255,0.06); padding: 0.2rem 0.6rem; border-radius: 6px; font-size: 0.75rem; color: {conf_color}; font-weight: 700;">
                                Confidence Score: {conf:.0f}%
                            </span>
                        </div>
                        <div style="font-size: 1.2rem; font-weight: 800; color: #F8FAFC;">
                            {case_row['student_name']} <span style="font-size: 0.85rem; color: #38BDF8;">({case_row['student_id']})</span>
                        </div>
                        <div style="font-size: 0.85rem; color: #94A3B8; margin-top: 2px;">
                            Dept: {case_row['department']} &bull; Date: {case_row['date']} &bull; Period: {case_row['period_number']}
                        </div>
                        <hr style="border-color: rgba(255,255,255,0.08); margin: 8px 0;">
                        <div style="font-size: 0.85rem; color: #CBD5E1; line-height: 1.5;">
                            <b>Discrepancy:</b> <span style="color: #F87171; font-weight: 600;">{case_row['discrepancy_type']}</span><br>
                            <b>Sources Involved:</b> {case_row['sources_involved']}<br>
                            <b>Evidence Present:</b> {case_row['evidence_present']}<br>
                            <b>Evidence Missing:</b> {case_row['evidence_missing']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with c_action:
                    st.markdown("##### 📝 Case Adjudication & Notes")
                    new_status = st.selectbox(
                        "Set Review Status:",
                        options=["Pending", "Verified", "Corrected", "Dismissed"],
                        index=["Pending", "Verified", "Corrected", "Dismissed"].index(case_row["review_status"]),
                        key=f"status_sel_{selected_case_id}"
                    )
                    reviewer_notes = st.text_area(
                        "Reviewer Determination Notes (Audited):",
                        value=case_row.get("reviewer_notes") or "",
                        placeholder="e.g., Verified student was attending authorized robotics competition in Lab 4; attendance marked corrected.",
                        key=f"notes_{selected_case_id}"
                    )
                    reviewer_user = st.selectbox(
                        "Adjudicating Official:",
                        options=["Dean of Academic Affairs (Admin)", "Department Academic Counselor", "Senior Faculty Advisor"],
                        key=f"user_{selected_case_id}"
                    )

                    if st.button("💾 Submit Case Determination", type="primary", use_container_width=True):
                        if not reviewer_notes.strip():
                            st.error("Please provide reviewer determination notes for the audit trail.")
                        else:
                            success = update_case_status(
                                case_id=int(case_row["case_id"]),
                                new_status=new_status,
                                reviewer_notes=reviewer_notes.strip(),
                                reviewer_user=reviewer_user
                            )
                            if success:
                                st.success(f"✅ Case #{case_row['case_id']} updated to '{new_status}' with audit trail.")
                                st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 📑 Full Discrepancy Case Register:")
            st.dataframe(filtered_cases, use_container_width=True)

    # TAB 2: MULTI-SOURCE SENSOR STREAM SIMULATOR
    with tab_stream:
        st.subheader("Multi-Source Stream Ingestion & Testing")
        st.markdown("""
        Import raw sensor streams from external campus IoT terminals (turnstiles, biometric door readers, QR kiosks)
        to cross-reference against faculty classroom attendance.
        """)

        s_col1, s_col2 = st.columns(2)
        with s_col1:
            stream_source_type = st.selectbox(
                "Source Terminal Type:",
                options=["campus_gate", "biometric_door", "classroom_qr"]
            )
        with s_col2:
            st.caption("Upload raw device log with columns: `student_id`, `event_timestamp`, `event_type`, `location_or_device`.")

        raw_event_file = st.file_uploader("Upload Sensor Log (CSV):", type=["csv"], key="raw_sensor_file")
        if raw_event_file is not None:
            try:
                ev_df = pd.read_csv(raw_event_file)
                st.dataframe(ev_df.head(5), use_container_width=True)

                if st.button("📥 Ingest Stream Events", type="primary"):
                    batch_id = f"STREAM_{int(datetime.datetime.now().timestamp())}"
                    count = import_raw_events_stream(
                        events_df=ev_df,
                        source_type=stream_source_type,
                        batch_id=batch_id
                    )
                    st.success(f"✅ Successfully ingested {count} raw sensor events into imported_source_events table under batch {batch_id}!")
                    st.info("Switch to the 'Discrepancy Review Queue' tab and click 'Run Reconciliation Scan' to identify mismatches.")
            except Exception as e:
                st.error(f"Error parsing sensor stream file: {str(e)}")
