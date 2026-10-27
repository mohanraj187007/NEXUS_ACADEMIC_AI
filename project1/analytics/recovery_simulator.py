"""
Mathematical Attendance Recovery Simulator & What-If Scenario Matrix Engine
Computes exact consecutive classes required to reach compliance targets (75%, 80%, 85%)
and calculates hypothetical future attendance & risk state transitions.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List


def calculate_recovery_roadmap(total_classes: int, attended_classes: int, remaining_classes: int = 40) -> Dict[str, Any]:
    """
    Computes rigorous mathematical recovery metrics:
    - Formula for target T: k = ceil((T * total - attended) / (1 - T))
    """
    if total_classes <= 0:
        return {}

    current_pct = (attended_classes / total_classes * 100.0)
    
    def classes_needed_for_target(target_pct: float) -> int:
        T = target_pct / 100.0
        if current_pct >= target_pct:
            return 0
        if T >= 1.0:
            return 999
        k = int(np.ceil((T * total_classes - attended_classes) / (1.0 - T)))
        return max(0, k)

    req_75 = classes_needed_for_target(75.0)
    req_80 = classes_needed_for_target(80.0)
    req_85 = classes_needed_for_target(85.0)

    # Max potential attendance if student attends 100% of all remaining classes
    max_possible_attended = attended_classes + remaining_classes
    max_possible_total = total_classes + remaining_classes
    max_potential_pct = (max_possible_attended / max_possible_total * 100.0)

    is_75_achievable = req_75 <= remaining_classes

    # Number of upcoming classes the student can afford to miss without dropping below 75%
    # (attended) / (total + m) >= 0.75 => attended >= 0.75 * total + 0.75 * m => m = (attended - 0.75 * total) / 0.75
    if current_pct > 75.0:
        safe_misses = int(np.floor((attended_classes - 0.75 * total_classes) / 0.75))
        safe_misses = max(0, safe_misses)
    else:
        safe_misses = 0

    return {
        "current_pct": round(current_pct, 2),
        "total_classes": total_classes,
        "attended_classes": attended_classes,
        "missed_classes": total_classes - attended_classes,
        "remaining_classes": remaining_classes,
        "req_consecutive_75": req_75,
        "req_consecutive_80": req_80,
        "req_consecutive_85": req_85,
        "max_potential_pct": round(max_potential_pct, 1),
        "is_75_achievable": is_75_achievable,
        "safe_missable_classes": safe_misses
    }


def simulate_what_if_scenario(
    total_classes: int,
    attended_classes: int,
    upcoming_classes: int,
    upcoming_attended: int,
    current_risk_score: int
) -> Dict[str, Any]:
    """
    Simulates a custom 'What-If' scenario with specified upcoming class attendances.
    """
    projected_total = total_classes + upcoming_classes
    projected_attended = attended_classes + upcoming_attended
    projected_pct = (projected_attended / projected_total * 100.0) if projected_total > 0 else 0.0

    # Risk score delta approximation
    current_pct = (attended_classes / total_classes * 100.0) if total_classes > 0 else 0.0
    pct_delta = projected_pct - current_pct

    # Adjust risk score based on attendance percentage gain/loss
    projected_risk_score = int(np.clip(current_risk_score - (pct_delta * 1.8), 0, 100))

    if projected_risk_score <= 30:
        projected_level = "LOW"
        color = "#10B981"
    elif projected_risk_score <= 60:
        projected_level = "MEDIUM"
        color = "#F59E0B"
    elif projected_risk_score <= 80:
        projected_level = "HIGH"
        color = "#EF4444"
    else:
        projected_level = "CRITICAL"
        color = "#991B1B"

    return {
        "projected_total": projected_total,
        "projected_attended": projected_attended,
        "projected_pct": round(projected_pct, 2),
        "projected_risk_score": projected_risk_score,
        "projected_risk_level": projected_level,
        "projected_color": color,
        "pct_delta": round(pct_delta, 2)
    }


def generate_standard_scenario_matrix(total_classes: int, attended_classes: int, current_risk_score: int) -> pd.DataFrame:
    """
    Generates comparative What-If scenarios (e.g. Attend next 5, 10, 15, Miss next 3, 5).
    """
    scenarios = [
        {"name": "Attend Next 5 Classes", "upcoming": 5, "attended": 5, "desc": "100% attendance in next 5"},
        {"name": "Attend Next 10 Classes", "upcoming": 10, "attended": 10, "desc": "100% attendance in next 10"},
        {"name": "Attend Next 20 Classes", "upcoming": 20, "attended": 20, "desc": "100% attendance in next 20"},
        {"name": "80% Attendance in Next 15 Classes", "upcoming": 15, "attended": 12, "desc": "12 of next 15 attended"},
        {"name": "Miss Next 3 Classes", "upcoming": 3, "attended": 0, "desc": "0 of next 3 attended"},
        {"name": "Miss Next 6 Classes", "upcoming": 6, "attended": 0, "desc": "0 of next 6 attended"}
    ]

    rows = []
    for sc in scenarios:
        res = simulate_what_if_scenario(
            total_classes=total_classes,
            attended_classes=attended_classes,
            upcoming_classes=sc["upcoming"],
            upcoming_attended=sc["attended"],
            current_risk_score=current_risk_score
        )
        rows.append({
            "Scenario": sc["name"],
            "Description": sc["desc"],
            "Projected Attendance %": f"{res['projected_pct']:.1f}%",
            "Delta": f"{'+' if res['pct_delta'] >= 0 else ''}{res['pct_delta']:.1f}%",
            "Projected Risk Score": f"{res['projected_risk_score']}/100",
            "Projected Risk Level": res["projected_risk_level"]
        })

    return pd.DataFrame(rows)
