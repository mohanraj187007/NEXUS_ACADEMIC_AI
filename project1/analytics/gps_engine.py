"""
GPS Campus Geofence Validation Engine
Academic Attendance Pattern & Risk Analytics System
Validates user coordinates against configured campus boundary using the Haversine formula.
Operates on-demand with zero background tracking and logs verification provenance.
"""

import math
from typing import Dict, Any, Tuple, Optional
import pandas as pd
from database.database import get_campuses, record_gps_checkin, DB_PATH


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates great-circle distance between two geographic coordinates in meters
    using the Haversine formula.
    """
    R = 6371000.0  # Earth's mean radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def evaluate_geofence(
    user_lat: float,
    user_lon: float,
    campus_lat: float,
    campus_lon: float,
    radius_meters: float
) -> Tuple[bool, float, str, str]:
    """
    Evaluates whether a coordinate point falls within the campus geofence boundary.
    Returns: (is_inside, distance_meters, status_label, descriptive_message)
    """
    dist_meters = haversine_distance_meters(user_lat, user_lon, campus_lat, campus_lon)

    if dist_meters <= radius_meters:
        return (
            True,
            dist_meters,
            "VERIFIED_INSIDE",
            f"Coordinates verified inside campus boundary ({dist_meters:.1f}m from center, radius: {radius_meters:.0f}m)."
        )
    else:
        excess = dist_meters - radius_meters
        return (
            False,
            dist_meters,
            "DENIED_OUTSIDE_GEOFENCE",
            f"Check-in rejected: Location is {dist_meters:.1f}m from campus center ({excess:.1f}m outside allowed {radius_meters:.0f}m geofence)."
        )


def execute_gps_checkin(
    institution_id: str,
    campus_id: str,
    user_id: str,
    user_lat: float,
    user_lon: float,
    device_info: str = "Web Browser Geolocation",
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """
    Executes an on-demand campus check-in:
    1. Looks up target campus coordinates and geofence radius.
    2. Calculates distance using Haversine formula.
    3. Records the check-in attempt and verification outcome into the database.
    """
    campuses_df = get_campuses(institution_id=institution_id, db_path=db_path)
    if campuses_df.empty:
        # Fallback to campus lookup without institution filter
        campuses_df = get_campuses(db_path=db_path)

    campus_row = campuses_df[campuses_df["campus_id"] == campus_id]
    if campus_row.empty:
        if not campuses_df.empty:
            campus_row = campuses_df.iloc[[0]]
            campus_id = campus_row["campus_id"].values[0]
        else:
            return {
                "success": False,
                "verification_status": "CAMPUS_NOT_FOUND",
                "distance_meters": 0.0,
                "message": f"Campus '{campus_id}' not found in institution database."
            }

    c_lat = float(campus_row["latitude"].values[0])
    c_lon = float(campus_row["longitude"].values[0])
    radius = float(campus_row["geofence_radius_meters"].values[0])
    campus_name = str(campus_row["name"].values[0])

    is_inside, dist_m, status_label, msg = evaluate_geofence(
        user_lat=user_lat,
        user_lon=user_lon,
        campus_lat=c_lat,
        campus_lon=c_lon,
        radius_meters=radius
    )

    checkin_id = record_gps_checkin(
        institution_id=institution_id,
        campus_id=campus_id,
        user_id=user_id,
        latitude=user_lat,
        longitude=user_lon,
        distance_meters=dist_m,
        verification_status=status_label,
        device_info=device_info,
        db_path=db_path
    )

    return {
        "success": is_inside,
        "checkin_id": checkin_id,
        "campus_id": campus_id,
        "campus_name": campus_name,
        "verification_status": status_label,
        "distance_meters": dist_m,
        "geofence_radius_meters": radius,
        "message": msg
    }
