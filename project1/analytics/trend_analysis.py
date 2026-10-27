"""
Attendance Trend Intelligence Engine
Analyzes historical weekly trends, slope velocities, recent vs prior window deltas,
and classifies students into: Improving, Stable, Declining, Critical Decline, or Fluctuating.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from analytics.attendance import get_weekly_attendance_trend


def analyze_student_trend(df: pd.DataFrame, student_id: str, recent_window_weeks: int = 4) -> Dict[str, Any]:
    """
    Analyzes historical trend trajectory for a specific student.
    Calculates linear slope, moving average deltas, volatility, and categorical trend.
    """
    weekly_df = get_weekly_attendance_trend(df, student_id=student_id)
    if weekly_df.empty or len(weekly_df) < 2:
        return {
            "trend_direction": "Stable",
            "trend_severity": "Normal",
            "recent_avg": 0.0,
            "previous_avg": 0.0,
            "change_pct": 0.0,
            "slope": 0.0,
            "volatility": 0.0,
            "weekly_data": weekly_df,
            "summary_text": "Insufficient weekly data to evaluate trend."
        }

    total_weeks = len(weekly_df)
    
    # Partition into recent window and prior baseline
    if total_weeks <= recent_window_weeks:
        split_idx = max(1, total_weeks // 2)
        prior_df = weekly_df.iloc[:split_idx]
        recent_df = weekly_df.iloc[split_idx:]
    else:
        prior_df = weekly_df.iloc[:-recent_window_weeks]
        recent_df = weekly_df.iloc[-recent_window_weeks:]

    prior_avg = prior_df["attendance_pct"].mean() if not prior_df.empty else 0.0
    recent_avg = recent_df["attendance_pct"].mean() if not recent_df.empty else 0.0
    change_pct = recent_avg - prior_avg

    # Linear regression slope across weeks
    x = weekly_df["week"].values
    y = weekly_df["attendance_pct"].values
    
    if len(x) > 1 and np.var(x) > 0:
        slope, _ = np.polyfit(x, y, 1)
    else:
        slope = 0.0

    volatility = float(np.std(y)) if len(y) > 1 else 0.0

    # Categorization logic
    if change_pct <= -15.0 or (slope <= -3.0 and recent_avg < 75.0):
        direction = "Critical Decline"
        severity = "Critical"
        summary_text = f"Consistently critical drop: attendance plunged by {abs(change_pct):.1f}% recently (recent avg: {recent_avg:.1f}% vs prior {prior_avg:.1f}%)."
    elif change_pct <= -5.0 or slope <= -1.2:
        direction = "Declining"
        severity = "Moderate"
        summary_text = f"Declining trend detected: attendance decreased by {abs(change_pct):.1f}% over the last {len(recent_df)} weeks."
    elif change_pct >= 5.0 and slope >= 1.0:
        direction = "Improving"
        severity = "Positive"
        summary_text = f"Improving trend: attendance gained +{change_pct:.1f}% recently (recent avg: {recent_avg:.1f}%)."
    elif volatility > 18.0:
        direction = "Fluctuating"
        severity = "Warning"
        summary_text = f"Erratic attendance pattern: high weekly volatility (std dev ±{volatility:.1f}%)."
    else:
        direction = "Stable"
        severity = "Normal"
        summary_text = f"Consistent attendance trajectory across {total_weeks} recorded weeks."

    return {
        "trend_direction": direction,
        "trend_severity": severity,
        "recent_avg": round(float(recent_avg), 2),
        "previous_avg": round(float(prior_avg), 2),
        "change_pct": round(float(change_pct), 2),
        "slope": round(float(slope), 2),
        "volatility": round(float(volatility), 2),
        "weekly_data": weekly_df,
        "summary_text": summary_text
    }


def get_cohort_trend_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes the trend direction and change percentage for all students in the cohort.
    """
    students = df["student_id"].unique()
    records = []

    for s_id in students:
        s_data = df[df["student_id"] == s_id]
        if s_data.empty:
            continue
        first = s_data.iloc[0]
        res = analyze_student_trend(df, student_id=s_id)
        records.append({
            "student_id": s_id,
            "register_number": first.get("register_number", ""),
            "name": first.get("student_name", ""),
            "department": first.get("department", ""),
            "year": first.get("year", 0),
            "section": first.get("section", ""),
            "trend_direction": res["trend_direction"],
            "trend_severity": res["trend_severity"],
            "recent_avg": res["recent_avg"],
            "previous_avg": res["previous_avg"],
            "change_pct": res["change_pct"],
            "slope": res["slope"]
        })

    return pd.DataFrame(records)
