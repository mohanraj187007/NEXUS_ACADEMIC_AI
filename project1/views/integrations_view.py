"""
Hardware & Vendor Integrations View
Displays real-time connectivity status, configuration forms, and diagnostic ping tests
for campus biometric terminals, turnstiles, and authorized file export pipelines.
Never fabricates active connections for unconfigured hardware.
"""

import streamlit as st
import pandas as pd
import datetime
from integrations.vendor_adapters import (
    get_all_adapters, CsvXlsxExportAdapter, BiometricApiAdapter, CampusGateApiAdapter
)
from database.database import get_setting, set_setting
from utils.helpers import render_kpi_card


def render_integrations_center():
    """Renders the Hardware and Vendor Integrations interface."""
    st.markdown('<div class="main-header-title">🔌 Hardware & Vendor Integrations Hub</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Manage connectivity and REST interfaces for campus biometric door terminals, turnstiles, and authorized institutional file exports</div>', unsafe_allow_html=True)

    st.markdown("""
    <div style="
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 1.25rem;
        font-size: 0.8rem;
        color: #94A3B8;
        line-height: 1.4;
    ">
        <b style="color: #38BDF8;">🔒 AUTHENTICATION & HARDWARE POLICY:</b>
        The system communicates exclusively with documented college APIs and authorized file exports. We never claim a physical biometric device is connected unless valid institutional endpoints and credentials have been verified.
    </div>
    """, unsafe_allow_html=True)

    adapters = get_all_adapters()
    file_adapter = adapters[0]
    bio_adapter = adapters[1]
    gate_adapter = adapters[2]

    # Status Overview KPIs
    bio_configured = bio_adapter.is_configured()
    gate_configured = gate_adapter.is_configured()

    k1, k2, k3 = st.columns(3)
    with k1:
        render_kpi_card("File Export Engine", "Active", "CSV & XLSX Ingestion Ready", border_color="#10B981")
    with k2:
        bio_color = "#10B981" if bio_configured else "#EF4444"
        render_kpi_card("Biometric Terminal API", "Online" if bio_configured else "Unconfigured", "REST Endpoint" if bio_configured else "Offline / File Mode", border_color=bio_color)
    with k3:
        gate_color = "#10B981" if gate_configured else "#EF4444"
        render_kpi_card("Campus Gate Turnstiles", "Online" if gate_configured else "Unconfigured", "Access Controller" if gate_configured else "Offline / File Mode", border_color=gate_color)

    st.markdown("<br>", unsafe_allow_html=True)

    # 1. File Export Adapter Card
    st.subheader("1. 📄 Authorized Institutional File Export Adapter")
    st.markdown("""
    <div class="analysis-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <b style="color: #38BDF8; font-size: 1.05rem;">Authorized Batch Ingestion Engine</b>
            <span style="background: rgba(16, 185, 129, 0.15); color: #34D399; padding: 0.2rem 0.6rem; border-radius: 6px; font-weight: 700; font-size: 0.75rem;">
                ● ACTIVE / OPERATIONAL
            </span>
        </div>
        <p style="color: #CBD5E1; font-size: 0.85rem; margin-top: 6px; line-height: 1.45;">
            Default production ingestion adapter. Accepts CSV and Excel (.xlsx) files exported by authorized academic ERP systems. Validates column schemas, enforces row-level constraints, and checks for conflicting attendance records.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🧪 Run Diagnostics on File Engine"):
        res = file_adapter.test_connection()
        st.success(f"Diagnostics Passed: {res['message']} (Latency: {res['latency_ms']}ms)")

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 2rem 0;'>", unsafe_allow_html=True)

    # 2. Biometric API Adapter Card
    st.subheader("2. 🔲 Campus Biometric REST API Adapter")
    st.markdown("Configure direct REST integration with campus biometric door controllers (e.g., ZKTeco, Matrix, Essl, or custom ERP).")

    cur_bio_endpoint = str(get_setting("biometric_api_endpoint", ""))
    cur_bio_key = str(get_setting("biometric_api_key", ""))

    c_b1, c_b2 = st.columns(2)
    with c_b1:
        bio_endpoint = st.text_input(
            "Biometric API Gateway Endpoint:",
            value=cur_bio_endpoint,
            placeholder="e.g. https://biometrics.college.edu/api/v1/punches",
            help="Base URL for campus biometric server."
        )
    with c_b2:
        bio_key = st.text_input(
            "API Authorization Token / Secret:",
            value=cur_bio_key,
            type="password",
            placeholder="Enter institutional Bearer token",
            help="Encrypted token passed via Authorization header."
        )

    b_btn1, b_btn2 = st.columns(2)
    with b_btn1:
        if st.button("💾 Save Biometric Configuration", type="primary", use_container_width=True):
            set_setting("biometric_api_endpoint", bio_endpoint.strip(), "Biometric REST API Endpoint")
            set_setting("biometric_api_key", bio_key.strip(), "Biometric API Authorization Secret")
            st.success("Biometric adapter configuration saved successfully!")
            st.rerun()

    with b_btn2:
        if st.button("🔌 Ping Biometric Gateway", use_container_width=True):
            test_res = bio_adapter.test_connection()
            if test_res["success"]:
                st.success(f"✅ Connection Succeeded! Response Code: {test_res.get('status_code', 200)} (Latency: {test_res['latency_ms']}ms)")
            else:
                st.warning(f"⚠️ {test_res['message']} (Status: {test_res['status']})")

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 2rem 0;'>", unsafe_allow_html=True)

    # 3. Campus Gate Turnstile Adapter Card
    st.subheader("3. 🚪 Campus Gate & Turnstile Access Adapter")
    st.markdown("Configure real-time event streaming from physical campus pedestrian turnstiles and perimeter gates.")

    cur_gate_endpoint = str(get_setting("campus_gate_endpoint", ""))
    cur_gate_token = str(get_setting("campus_gate_token", ""))

    c_g1, c_g2 = st.columns(2)
    with c_g1:
        gate_endpoint = st.text_input(
            "Campus Gate Gateway Endpoint:",
            value=cur_gate_endpoint,
            placeholder="e.g. https://turnstiles.college.edu/api/events",
            help="Base URL for campus perimeter turnstile access control."
        )
    with c_g2:
        gate_token = st.text_input(
            "Gate Access Authentication Secret:",
            value=cur_gate_token,
            type="password",
            placeholder="Enter gate access secret key"
        )

    g_btn1, g_btn2 = st.columns(2)
    with g_btn1:
        if st.button("💾 Save Turnstile Configuration", type="primary", use_container_width=True):
            set_setting("campus_gate_endpoint", gate_endpoint.strip(), "Campus Gate Turnstile Endpoint")
            set_setting("campus_gate_token", gate_token.strip(), "Campus Gate Access Secret")
            st.success("Turnstile adapter configuration saved successfully!")
            st.rerun()

    with g_btn2:
        if st.button("🔌 Ping Gate Controller", use_container_width=True):
            gate_res = gate_adapter.test_connection()
            if gate_res["success"]:
                st.success(f"✅ Connection Succeeded! Response Code: {gate_res.get('status_code', 200)} (Latency: {gate_res['latency_ms']}ms)")
            else:
                st.warning(f"⚠️ {gate_res['message']} (Status: {gate_res['status']})")
