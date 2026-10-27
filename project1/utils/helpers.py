"""
UI Styling, CSS Injection, KPI Cards, and Visual Helpers
Provides cohesive, enterprise-grade dark glassmorphism styling for the Academic Analytics Platform.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, List, Optional


def load_custom_css():
    """Injects high-end, responsive custom CSS into the Streamlit session."""
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

        :root {
            --bg-canvas: #090D16;
            --bg-surface: #0F172A;
            --bg-card: rgba(17, 24, 39, 0.75);
            --bg-glass: rgba(30, 41, 59, 0.6);
            --border-subtle: rgba(255, 255, 255, 0.08);
            --border-hover: rgba(99, 102, 241, 0.35);
            --primary-gradient: linear-gradient(135deg, #38BDF8 0%, #6366F1 50%, #A855F7 100%);
            --accent-cyan: #38BDF8;
            --accent-indigo: #6366F1;
            --accent-purple: #A855F7;
            --risk-low: #10B981;
            --risk-med: #F59E0B;
            --risk-high: #EF4444;
            --risk-crit: #DC2626;
        }

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #E2E8F0;
        }

        /* App Background */
        .stApp {
            background-color: var(--bg-canvas);
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.08) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(56, 189, 248, 0.05) 0px, transparent 50%);
        }

        /* Top Header Title Styling */
        .main-header-title {
            font-size: 2.1rem;
            font-weight: 800;
            background: linear-gradient(135deg, #38BDF8 0%, #818CF8 50%, #C084FC 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.25rem;
            letter-spacing: -0.025em;
            line-height: 1.2;
        }
        
        .main-header-subtitle {
            color: #94A3B8;
            font-size: 0.92rem;
            font-weight: 500;
            margin-bottom: 1.25rem;
            line-height: 1.4;
        }

        /* Top Executive Breadcrumbs & Status Bar */
        .top-navbar-container {
            background: linear-gradient(90deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.6) 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 0.75rem 1.2rem;
            margin-bottom: 1.4rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            backdrop-filter: blur(16px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }

        .breadcrumb-trail {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.82rem;
            font-weight: 600;
            color: #64748B;
        }

        .breadcrumb-trail .active-crumb {
            color: #38BDF8;
            font-weight: 700;
        }

        .breadcrumb-trail .separator {
            color: #475569;
            font-size: 0.75rem;
        }

        .system-pill-live {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            background: rgba(16, 185, 129, 0.12);
            color: #34D399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 30px;
            padding: 0.25rem 0.75rem;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .live-dot {
            width: 7px;
            height: 7px;
            background-color: #10B981;
            border-radius: 50%;
            box-shadow: 0 0 8px #10B981;
            animation: pulse-dot 2s infinite;
        }

        @keyframes pulse-dot {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        /* Active Filter Chips Bar */
        .filter-chips-bar {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 1rem;
            padding: 0.6rem 0.9rem;
            background: rgba(15, 23, 42, 0.5);
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        .filter-chip {
            background: rgba(99, 102, 241, 0.15);
            border: 1px solid rgba(99, 102, 241, 0.35);
            color: #C7D2FE;
            padding: 0.2rem 0.6rem;
            border-radius: 6px;
            font-size: 0.74rem;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
        }

        /* Sidebar Customization */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0B1120 0%, #060913 100%) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.07) !important;
        }

        /* Sidebar Brand Header */
        .sidebar-brand-card {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1.2rem;
            text-align: center;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        }

        .sidebar-brand-card .brand-title {
            font-size: 1.08rem;
            font-weight: 800;
            background: linear-gradient(90deg, #38BDF8, #818CF8, #C084FC);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.01em;
            margin-bottom: 0.2rem;
        }

        .sidebar-brand-card .brand-tag {
            font-size: 0.68rem;
            font-weight: 600;
            color: #64748B;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        /* Sidebar Mini Metric Strip */
        .sidebar-pulse-strip {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 0.4rem;
            margin-bottom: 1.1rem;
        }

        .pulse-box {
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 8px;
            padding: 0.45rem 0.3rem;
            text-align: center;
        }

        .pulse-box .val {
            font-size: 0.88rem;
            font-weight: 800;
            color: #F8FAFC;
            font-family: 'JetBrains Mono', monospace;
        }

        .pulse-box .lbl {
            font-size: 0.62rem;
            font-weight: 600;
            color: #64748B;
            text-transform: uppercase;
            margin-top: 0.1rem;
        }

        /* Sidebar Category Navigation Section Headers */
        .nav-category-header {
            font-size: 0.68rem;
            font-weight: 800;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-top: 1rem;
            margin-bottom: 0.4rem;
            padding-left: 0.4rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            padding-bottom: 0.25rem;
        }

        /* Radio Buttons Navigation Styling (Looks like Modern SaaS Navigation Menu) */
        div[data-testid="stRadio"] div[role="radiogroup"] {
            gap: 0.3rem !important;
        }

        /* Hide standard round radio indicator */
        div[data-testid="stRadio"] div[role="radiogroup"] > label > div:first-child {
            display: none !important;
        }

        /* Custom Navigation Item Tile */
        div[data-testid="stRadio"] div[role="radiogroup"] > label {
            background: rgba(15, 23, 42, 0.4) !important;
            border: 1px solid rgba(255, 255, 255, 0.04) !important;
            border-radius: 9px !important;
            padding: 0.55rem 0.85rem !important;
            margin: 0 !important;
            transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
            cursor: pointer !important;
            width: 100% !important;
            display: flex !important;
            align-items: center !important;
        }

        div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
            background: rgba(99, 102, 241, 0.12) !important;
            border-color: rgba(99, 102, 241, 0.35) !important;
            transform: translateX(3px) !important;
        }

        /* Active Navigation Item Tile */
        div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked),
        div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"] {
            background: linear-gradient(90deg, rgba(99, 102, 241, 0.25) 0%, rgba(56, 189, 248, 0.08) 100%) !important;
            border: 1px solid rgba(99, 102, 241, 0.5) !important;
            border-left: 3.5px solid #6366F1 !important;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.15) !important;
        }

        div[data-testid="stRadio"] div[role="radiogroup"] > label p {
            font-size: 0.86rem !important;
            font-weight: 600 !important;
            color: #94A3B8 !important;
            margin: 0 !important;
            transition: color 0.15s ease !important;
        }

        div[data-testid="stRadio"] div[role="radiogroup"] > label:hover p {
            color: #E2E8F0 !important;
        }

        div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) p,
        div[data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"] p {
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }

        /* Glassmorphic KPI Cards */
        .kpi-container {
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 1.1rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
            backdrop-filter: blur(12px);
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            margin-bottom: 0.75rem;
            position: relative;
            overflow: hidden;
        }

        .kpi-container::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.15), transparent);
        }

        .kpi-container:hover {
            border-color: rgba(99, 102, 241, 0.4);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        }

        .kpi-title {
            color: #94A3B8;
            font-size: 0.74rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.35rem;
        }

        .kpi-value {
            font-size: 1.75rem;
            font-weight: 800;
            color: #F8FAFC;
            letter-spacing: -0.03em;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        .kpi-subtitle {
            font-size: 0.74rem;
            color: #64748B;
            margin-top: 0.3rem;
            font-weight: 500;
        }

        /* Status & Risk Badges */
        .badge {
            display: inline-block;
            padding: 0.22rem 0.65rem;
            border-radius: 20px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }

        .badge-low {
            background-color: rgba(16, 185, 129, 0.15);
            color: #34D399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .badge-medium {
            background-color: rgba(245, 158, 11, 0.15);
            color: #FBBF24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .badge-high {
            background-color: rgba(239, 68, 68, 0.15);
            color: #F87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .badge-critical {
            background-color: rgba(153, 27, 27, 0.3);
            color: #FCA5A5;
            border: 1px solid rgba(239, 68, 68, 0.6);
            animation: pulse-glow 2s infinite;
        }

        .badge-info {
            background-color: rgba(59, 130, 246, 0.15);
            color: #60A5FA;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }

        /* Reason and Recommendation Callout Cards */
        .analysis-card {
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(51, 65, 85, 0.7);
            border-radius: 12px;
            padding: 1.2rem;
            margin-bottom: 1rem;
        }

        .action-card {
            background: linear-gradient(135deg, rgba(30, 58, 138, 0.35) 0%, rgba(15, 23, 42, 0.8) 100%);
            border: 1px solid rgba(96, 165, 250, 0.3);
            border-radius: 12px;
            padding: 1.2rem;
            margin-bottom: 1rem;
        }

        /* Pulse glow animation for critical risk items */
        @keyframes pulse-glow {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
            70% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }

        /* Streamlit expander styling */
        .streamlit-expanderHeader {
            background: rgba(15, 23, 42, 0.6) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 8px !important;
            font-size: 0.85rem !important;
            font-weight: 600 !important;
        }
        </style>
    """, unsafe_allow_html=True)


def render_enterprise_top_bar(current_nav: str, category_name: str, active_filters: Dict[str, Any] = None, total_students: int = 0, total_records: int = 0):
    """
    Renders an executive top header with dynamic breadcrumbs, live pulse indicator,
    and active filter chips.
    """
    # Active filters chip summary
    chips_html = ""
    if active_filters:
        applied = []
        if active_filters.get("department") and active_filters["department"] != "All":
            applied.append(f"Dept: <b>{active_filters['department']}</b>")
        if active_filters.get("year") and active_filters["year"] != "All":
            applied.append(f"Year: <b>{active_filters['year']}</b>")
        if active_filters.get("section") and active_filters["section"] != "All":
            applied.append(f"Sec: <b>{active_filters['section']}</b>")
        if active_filters.get("subject_id") and active_filters["subject_id"] != "All":
            applied.append(f"Subject Filter Active")
        
        if applied:
            chips_html = '<div class="filter-chips-bar"><span style="font-size: 0.72rem; color: #94A3B8; font-weight: 700; text-transform: uppercase;">Active Scope:</span>'
            for chip in applied:
                chips_html += f'<span class="filter-chip">{chip}</span>'
            chips_html += '</div>'

    html = f"""
    <div class="top-navbar-container">
        <div class="breadcrumb-trail">
            <span>🎓 NEXUS ACADEMIC AI</span>
            <span class="separator">›</span>
            <span>{category_name}</span>
            <span class="separator">›</span>
            <span class="active-crumb">{current_nav}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span style="font-size: 0.75rem; color: #94A3B8; font-weight: 500;">
                <span style="color: #F8FAFC; font-weight: 700;">{total_students}</span> Cohort Students &nbsp;|&nbsp; 
                <span style="color: #F8FAFC; font-weight: 700;">{total_records:,}</span> Logs
            </span>
            <div class="system-pill-live">
                <div class="live-dot"></div>
                <span>Live Engine</span>
            </div>
        </div>
    </div>
    {chips_html}
    """
    st.markdown(html, unsafe_allow_html=True)


def render_kpi_card(title: str, value: str, subtitle: str = "", border_color: str = "#6366F1"):
    """Renders an aesthetic KPI card."""
    html = f"""
    <div class="kpi-container" style="border-left: 4px solid {border_color};">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        {f'<div class="kpi-subtitle">{subtitle}</div>' if subtitle else ''}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def get_risk_badge(level: str, score: Optional[int] = None) -> str:
    """Returns HTML for a colored risk pill."""
    lvl = level.upper()
    css_class = "badge-low"
    if lvl == "MEDIUM":
        css_class = "badge-medium"
    elif lvl == "HIGH":
        css_class = "badge-high"
    elif lvl == "CRITICAL":
        css_class = "badge-critical"

    label = f"{lvl} ({score}/100)" if score is not None else lvl
    return f'<span class="badge {css_class}">{label}</span>'


def format_plotly_theme(fig: go.Figure, title: str = "", height: int = 380) -> go.Figure:
    """Applies a cohesive dark glassmorphic layout theme to Plotly figures."""
    fig.update_layout(
        title={
            "text": f"<b>{title}</b>" if title else "",
            "font": {"size": 15, "color": "#F8FAFC", "family": "Plus Jakarta Sans"}
        },
        paper_bgcolor="rgba(15, 23, 42, 0.4)",
        plot_bgcolor="rgba(15, 23, 42, 0.6)",
        font={"color": "#94A3B8", "family": "Plus Jakarta Sans"},
        height=height,
        margin=dict(l=30, r=30, t=50 if title else 20, b=40),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.05)",
            zeroline=False,
            color="#94A3B8"
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.05)",
            zeroline=False,
            color="#94A3B8"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color="#CBD5E1")
        )
    )
    return fig


def render_empty_state(
    title: str = "No Active Attendance Records Configured",
    description: Optional[str] = None,
    show_templates: Optional[bool] = None,
    **kwargs
) -> None:
    """Renders a clean, enterprise-grade empty state card with guidance and template downloads."""
    from utils.preprocessing import generate_csv_template, generate_excel_template
    
    # Support multiple invocation patterns:
    # 1. render_empty_state("Context message")
    # 2. render_empty_state("Title", "Description")
    # 3. render_empty_state(context_message="Context message")
    # 4. render_empty_state(title="Title", description="Description")
    if description is None:
        if kwargs.get("context_message"):
            card_title = title
            card_desc = kwargs["context_message"]
        else:
            if any(term in title.lower() for term in ["available for", "records found", "to evaluate", "to inspect", "matching current", "for report"]):
                card_title = "No Active Attendance Records Configured"
                card_desc = f"{title}<br>To activate real institutional risk metrics and predictive intelligence, import official college attendance records via <b>CSV</b> or <b>Excel (.xlsx)</b>."
            else:
                card_title = title
                card_desc = "To activate real institutional risk metrics and predictive intelligence, import official college attendance records via <b>CSV</b> or <b>Excel (.xlsx)</b>."
        if show_templates is None:
            show_templates = True
    else:
        card_title = title
        card_desc = description
        if show_templates is None:
            # Determine whether bulk attendance template downloads make sense for this context
            is_non_attendance = any(term in card_title.lower() for term in [
                "import execution", "audit event", "classroom", "laboratory",
                "check-in logs", "qr attendance", "hardware"
            ])
            show_templates = not is_non_attendance and (
                "attendance" in card_title.lower() or "attendance" in card_desc.lower()
            )

    supported_fields_html = ""
    if show_templates:
        supported_fields_html = """
        <div style="
            display: inline-block;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            padding: 0.75rem 1.25rem;
            text-align: left;
            font-size: 0.82rem;
            color: #CBD5E1;
            margin-bottom: 1.5rem;
        ">
            <b style="color: #38BDF8;">📋 Supported Fields:</b> <code>student_id</code>, <code>student_name</code>, <code>department</code>, <code>semester</code>, <code>subject_id</code>, <code>attendance_date</code>, <code>period_number</code>, <code>attendance_status</code>, <code>scheduled_start_time</code>, <code>check_in_time</code>
        </div>
        """

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px dashed rgba(56, 189, 248, 0.35);
        border-radius: 16px;
        padding: 2.5rem 2rem;
        text-align: center;
        margin: 1.5rem 0;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    ">
        <div style="font-size: 2.8rem; margin-bottom: 0.75rem;">📂</div>
        <div style="font-size: 1.4rem; font-weight: 800; color: #F8FAFC; margin-bottom: 0.5rem;">
            {card_title}
        </div>
        <div style="font-size: 0.95rem; color: #94A3B8; max-width: 650px; margin: 0 auto 1.5rem auto; line-height: 1.5;">
            {card_desc}
        </div>
        {supported_fields_html}
    </div>
    """, unsafe_allow_html=True)

    if show_templates:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            st.download_button(
                label="📄 Download Blank CSV Template",
                data=generate_csv_template(),
                file_name="Institutional_Attendance_Template.csv",
                mime="text/csv",
                use_container_width=True
            )
        with col2:
            st.download_button(
                label="📊 Download Blank Excel (.xlsx) Template",
                data=generate_excel_template(),
                file_name="Institutional_Attendance_Template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with col3:
            st.info("Navigate to **📥 Ingestion & Sync Hub** in the sidebar to upload files.")


def render_disclaimer_card(
    message: Optional[str] = None,
    title: str = "⚖️ INSTITUTIONAL DISCREPANCY & ETHICS ADVISORY",
    **kwargs
) -> None:
    """Renders a mandatory ethics, privacy, and administrative disclaimer card."""
    default_msg = (
        "Gate turnstile events do not prove continuous classroom presence. A missing biometric record does not confirm absence. "
        "Wi-Fi connections, device locations, or QR check-ins alone do not prove a student's identity or classroom engagement. "
        "All flagged items represent discrepancies requiring human verification, not confirmed misconduct."
    )
    content = message if message else kwargs.get("text", kwargs.get("content", default_msg))
    header = title if title else kwargs.get("title", "⚖️ INSTITUTIONAL DISCREPANCY & ETHICS ADVISORY")

    st.markdown(f"""
    <div style="
        background: rgba(245, 158, 11, 0.08);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-left: 4px solid #F59E0B;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 1.25rem;
        font-size: 0.8rem;
        color: #FDE68A;
        line-height: 1.45;
    ">
        <b>{header}:</b><br>
        {content}
    </div>
    """, unsafe_allow_html=True)

