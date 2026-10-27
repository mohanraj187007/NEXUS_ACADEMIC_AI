"""
Attendance Anomaly Detection Engine
Applies statistical Z-Score and rolling delta thresholding to flag sudden,
unusual shifts in attendance behavior.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from analytics.attendance import get_weekly_attendance_trend


def detect_student_anomaly(df: pd.DataFrame, student_id: str, threshold_z: float = 1.6) -> Dict[str, Any]:
    """
    Detects sudden attendance drops compared against the student's historical baseline.
    """
    weekly_df = get_weekly_attendance_trend(df, student_id=student_id)
    if weekly_df.empty or len(weekly_df) < 3:
        return {
            "has_anomaly": False,
            "anomaly_type": None,
            "baseline_pct": 0.0,
            "recent_pct": 0.0,
            "delta_pct": 0.0,
            "z_score": 0.0,
            "description": "Insufficient history for anomaly evaluation."
        }

    rates = weekly_df["attendance_pct"].values
    
    # Check if the most recent 1-2 weeks have a severe sudden plunge
    # Compare recent 2 weeks vs earlier weeks
    recent_len = min(2, len(weekly_df) // 2)
    prior_rates = rates[:-recent_len]
    recent_rates = rates[-recent_len:]

    baseline_mean = float(np.mean(prior_rates))
    baseline_std = float(np.std(prior_rates))
    recent_mean = float(np.mean(recent_rates))
    delta = recent_mean - baseline_mean

    # Avoid zero division
    effective_std = max(baseline_std, 5.0)
    z_score = (recent_mean - baseline_mean) / effective_std

    has_anomaly = False
    anomaly_type = None
    description = "Normal consistent attendance."

    # Anomaly conditions:
    # 1. Historical baseline was healthy (> 75%), but recent window dropped by >= 25%
    # 2. Or statistical Z-score < -threshold_z with substantial drop (> 20%)
    if baseline_mean >= 75.0 and delta <= -25.0:
        has_anomaly = True
        anomaly_type = "CRITICAL_DROP"
        description = f"Severe sudden plunge: baseline was {baseline_mean:.1f}%, but dropped to {recent_mean:.1f}% recently (Δ -{abs(delta):.1f}%)."
    elif delta <= -20.0 and z_score <= -threshold_z:
        has_anomaly = True
        anomaly_type = "STATISTICAL_PLUNGE"
        description = f"Statistical anomaly detected: {abs(delta):.1f}% drop below historical baseline (Z = {z_score:.2f})."

    return {
        "has_anomaly": has_anomaly,
        "anomaly_type": anomaly_type,
        "baseline_pct": round(baseline_mean, 1),
        "recent_pct": round(recent_mean, 1),
        "delta_pct": round(delta, 1),
        "z_score": round(float(z_score), 2),
        "description": description
    }


def scan_cohort_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Scans all students in the cohort and returns a table of flagged anomalies.
    """
    students = df["student_id"].unique()
    anomalies = []

    for s_id in students:
        res = detect_student_anomaly(df, student_id=s_id)
        if res["has_anomaly"]:
            s_rows = df[df["student_id"] == s_id]
            first = s_rows.iloc[0]
            anomalies.append({
                "student_id": s_id,
                "register_number": first.get("register_number", ""),
                "name": first.get("student_name", ""),
                "department": first.get("department", ""),
                "year": first.get("year", 0),
                "section": first.get("section", ""),
                "anomaly_type": res["anomaly_type"],
                "baseline_pct": res["baseline_pct"],
                "recent_pct": res["recent_pct"],
                "delta_pct": res["delta_pct"],
                "z_score": res["z_score"],
                "description": res["description"]
            })

    return pd.DataFrame(anomalies)
