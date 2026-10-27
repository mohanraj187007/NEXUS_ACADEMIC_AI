"""
Early Warning & Predictive Trajectory Engine
Projects forward-looking attendance trajectories across 2 to 4 weeks,
identifying students at imminent risk of breaching compliance thresholds.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
from analytics.attendance import get_weekly_attendance_trend
from analytics.trend_analysis import analyze_student_trend
from analytics.risk_engine import calculate_student_risk


def predict_student_trajectory(df: pd.DataFrame, student_id: str, lookahead_weeks: int = 3, classes_per_week: int = 25) -> Dict[str, Any]:
    """
    Simulates attendance trajectory over the next `lookahead_weeks`
    using historical weekly trend slope and recent moving averages.
    """
    student_records = df[df["student_id"] == student_id]
    if student_records.empty:
        return {}

    total_classes = len(student_records)
    attended_classes = (student_records["status"] == "Present").sum()
    current_pct = (attended_classes / total_classes * 100.0) if total_classes > 0 else 0.0

    weekly_df = get_weekly_attendance_trend(df, student_id=student_id)
    trend_res = analyze_student_trend(df, student_id=student_id)
    risk_res = calculate_student_risk(df, student_id=student_id)

    recent_avg_pct = trend_res["recent_avg"] if trend_res["recent_avg"] > 0 else current_pct
    slope = trend_res["slope"]

    # Weighted projected attendance rate for future weeks
    # If slope is negative, future rate continues decaying down to a floor
    decayed_future_rate = max(20.0, min(100.0, recent_avg_pct + (slope * (lookahead_weeks / 2.0))))
    
    future_classes_total = lookahead_weeks * classes_per_week
    future_classes_attended = future_classes_total * (decayed_future_rate / 100.0)

    projected_total = total_classes + future_classes_total
    projected_attended = attended_classes + future_classes_attended
    projected_pct = (projected_attended / projected_total * 100.0)

    # Determine Warning Status
    if projected_pct < 70.0:
        warning_status = "CRITICAL_RISK_IMMINENT"
        warning_tag = "🚨 Imminent Critical Breach"
        warning_desc = f"Projected to fall to {projected_pct:.1f}% within {lookahead_weeks} weeks if recent pattern continues."
    elif current_pct >= 75.0 and projected_pct < 75.0:
        warning_status = "BREACH_WARNING"
        warning_tag = "⚠️ Imminent 75% Breach"
        warning_desc = f"Currently safe at {current_pct:.1f}%, but trajectory projects a drop to {projected_pct:.1f}% (<75%)."
    elif current_pct < 80.0 and trend_res["trend_direction"] in ["Declining", "Critical Decline"]:
        warning_status = "BORDERLINE_WATCHLIST"
        warning_tag = "📉 Borderline Watchlist"
        warning_desc = f"Hovering at {current_pct:.1f}% with negative velocity (Δ {trend_res['change_pct']:.1f}%)."
    else:
        warning_status = "SAFE_TRAJECTORY"
        warning_tag = "✅ Safe Trajectory"
        warning_desc = f"Attendance expected to remain stable at ~{projected_pct:.1f}%."

    return {
        "student_id": student_id,
        "current_pct": round(current_pct, 1),
        "recent_avg_pct": round(recent_avg_pct, 1),
        "current_risk_score": risk_res["risk_score"],
        "current_risk_level": risk_res["risk_level"],
        "trend_direction": trend_res["trend_direction"],
        "projected_pct": round(projected_pct, 1),
        "lookahead_weeks": lookahead_weeks,
        "warning_status": warning_status,
        "warning_tag": warning_tag,
        "warning_desc": warning_desc,
        "weekly_data": weekly_df
    }


def get_early_warning_registry(df: pd.DataFrame, lookahead_weeks: int = 3) -> pd.DataFrame:
    """
    Generates an early warning watchlist for all students.
    """
    students = df[["student_id", "register_number", "student_name", "department", "year", "section"]].drop_duplicates()
    records = []

    for _, stu in students.iterrows():
        s_id = stu["student_id"]
        pred = predict_student_trajectory(df, student_id=s_id, lookahead_weeks=lookahead_weeks)
        if pred:
            records.append({
                "student_id": s_id,
                "register_number": stu["register_number"],
                "name": stu["student_name"],
                "department": stu["department"],
                "year": stu["year"],
                "section": stu["section"],
                "current_pct": pred["current_pct"],
                "projected_pct": pred["projected_pct"],
                "current_risk": pred["current_risk_level"],
                "current_score": pred["current_risk_score"],
                "trend": pred["trend_direction"],
                "warning_status": pred["warning_status"],
                "warning_tag": pred["warning_tag"],
                "warning_desc": pred["warning_desc"]
            })

    warn_df = pd.DataFrame(records)
    # Sort with highest warning priorities first
    priority_order = {"CRITICAL_RISK_IMMINENT": 1, "BREACH_WARNING": 2, "BORDERLINE_WATCHLIST": 3, "SAFE_TRAJECTORY": 4}
    warn_df["priority"] = warn_df["warning_status"].map(priority_order)
    return warn_df.sort_values(by=["priority", "projected_pct"]).drop(columns=["priority"]).reset_index(drop=True)
