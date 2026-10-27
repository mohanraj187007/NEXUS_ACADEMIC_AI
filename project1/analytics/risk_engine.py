"""
Explainable 7-Factor Risk Score Engine & Faculty Action Recommender
Calculates transparent 0-100 risk scores with itemized factor scores,
human-interpretable explanations, and actionable faculty recommendations.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from analytics.trend_analysis import analyze_student_trend
from analytics.pattern_detection import get_all_student_patterns
from analytics.attendance import get_class_benchmarks, get_subject_wise_attendance


from database.database import get_setting


def calculate_student_risk(df: pd.DataFrame, student_id: str, target_threshold: Optional[float] = None) -> Dict[str, Any]:
    """
    Computes a comprehensive 0-100 risk score broken down into 7 explainable factors:
    1. Overall Attendance % Deficit (Max 30 pts)
    2. Recent Trend Velocity (Max 20 pts)
    3. Absence Streak Impact (Max 15 pts)
    4. Subject-Wise Vulnerability (Max 10 pts)
    5. Volatility & Irregularity (Max 10 pts)
    6. Class Benchmark Deficit (Max 5 pts)
    7. Recovery Difficulty Index (Max 10 pts)
    """
    if target_threshold is None:
        target_threshold = float(get_setting("mandatory_attendance_pct", 75.0))

    student_records = df[df["student_id"] == student_id]
    if student_records.empty:
        return {
            "student_id": student_id,
            "risk_score": 0,
            "risk_level": "LOW",
            "factor_breakdown": {},
            "reasons": ["No attendance data available."],
            "recommendations": ["Ensure student registration is valid."]
        }

    total_classes = len(student_records)
    attended_classes = (student_records["status"].isin(["Present", "Late"])).sum()
    att_pct = (attended_classes / total_classes * 100.0) if total_classes > 0 else 0.0

    # 1. Attendance % Risk (Max 30 pts)
    if att_pct >= 85.0:
        pct_risk = 0.0
    elif att_pct >= 75.0:
        pct_risk = (85.0 - att_pct) / 10.0 * 10.0  # 0 to 10 pts
    elif att_pct >= 65.0:
        pct_risk = 10.0 + (75.0 - att_pct) / 10.0 * 12.0  # 10 to 22 pts
    else:
        pct_risk = 22.0 + min(8.0, (65.0 - att_pct) / 65.0 * 8.0 * 2.5)  # 22 to 30 pts
    pct_risk = min(30.0, max(0.0, pct_risk))

    # 2. Recent Trend Velocity Risk (Max 20 pts)
    trend_res = analyze_student_trend(df, student_id=student_id)
    change_pct = trend_res["change_pct"]
    slope = trend_res["slope"]
    
    if change_pct <= -15.0 or (slope <= -3.0 and att_pct < 80.0):
        trend_risk = 20.0
    elif change_pct <= -10.0 or slope <= -2.0:
        trend_risk = 14.0
    elif change_pct <= -5.0 or slope <= -1.0:
        trend_risk = 8.0
    elif change_pct < 0.0:
        trend_risk = 3.0
    else:
        trend_risk = 0.0

    # 3. Absence Streak Risk (Max 15 pts)
    pattern_res = get_all_student_patterns(student_records)
    cur_absent_streak = pattern_res["streaks"]["current_absence_streak"]
    max_absent_streak = pattern_res["streaks"]["longest_absence_streak"]

    if cur_absent_streak >= 5:
        streak_risk = 15.0
    elif cur_absent_streak >= 3:
        streak_risk = 10.0
    elif cur_absent_streak >= 1:
        streak_risk = 4.0
    elif max_absent_streak >= 6:
        streak_risk = 6.0
    else:
        streak_risk = 0.0

    # 4. Subject-Wise Risk (Max 10 pts)
    sub_df = get_subject_wise_attendance(df, student_id=student_id)
    min_sub_pct = sub_df["attendance_pct"].min() if not sub_df.empty else 100.0
    num_subs_below_75 = (sub_df["attendance_pct"] < 75.0).sum() if not sub_df.empty else 0

    if min_sub_pct < 55.0:
        subject_risk = 10.0
    elif min_sub_pct < 65.0:
        subject_risk = 7.0
    elif min_sub_pct < 75.0 or num_subs_below_75 >= 2:
        subject_risk = 4.0
    elif num_subs_below_75 == 1:
        subject_risk = 2.0
    else:
        subject_risk = 0.0

    # 5. Volatility & Irregularity Risk (Max 10 pts)
    volatility = trend_res["volatility"]
    if volatility >= 25.0:
        volatility_risk = 10.0
    elif volatility >= 18.0:
        volatility_risk = 7.0
    elif volatility >= 12.0:
        volatility_risk = 4.0
    else:
        volatility_risk = 0.0

    # 6. Class Benchmark Deficit Risk (Max 5 pts)
    bench_res = get_class_benchmarks(df, student_id=student_id)
    delta_class = bench_res["delta_class"]  # student_pct - class_avg
    if delta_class <= -15.0:
        bench_risk = 5.0
    elif delta_class <= -8.0:
        bench_risk = 3.5
    elif delta_class <= -3.0:
        bench_risk = 2.0
    else:
        bench_risk = 0.0

    # 7. Recovery Difficulty Index (Max 10 pts)
    # Mathematical classes required for 75%
    if att_pct < target_threshold:
        req_consecutive = int(np.ceil((0.75 * total_classes - attended_classes) / (1.0 - 0.75)))
        req_consecutive = max(0, req_consecutive)
        # Scale risk based on difficulty
        if req_consecutive > 20:
            recovery_risk = 10.0
        elif req_consecutive > 10:
            recovery_risk = 7.0
        elif req_consecutive > 5:
            recovery_risk = 4.0
        else:
            recovery_risk = 2.0
    else:
        req_consecutive = 0
        recovery_risk = 0.0

    # Aggregate Total Score
    total_raw = (
        pct_risk + trend_risk + streak_risk + subject_risk +
        volatility_risk + bench_risk + recovery_risk
    )
    risk_score = int(min(100, max(0, round(total_raw))))

    # Categorize Risk Level
    if risk_score <= 30:
        risk_level = "LOW"
        risk_color = "#10B981"  # Emerald Green
    elif risk_score <= 60:
        risk_level = "MEDIUM"
        risk_color = "#F59E0B"  # Amber Orange
    elif risk_score <= 80:
        risk_level = "HIGH"
        risk_color = "#EF4444"  # Coral Red
    else:
        risk_level = "CRITICAL"
        risk_color = "#991B1B"  # Deep Crimson

    # Generate Dynamic Explainable Reasons
    reasons = []
    if att_pct < 75.0:
        reasons.append(f"Overall attendance is {att_pct:.1f}% (below the statutory 75.0% threshold).")
    elif att_pct < 80.0:
        reasons.append(f"Attendance is {att_pct:.1f}%, hovering in the vulnerable buffer zone (75–80%).")

    if change_pct <= -5.0:
        reasons.append(f"Attendance declined by {abs(change_pct):.1f}% over the last 4 weeks.")

    if cur_absent_streak >= 2:
        reasons.append(f"Currently on an active streak of {cur_absent_streak} consecutive unexcused absences.")

    if min_sub_pct < 70.0 and not sub_df.empty:
        worst = sub_df.iloc[0]
        reasons.append(f"Subject deficiency in {worst['subject_code']} ({worst['subject_name']}) at only {worst['attendance_pct']:.1f}%.")

    if delta_class <= -5.0:
        reasons.append(f"Student is {abs(delta_class):.1f}% below the class average of {bench_res['class_avg']:.1f}%.")

    for pat in pattern_res["patterns"]:
        if pat["type"] in ["DAY_BIAS", "HOUR_BIAS"]:
            reasons.append(f"{pat['tag']}: {pat['detail']}")

    if req_consecutive > 0:
        reasons.append(f"Requires {req_consecutive} consecutive attended classes to reach 75.0% compliance.")

    if not reasons:
        reasons.append("Consistent attendance behavior adhering to institutional benchmarks.")

    # Generate Dynamic Faculty Action Recommendations
    recommendations = []
    if risk_level == "CRITICAL":
        recommendations.append("🚨 Immediate 1-on-1 counseling required with Faculty Advisor and HOD.")
        recommendations.append("Formal attendance breach notification to be dispatched to parents/guardians.")
    elif risk_level == "HIGH":
        recommendations.append("⚠️ Schedule faculty mentoring session to identify root causes.")
        recommendations.append("Establish a weekly attendance milestone contract with the student.")
    elif risk_level == "MEDIUM":
        recommendations.append("🔍 Monitor attendance on a weekly basis and issue informal advisory notice.")
        recommendations.append("Encourage student to utilize upcoming review sessions.")
    else:
        recommendations.append("✅ Routine monitoring; student is performing well within safe academic margins.")

    if trend_res["trend_direction"] in ["Declining", "Critical Decline"]:
        recommendations.append("📉 Investigate recent velocity drop — assess sudden workload or personal constraints.")

    if min_sub_pct < 70.0 and not sub_df.empty:
        worst = sub_df.iloc[0]
        recommendations.append(f"📚 Coordinate with course faculty ({worst.get('faculty_name', 'Subject Instructor')}) for {worst['subject_code']}.")

    return {
        "student_id": student_id,
        "attendance_pct": round(att_pct, 2),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "factor_breakdown": {
            "Attendance % Risk (30)": round(pct_risk, 1),
            "Trend Velocity Risk (20)": round(trend_risk, 1),
            "Absence Streak Risk (15)": round(streak_risk, 1),
            "Subject Risk (10)": round(subject_risk, 1),
            "Volatility Risk (10)": round(volatility_risk, 1),
            "Class Benchmark Deficit (5)": round(bench_risk, 1),
            "Recovery Difficulty (10)": round(recovery_risk, 1)
        },
        "reasons": reasons,
        "recommendations": recommendations,
        "streaks": pattern_res["streaks"],
        "trend_direction": trend_res["trend_direction"],
        "required_consecutive": req_consecutive,
        "primary_risk_subject": pattern_res["primary_risk_subject"]
    }


def calculate_cohort_risk_registry(df: pd.DataFrame) -> pd.DataFrame:
    """
    Evaluates the 7-factor risk engine across the entire cohort.
    Returns a unified DataFrame suitable for sorting, filtering, and reporting.
    """
    if df.empty:
        return pd.DataFrame()

    students = df[["student_id", "register_number", "student_name", "department", "year", "section"]].drop_duplicates()
    registry = []

    for _, stu in students.iterrows():
        s_id = stu["student_id"]
        res = calculate_student_risk(df, student_id=s_id)
        registry.append({
            "student_id": s_id,
            "register_number": stu["register_number"],
            "name": stu["student_name"],
            "department": stu["department"],
            "year": stu["year"],
            "section": stu["section"],
            "attendance_pct": res["attendance_pct"],
            "risk_score": res["risk_score"],
            "risk_level": res["risk_level"],
            "trend": res["trend_direction"],
            "current_streak": res["streaks"]["current_absence_streak"],
            "primary_subject": res["primary_risk_subject"] or "None",
            "required_consecutive": res["required_consecutive"],
            "primary_reason": res["reasons"][0] if res["reasons"] else "None",
            "recommended_action": res["recommendations"][0] if res["recommendations"] else "Monitor"
        })

    reg_df = pd.DataFrame(registry)
    return reg_df.sort_values(by=["risk_score", "attendance_pct"], ascending=[False, True]).reset_index(drop=True)
