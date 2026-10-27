"""
Core Attendance Analytics Module
Calculates aggregate attendance rates using institutional formula:
Attendance % = (Attended eligible sessions / Total eligible scheduled sessions) * 100
Configurable handling of cancelled classes, approved leave, holidays, and excused absences.
Provides daily, weekly, monthly trends, department benchmarks, late arrival analytics,
and threshold proximity monitoring.
"""

import pandas as pd
import numpy as np
import datetime
from typing import Dict, Any, Optional, List, Tuple
from database.database import get_setting


def compute_session_eligibility(status: str, excused_rule: str = "exclude_from_total") -> Tuple[bool, bool]:
    """
    Determines whether a record is an eligible scheduled session and whether it counts as attended.
    Returns (is_eligible_session, is_attended_session).
    """
    st_clean = str(status).strip()
    
    # Cancelled classes are never counted as scheduled eligible sessions
    if st_clean == "Cancelled":
        return False, False
        
    # Standard Present
    if st_clean == "Present":
        return True, True
        
    # Late arrival is attended
    if st_clean == "Late":
        return True, True
        
    # Unexcused Absent
    if st_clean == "Absent":
        return True, False
        
    # Excused / Approved Leave
    if st_clean in ["Excused", "Approved Leave"]:
        if excused_rule == "count_as_attended":
            return True, True
        elif excused_rule == "exclude_from_total":
            return False, False  # Excluded from both numerator and denominator
        else: # neutral
            return False, False

    # Unknown / Unrecorded status: do NOT count as confirmed absence
    return False, False


def calculate_overall_metrics(df: pd.DataFrame, excused_rule: Optional[str] = None, threshold: Optional[float] = None) -> Dict[str, Any]:
    """
    Computes top-level attendance metrics from attendance records using the institutional formula.
    """
    if excused_rule is None:
        excused_rule = str(get_setting("excused_absence_rule", "exclude_from_total"))
    if threshold is None:
        threshold = float(get_setting("mandatory_attendance_pct", 75.0))

    if df.empty:
        return {
            "total_records": 0,
            "total_students": 0,
            "overall_attendance_pct": 0.0,
            "total_present": 0,
            "total_absent": 0,
            "total_late": 0,
            "total_excused": 0,
            "total_cancelled": 0,
            "eligible_sessions": 0,
            "attended_eligible": 0,
            "total_subjects": 0,
            "students_below_threshold": 0,
            "students_approaching_threshold": 0
        }

    total_records = len(df)
    total_present = int((df["status"] == "Present").sum())
    total_absent = int((df["status"] == "Absent").sum())
    total_late = int((df["status"] == "Late").sum())
    total_excused = int(df["status"].isin(["Excused", "Approved Leave"]).sum())
    total_cancelled = int((df["status"] == "Cancelled").sum())

    # Calculate eligible and attended counts row by row
    eligibility = [compute_session_eligibility(st, excused_rule) for st in df["status"]]
    eligible_sessions = sum(1 for is_el, _ in eligibility if is_el)
    attended_eligible = sum(1 for _, is_att in eligibility if is_att)

    pct = (attended_eligible / eligible_sessions * 100.0) if eligible_sessions > 0 else 0.0

    # Student-level threshold counts
    student_summaries = get_all_students_summary(df, excused_rule=excused_rule)
    below_thresh = int((student_summaries["attendance_pct"] < threshold).sum()) if not student_summaries.empty else 0
    approaching_thresh = int(((student_summaries["attendance_pct"] >= threshold) & (student_summaries["attendance_pct"] <= threshold + 5.0)).sum()) if not student_summaries.empty else 0

    return {
        "total_records": int(total_records),
        "total_students": int(df["student_id"].nunique()),
        "overall_attendance_pct": round(pct, 2),
        "total_present": total_present,
        "total_absent": total_absent,
        "total_late": total_late,
        "total_excused": total_excused,
        "total_cancelled": total_cancelled,
        "eligible_sessions": eligible_sessions,
        "attended_eligible": attended_eligible,
        "total_subjects": int(df["subject_id"].nunique()) if "subject_id" in df.columns else 0,
        "students_below_threshold": below_thresh,
        "students_approaching_threshold": approaching_thresh
    }


def calculate_student_summary(df: pd.DataFrame, student_id: str, excused_rule: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes detailed attendance metrics for an individual student.
    """
    if excused_rule is None:
        excused_rule = str(get_setting("excused_absence_rule", "exclude_from_total"))

    student_records = df[df["student_id"] == student_id].sort_values(by=["date", "hour"] if "hour" in df.columns else ["date"])
    if student_records.empty:
        return {}

    first_row = student_records.iloc[0]
    total_logs = len(student_records)

    eligibility = [compute_session_eligibility(st, excused_rule) for st in student_records["status"]]
    eligible_sessions = sum(1 for is_el, _ in eligibility if is_el)
    attended_eligible = sum(1 for _, is_att in eligibility if is_att)
    unexcused_absent = (student_records["status"] == "Absent").sum()
    late_count = (student_records["status"] == "Late").sum()
    excused_count = student_records["status"].isin(["Excused", "Approved Leave"]).sum()

    attendance_pct = (attended_eligible / eligible_sessions * 100.0) if eligible_sessions > 0 else 0.0

    return {
        "student_id": student_id,
        "register_number": first_row.get("register_number", student_id),
        "student_name": first_row.get("student_name", f"Student {student_id}"),
        "department": first_row.get("department", "General"),
        "year": int(first_row.get("year", 1)),
        "semester": int(first_row.get("semester", 1)),
        "section": first_row.get("section", "A"),
        "total_classes": int(eligible_sessions if eligible_sessions > 0 else total_logs),
        "total_logs": int(total_logs),
        "attended_classes": int(attended_eligible),
        "missed_classes": int(unexcused_absent),
        "late_classes": int(late_count),
        "excused_classes": int(excused_count),
        "attendance_pct": round(attendance_pct, 2)
    }


def get_all_students_summary(df: pd.DataFrame, excused_rule: Optional[str] = None) -> pd.DataFrame:
    """
    Aggregates attendance for all students into a clean summary table with metadata.
    """
    if df.empty:
        return pd.DataFrame()

    if excused_rule is None:
        excused_rule = str(get_setting("excused_absence_rule", "exclude_from_total"))

    group_cols = ["student_id", "register_number", "student_name", "department", "year", "section"]
    for c in ["semester"]:
        if c in df.columns:
            group_cols.append(c)

    # Calculate student level summaries
    records = []
    for s_id, group in df.groupby("student_id"):
        first_row = group.iloc[0]
        eligibility = [compute_session_eligibility(st, excused_rule) for st in group["status"]]
        eligible_sessions = sum(1 for is_el, _ in eligibility if is_el)
        attended_eligible = sum(1 for _, is_att in eligibility if is_att)
        unexcused_absent = (group["status"] == "Absent").sum()
        late_count = (group["status"] == "Late").sum()
        excused_count = group["status"].isin(["Excused", "Approved Leave"]).sum()
        pct = (attended_eligible / eligible_sessions * 100.0) if eligible_sessions > 0 else 0.0

        records.append({
            "student_id": s_id,
            "register_number": first_row.get("register_number", s_id),
            "student_name": first_row.get("student_name", f"Student {s_id}"),
            "department": first_row.get("department", "General"),
            "year": int(first_row.get("year", 1)),
            "semester": int(first_row.get("semester", 1)),
            "section": first_row.get("section", "A"),
            "total_classes": eligible_sessions if eligible_sessions > 0 else len(group),
            "attended_classes": attended_eligible,
            "missed_classes": unexcused_absent,
            "late_classes": late_count,
            "excused_classes": excused_count,
            "attendance_pct": round(pct, 2)
        })

    res_df = pd.DataFrame(records)
    return res_df.sort_values(by="attendance_pct", ascending=True).reset_index(drop=True)


def get_subject_wise_attendance(df: pd.DataFrame, student_id: Optional[str] = None, excused_rule: Optional[str] = None) -> pd.DataFrame:
    """
    Calculates attendance rate grouped by subject (for a single student or cohort).
    """
    if excused_rule is None:
        excused_rule = str(get_setting("excused_absence_rule", "exclude_from_total"))

    data = df if student_id is None else df[df["student_id"] == student_id]
    if data.empty:
        return pd.DataFrame(columns=["subject_id", "subject_code", "subject_name", "faculty_name", "total_classes", "attended", "missed", "attendance_pct", "risk_level"])

    group_keys = [c for c in ["subject_id", "subject_code", "subject_name", "faculty_name"] if c in data.columns]
    if not group_keys:
        return pd.DataFrame()

    records = []
    for keys, grp in data.groupby(group_keys):
        if not isinstance(keys, tuple):
            keys = (keys,)
        key_dict = dict(zip(group_keys, keys))
        
        eligibility = [compute_session_eligibility(st, excused_rule) for st in grp["status"]]
        eligible_sessions = sum(1 for is_el, _ in eligibility if is_el)
        attended_eligible = sum(1 for _, is_att in eligibility if is_att)
        missed = (grp["status"] == "Absent").sum()
        pct = (attended_eligible / eligible_sessions * 100.0) if eligible_sessions > 0 else 0.0

        row = {**key_dict}
        row["total_classes"] = eligible_sessions if eligible_sessions > 0 else len(grp)
        row["attended"] = attended_eligible
        row["missed"] = missed
        row["attendance_pct"] = round(pct, 2)
        
        if pct >= 85.0:
            row["risk_level"] = "Low Risk"
        elif pct >= 75.0:
            row["risk_level"] = "Moderate Risk"
        elif pct >= 65.0:
            row["risk_level"] = "High Risk"
        else:
            row["risk_level"] = "Critical Risk"

        records.append(row)

    res_df = pd.DataFrame(records)
    return res_df.sort_values(by="attendance_pct", ascending=True).reset_index(drop=True)


def get_department_wise_attendance(df: pd.DataFrame, excused_rule: Optional[str] = None) -> pd.DataFrame:
    """
    Calculates aggregate attendance rate and student count by academic department.
    """
    if df.empty or "department" not in df.columns:
        return pd.DataFrame(columns=["department", "total_students", "total_classes", "attended", "attendance_pct"])

    if excused_rule is None:
        excused_rule = str(get_setting("excused_absence_rule", "exclude_from_total"))

    records = []
    for dept, grp in df.groupby("department"):
        eligibility = [compute_session_eligibility(st, excused_rule) for st in grp["status"]]
        eligible_sessions = sum(1 for is_el, _ in eligibility if is_el)
        attended_eligible = sum(1 for _, is_att in eligibility if is_att)
        pct = (attended_eligible / eligible_sessions * 100.0) if eligible_sessions > 0 else 0.0

        records.append({
            "department": dept,
            "total_students": int(grp["student_id"].nunique()),
            "total_classes": eligible_sessions if eligible_sessions > 0 else len(grp),
            "attended": attended_eligible,
            "attendance_pct": round(pct, 2)
        })

    res_df = pd.DataFrame(records)
    return res_df.sort_values(by="attendance_pct", ascending=False).reset_index(drop=True)


def get_weekly_attendance_trend(df: pd.DataFrame, student_id: Optional[str] = None) -> pd.DataFrame:
    """
    Calculates week-by-week attendance percentages.
    """
    data = df if student_id is None else df[df["student_id"] == student_id]
    if data.empty or "week" not in data.columns:
        return pd.DataFrame(columns=["week", "total_classes", "attended", "attendance_pct"])

    weekly = data.groupby("week").agg(
        total_classes=("status", "count"),
        attended=("status", lambda s: (s.isin(["Present", "Late"])).sum())
    ).reset_index()

    weekly["attendance_pct"] = (weekly["attended"] / weekly["total_classes"] * 100.0).round(2)
    return weekly.sort_values(by="week", ascending=True)


def get_periodic_trends(df: pd.DataFrame, frequency: str = "daily") -> pd.DataFrame:
    """
    Calculates daily, weekly, or monthly attendance trends.
    frequency: 'daily', 'weekly', 'monthly'.
    """
    if df.empty or "date" not in df.columns:
        return pd.DataFrame()

    df_copy = df.copy()
    df_copy["dt"] = pd.to_datetime(df_copy["date"])

    if frequency == "daily":
        df_copy["period"] = df_copy["dt"].dt.strftime("%Y-%m-%d")
    elif frequency == "monthly":
        df_copy["period"] = df_copy["dt"].dt.strftime("%Y-%m")
    else:  # weekly
        if "week" in df_copy.columns:
            df_copy["period"] = df_copy["week"].apply(lambda w: f"Week {w}")
        else:
            df_copy["period"] = df_copy["dt"].dt.strftime("%Y-W%U")

    grouped = df_copy.groupby("period").agg(
        total_sessions=("status", "count"),
        attended=("status", lambda s: (s.isin(["Present", "Late"])).sum()),
        absent=("status", lambda s: (s == "Absent").sum()),
        late=("status", lambda s: (s == "Late").sum())
    ).reset_index()

    grouped["attendance_pct"] = (grouped["attended"] / grouped["total_sessions"] * 100.0).round(2)
    return grouped


def get_class_benchmarks(df: pd.DataFrame, student_id: str) -> Dict[str, Any]:
    """
    Compares a student's attendance against the class, department, and section averages.
    """
    student_records = df[df["student_id"] == student_id]
    if student_records.empty:
        return {"student_pct": 0.0, "class_avg": 0.0, "dept_avg": 0.0, "section_avg": 0.0, "delta_class": 0.0}

    student_pct = (student_records["status"].isin(["Present", "Late"])).sum() / len(student_records) * 100.0
    dept = student_records.iloc[0].get("department", "")
    sec = student_records.iloc[0].get("section", "")
    yr = student_records.iloc[0].get("year", 1)

    class_avg = (df["status"].isin(["Present", "Late"])).sum() / len(df) * 100.0

    dept_df = df[df["department"] == dept]
    dept_avg = (dept_df["status"].isin(["Present", "Late"])).sum() / len(dept_df) * 100.0 if not dept_df.empty else class_avg

    sec_df = df[(df["department"] == dept) & (df["year"] == yr) & (df["section"] == sec)]
    sec_avg = (sec_df["status"].isin(["Present", "Late"])).sum() / len(sec_df) * 100.0 if not sec_df.empty else class_avg

    return {
        "student_pct": round(student_pct, 2),
        "class_avg": round(class_avg, 2),
        "dept_avg": round(dept_avg, 2),
        "section_avg": round(sec_avg, 2),
        "delta_class": round(student_pct - class_avg, 2),
        "delta_dept": round(student_pct - dept_avg, 2),
        "delta_section": round(student_pct - sec_avg, 2)
    }


def get_data_quality_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detects data-quality anomalies: unrecorded periods, missing dates, or irregular timestamps.
    """
    if df.empty or "date" not in df.columns:
        return pd.DataFrame()

    records = []
    # Check for students with uncharacteristically sparse attendance logs
    student_counts = df.groupby(["student_id", "register_number", "student_name"]).size().reset_index(name="log_count")
    median_logs = student_counts["log_count"].median()

    if median_logs > 0:
        sparse_students = student_counts[student_counts["log_count"] < (median_logs * 0.4)]
        for _, row in sparse_students.iterrows():
            records.append({
                "student_id": row["student_id"],
                "student_name": row["student_name"],
                "anomaly_type": "Sparse Attendance Records",
                "severity": "Medium",
                "details": f"Only {row['log_count']} logs recorded compared to cohort median of {int(median_logs)}."
            })

    # Check for dates with anomalous class cancellations or drop in logging
    date_counts = df.groupby("date").size().reset_index(name="session_count")
    median_sessions = date_counts["session_count"].median()
    if median_sessions > 0:
        low_dates = date_counts[date_counts["session_count"] < (median_sessions * 0.25)]
        for _, d_row in low_dates.iterrows():
            records.append({
                "student_id": "COHORT_WIDE",
                "student_name": "Multiple Students",
                "anomaly_type": "Suspected Unrecorded Class Day",
                "severity": "Low",
                "details": f"Date {d_row['date']} has only {d_row['session_count']} attendance entries (cohort baseline {int(median_sessions)})."
            })

    return pd.DataFrame(records)
