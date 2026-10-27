"""
Absence Pattern Detection & Streak Analysis Engine
Identifies behavioral anomalies, day-of-week biases, hour/time clustering,
subject-specific avoidance, and streaks (current & historical max).
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional


def calculate_attendance_streaks(student_records: pd.DataFrame) -> Dict[str, int]:
    """
    Computes current and longest streaks of consecutive Present and Absent classes.
    Chronologically sorted.
    """
    if student_records.empty:
        return {
            "current_present_streak": 0,
            "current_absence_streak": 0,
            "longest_present_streak": 0,
            "longest_absence_streak": 0
        }

    sorted_records = student_records.sort_values(by=["date", "hour"]).reset_index(drop=True)
    statuses = sorted_records["status"].tolist()

    longest_present = 0
    longest_absent = 0
    cur_p = 0
    cur_a = 0

    for st in statuses:
        if st == "Present":
            cur_p += 1
            cur_a = 0
            if cur_p > longest_present:
                longest_present = cur_p
        else:
            cur_a += 1
            cur_p = 0
            if cur_a > longest_absent:
                longest_absent = cur_a

    # Determine current trailing streak from end of list
    last_status = statuses[-1]
    trailing_count = 0
    for st in reversed(statuses):
        if st == last_status:
            trailing_count += 1
        else:
            break

    current_present = trailing_count if last_status == "Present" else 0
    current_absent = trailing_count if last_status == "Absent" else 0

    return {
        "current_present_streak": current_present,
        "current_absence_streak": current_absent,
        "longest_present_streak": longest_present,
        "longest_absence_streak": longest_absent,
        "longest_absent_streak": longest_absent
    }


def analyze_day_of_week_pattern(student_records: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyzes absence patterns across Monday to Friday.
    """
    if student_records.empty:
        return {"patterns": [], "day_stats": pd.DataFrame()}

    df = student_records.copy()
    df["date_dt"] = pd.to_datetime(df["date"])
    df["day_name"] = df["date_dt"].dt.day_name()
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    day_stats = df.groupby("day_name").agg(
        total_classes=("status", "count"),
        absent_classes=("status", lambda s: (s == "Absent").sum())
    ).reset_index()

    # Reindex by standard work week
    day_stats["day_name"] = pd.Categorical(day_stats["day_name"], categories=day_order, ordered=True)
    day_stats = day_stats.sort_values("day_name").reset_index(drop=True)
    day_stats["absence_rate"] = (day_stats["absent_classes"] / day_stats["total_classes"] * 100.0).round(1)

    overall_absence_rate = (df["status"] == "Absent").sum() / len(df) * 100.0
    detected_patterns = []

    for _, row in day_stats.iterrows():
        d_name = row["day_name"]
        d_rate = row["absence_rate"]
        # Trigger if day absence rate is >= 35% and at least 1.6x overall absence rate
        if d_rate >= 35.0 and (d_rate >= 1.5 * overall_absence_rate or d_rate >= 50.0):
            detected_patterns.append({
                "type": "DAY_BIAS",
                "tag": f"Frequent {d_name} Absence",
                "detail": f"High absence rate of {d_rate:.1f}% on {d_name}s (overall cohort absence is {overall_absence_rate:.1f}%).",
                "severity": "High" if d_rate > 50 else "Medium"
            })

    return {
        "patterns": detected_patterns,
        "day_stats": day_stats,
        "overall_absence_rate": round(overall_absence_rate, 1)
    }


def analyze_hour_pattern(student_records: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyzes absence patterns by class hour / time slot (Hour 1 to Hour 6).
    """
    if student_records.empty:
        return {"patterns": [], "hour_stats": pd.DataFrame()}

    df = student_records.copy()
    hour_stats = df.groupby("hour").agg(
        total_classes=("status", "count"),
        absent_classes=("status", lambda s: (s == "Absent").sum())
    ).reset_index()
    
    hour_stats["absence_rate"] = (hour_stats["absent_classes"] / hour_stats["total_classes"] * 100.0).round(1)
    overall_absence_rate = (df["status"] == "Absent").sum() / len(df) * 100.0
    detected_patterns = []

    # Check Hour 1 (Morning punctuality)
    h1_row = hour_stats[hour_stats["hour"] == 1]
    if not h1_row.empty:
        h1_rate = h1_row.iloc[0]["absence_rate"]
        if h1_rate >= 40.0 and h1_rate >= 1.5 * overall_absence_rate:
            detected_patterns.append({
                "type": "HOUR_BIAS",
                "tag": "Frequent 1st Hour Absence",
                "detail": f"Morning punctuality deficit: {h1_rate:.1f}% absence in 1st hour classes.",
                "severity": "Medium"
            })

    # Check Last Hour (Post-lunch / early departure)
    max_h = hour_stats["hour"].max()
    last_row = hour_stats[hour_stats["hour"] == max_h]
    if not last_row.empty:
        last_rate = last_row.iloc[0]["absence_rate"]
        if last_rate >= 40.0 and last_rate >= 1.5 * overall_absence_rate:
            detected_patterns.append({
                "type": "HOUR_BIAS",
                "tag": "Frequent Late Hour Absence",
                "detail": f"End-of-day absenteeism: {last_rate:.1f}% absence in final hour {max_h}.",
                "severity": "Medium"
            })

    return {
        "patterns": detected_patterns,
        "hour_stats": hour_stats
    }


def analyze_subject_clustering(student_records: pd.DataFrame) -> Dict[str, Any]:
    """
    Detects if absences are disproportionately clustered in specific subjects.
    """
    if student_records.empty:
        return {"patterns": [], "subject_stats": pd.DataFrame(), "primary_risk_subject": None}

    df = student_records.copy()
    sub_stats = df.groupby(["subject_id", "subject_code", "subject_name"]).agg(
        total_classes=("status", "count"),
        absent_classes=("status", lambda s: (s == "Absent").sum())
    ).reset_index()

    sub_stats["absence_rate"] = (sub_stats["absent_classes"] / sub_stats["total_classes"] * 100.0).round(1)
    sub_stats["attendance_pct"] = 100.0 - sub_stats["absence_rate"]
    sub_stats = sub_stats.sort_values(by="absence_rate", ascending=False).reset_index(drop=True)

    detected_patterns = []
    primary_risk_subject = None

    if not sub_stats.empty:
        worst_sub = sub_stats.iloc[0]
        if worst_sub["attendance_pct"] < 70.0:
            primary_risk_subject = f"{worst_sub['subject_code']} - {worst_sub['subject_name']}"
            detected_patterns.append({
                "type": "SUBJECT_CLUSTERING",
                "tag": f"Repeated Absence in {worst_sub['subject_code']}",
                "detail": f"Subject vulnerability: {worst_sub['attendance_pct']:.1f}% attendance in {worst_sub['subject_name']}.",
                "severity": "High" if worst_sub["attendance_pct"] < 60.0 else "Medium"
            })

    return {
        "patterns": detected_patterns,
        "subject_stats": sub_stats,
        "primary_risk_subject": primary_risk_subject
    }


def get_all_student_patterns(student_records: pd.DataFrame) -> Dict[str, Any]:
    """
    Aggregates all behavioral pattern detections into a unified intelligence report.
    """
    streaks = calculate_attendance_streaks(student_records)
    day_res = analyze_day_of_week_pattern(student_records)
    hour_res = analyze_hour_pattern(student_records)
    sub_res = analyze_subject_clustering(student_records)

    all_patterns = []
    all_patterns.extend(day_res["patterns"])
    all_patterns.extend(hour_res["patterns"])
    all_patterns.extend(sub_res["patterns"])

    if streaks["current_absence_streak"] >= 3:
        all_patterns.append({
            "type": "STREAK",
            "tag": f"{streaks['current_absence_streak']} Consecutive Absences",
            "detail": f"Active unexcused streak: student missed last {streaks['current_absence_streak']} consecutive classes.",
            "severity": "Critical" if streaks["current_absence_streak"] >= 5 else "High"
        })

    return {
        "streaks": streaks,
        "patterns": all_patterns,
        "day_stats": day_res["day_stats"],
        "hour_stats": hour_res["hour_stats"],
        "subject_stats": sub_res["subject_stats"],
        "primary_risk_subject": sub_res["primary_risk_subject"]
    }
