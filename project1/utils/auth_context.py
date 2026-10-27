"""
Multi-Tenant Context & Role-Based Access Control (RBAC) Module
Academic Attendance Pattern & Risk Analytics System (NEXUS ACADEMIC AI)

Manages secure session context, token verification, role-based authorization boundaries,
student privacy isolation, and granular permission enforcement across the application.
"""

import streamlit as st
from typing import Dict, Any, List, Optional
from database.database import (
    validate_session_token, revoke_session, log_auth_audit,
    get_all_institutions
)

# Canonical Enterprise Roles
ROLE_ADMINISTRATOR = "Administrator"
ROLE_COORDINATOR = "Academic Coordinator"
ROLE_FACULTY = "Faculty"
ROLE_STUDENT = "Student"

CANONICAL_ROLES = [
    ROLE_ADMINISTRATOR,
    ROLE_COORDINATOR,
    ROLE_FACULTY,
    ROLE_STUDENT
]

# Legacy role alias mapping
ROLE_ALIAS_MAP = {
    "admin": ROLE_ADMINISTRATOR,
    "super admin": ROLE_ADMINISTRATOR,
    "college admin": ROLE_ADMINISTRATOR,
    "campus admin": ROLE_ADMINISTRATOR,
    "administrator": ROLE_ADMINISTRATOR,
    "hod": ROLE_COORDINATOR,
    "academic coordinator": ROLE_COORDINATOR,
    "academic counselor": ROLE_COORDINATOR,
    "auditor": ROLE_COORDINATOR,
    "counselor": ROLE_COORDINATOR,
    "faculty": ROLE_FACULTY,
    "professor": ROLE_FACULTY,
    "student": ROLE_STUDENT
}


def normalize_role(raw_role: Optional[str]) -> str:
    """Normalizes any role string into one of the 4 canonical enterprise roles."""
    if not raw_role:
        return ROLE_STUDENT
    clean = raw_role.strip().lower()
    return ROLE_ALIAS_MAP.get(clean, raw_role)


def init_auth_session() -> None:
    """
    Initializes session state from in-memory session or validates persistent
    session token from Streamlit query parameters.
    """
    if "authenticated_user" in st.session_state and st.session_state["authenticated_user"]:
        return

    # Check query params for persistent session token
    query_params = st.query_params
    token = query_params.get("session_token")
    if token:
        user_session = validate_session_token(token)
        if user_session:
            user_session["role"] = normalize_role(user_session.get("role"))
            st.session_state["authenticated_user"] = user_session
            st.session_state["session_token"] = token
            st.session_state["auth_role"] = user_session["role"]
            st.session_state["auth_institution_id"] = user_session.get("institution_id", "INST_001")
            st.session_state["auth_campus_id"] = user_session.get("campus_id", "CAMP_001")
            st.session_state["auth_user_name"] = user_session.get("full_name", user_session.get("username"))
        else:
            # Token expired or invalid
            query_params.pop("session_token", None)
            st.session_state["session_expired"] = True


def get_current_user() -> Optional[Dict[str, Any]]:
    """Returns the authenticated user dictionary, or None if unauthenticated."""
    init_auth_session()
    return st.session_state.get("authenticated_user")


def is_authenticated() -> bool:
    """Checks whether a valid authenticated user session is active."""
    return get_current_user() is not None


def set_user_session(user_dict: Dict[str, Any], token: Optional[str] = None, remember_me: bool = False) -> None:
    """Establishes authenticated user state in session and query parameters."""
    norm_role = normalize_role(user_dict.get("role"))
    user_dict["role"] = norm_role

    st.session_state["authenticated_user"] = user_dict
    st.session_state["auth_role"] = norm_role
    st.session_state["auth_institution_id"] = user_dict.get("institution_id", "INST_001")
    st.session_state["auth_campus_id"] = user_dict.get("campus_id", "CAMP_001")
    st.session_state["auth_department_id"] = user_dict.get("department_id")
    st.session_state["auth_user_name"] = user_dict.get("full_name", user_dict.get("username"))

    if token:
        st.session_state["session_token"] = token
        st.query_params["session_token"] = token

    # Clear auth transient navigation flags
    st.session_state.pop("auth_page", None)
    st.session_state.pop("session_expired", None)
    st.session_state.pop("unauthorized_module", None)


def logout_current_user() -> None:
    """Invalidates active session token in database and clears all session states."""
    token = st.session_state.get("session_token") or st.query_params.get("session_token")
    user = st.session_state.get("authenticated_user")

    if token:
        revoke_session(token)

    if user:
        log_auth_audit(
            event_type="LOGOUT",
            user_id=user.get("user_id"),
            username=user.get("username"),
            ip_address="127.0.0.1",
            user_agent="Web Client",
            details="User signed out successfully"
        )

    # Clean session state
    st.session_state.pop("authenticated_user", None)
    st.session_state.pop("session_token", None)
    st.session_state.pop("auth_role", None)
    st.session_state.pop("target_student_id", None)
    st.session_state.pop("quick_student_search", None)
    st.session_state.pop("unauthorized_module", None)

    # Clean query parameters
    st.query_params.pop("session_token", None)
    st.query_params.pop("module", None)


def get_user_role() -> str:
    """Returns the normalized role of the current user."""
    user = get_current_user()
    if not user:
        return ROLE_STUDENT
    return normalize_role(user.get("role"))


def is_administrator() -> bool:
    return get_user_role() == ROLE_ADMINISTRATOR


def is_academic_coordinator() -> bool:
    return get_user_role() in [ROLE_ADMINISTRATOR, ROLE_COORDINATOR]


def is_faculty() -> bool:
    return get_user_role() == ROLE_FACULTY


def is_student() -> bool:
    return get_user_role() == ROLE_STUDENT


# =====================================================================
# ROLE-BASED ACCESS CONTROL (RBAC) RULES & PERMISSIONS
# =====================================================================

MODULE_PERMISSIONS = {
    # 1. Executive Overview
    "📊 Executive Overview": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY],
    # 2. Student 360° Profile
    "👤 Student 360° Profile": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY, ROLE_STUDENT],
    # 3. Subject Intelligence
    "📚 Subject Intelligence": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY],
    # 4. 7-Factor Risk & ML
    "🎯 7-Factor Risk & ML": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR],
    # 5. Absence Pattern Intelligence
    "🔍 Absence Pattern Intelligence": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR],
    # 6. Early Warning Forecast
    "⚠️ Early Warning Forecast": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR],
    # 7. Campus Infrastructure
    "🏛️ Campus Infrastructure": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR],
    # 8. Dynamic QR Attendance
    "📱 Dynamic QR Attendance": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY, ROLE_STUDENT],
    # 9. GPS Campus Check-In
    "📍 GPS Campus Check-In": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY, ROLE_STUDENT],
    # 10. Multi-Source Reconciliation
    "⚖️ Multi-Source Reconciliation": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY],
    # 11. Attendance Recovery Simulator
    "🧮 Recovery Simulator": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY, ROLE_STUDENT],
    # 12. Action & Alert Center
    "🚨 Action & Alert Center": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR],
    # 13. Ingestion & Sync Hub
    "📥 Ingestion & Sync Hub": [ROLE_ADMINISTRATOR],
    # 14. Hardware & Vendor Integrations
    "🔌 Hardware & Vendor Integrations": [ROLE_ADMINISTRATOR],
    # 15. Audit & Reports Hub
    "📄 Audit & Reports Hub": [ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY, ROLE_STUDENT],
    # 16. System & Academic Rules
    "⚙️ System & Academic Rules": [ROLE_ADMINISTRATOR]
}


def can_access_module(role: str, module_name: str) -> bool:
    """Server-side authorization check enforcing access boundaries."""
    norm_role = normalize_role(role)
    allowed_roles = MODULE_PERMISSIONS.get(module_name)
    if not allowed_roles:
        return False
    return norm_role in allowed_roles


def filter_navigation_for_role(nav_suites: Dict[str, Any], role: str) -> Dict[str, Any]:
    """
    Returns only the navigation suites and items that the specified role
    is authorized to access, preventing unauthorized menu exposure.
    """
    norm_role = normalize_role(role)
    filtered = {}

    for suite_title, suite_data in nav_suites.items():
        permitted_items = {}
        for item_label, item_meta in suite_data.get("items", {}).items():
            if can_access_module(norm_role, item_label):
                permitted_items[item_label] = item_meta
        if permitted_items:
            filtered[suite_title] = {
                "icon": suite_data.get("icon", "📌"),
                "items": permitted_items
            }

    return filtered


# Granular Action Permissions
def can_import_data() -> bool:
    return is_administrator()


def can_manage_infrastructure() -> bool:
    return is_administrator()


def can_start_qr_session() -> bool:
    return get_user_role() in [ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY]


def can_adjudicate_reconciliation() -> bool:
    return get_user_role() in [ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY]


def can_edit_settings() -> bool:
    return is_administrator()


def can_manage_users() -> bool:
    return is_administrator()


def can_view_all_students() -> bool:
    return get_user_role() in [ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_FACULTY]


def render_user_profile_card(user: Dict[str, Any]) -> None:
    """Renders user identity, role pill, tenant indicator, and sign-out button."""
    role = user.get("role", "Faculty")
    full_name = user.get("full_name") or user.get("username") or "Institutional User"
    email = user.get("email", "")
    inst_id = user.get("institution_id", "INST_001")

    # Role badge color palette
    role_colors = {
        ROLE_ADMINISTRATOR: ("#DC2626", "rgba(220, 38, 38, 0.15)", "🛡️ Administrator"),
        ROLE_COORDINATOR: ("#8B5CF6", "rgba(139, 92, 246, 0.15)", "⚖️ Academic Coordinator"),
        ROLE_FACULTY: ("#38BDF8", "rgba(56, 189, 248, 0.15)", "🎓 Faculty Member"),
        ROLE_STUDENT: ("#10B981", "rgba(16, 185, 129, 0.15)", "👤 Enrolled Student")
    }
    border_col, bg_col, role_badge_lbl = role_colors.get(role, ("#38BDF8", "rgba(56, 189, 248, 0.15)", role))

    email_html = f'<div style="font-size: 0.72rem; color: #64748B; margin-top: 2px;">{email}</div>' if email else ""

    st.markdown(f"""
    <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 0.85rem; margin-bottom: 1rem;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem;">
            <div style="font-size: 0.68rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.08em;">AUTHENTICATED USER</div>
            <span style="font-size: 0.65rem; font-weight: 700; color: {border_col}; background: {bg_col}; border: 1px solid {border_col}44; padding: 2px 7px; border-radius: 20px;">
                {role_badge_lbl}
            </span>
        </div>
        <div style="font-size: 0.92rem; font-weight: 800; color: #F8FAFC;">{full_name}</div>
        {email_html}
        <div style="font-size: 0.72rem; color: #38BDF8; margin-top: 4px;">Tenant: <b>{inst_id}</b></div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Sign Out", key="sidebar_sign_out_btn", use_container_width=True, type="secondary"):
        logout_current_user()
        st.rerun()


def render_tenant_and_role_switcher() -> None:
    """
    Renders the active tenant badge and user profile in the sidebar.
    """
    user = get_current_user()
    if user:
        render_user_profile_card(user)
