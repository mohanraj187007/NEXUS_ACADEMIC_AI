"""
Synthetic Academic Data Generator
Generates realistic attendance records for 100+ students across multiple subjects and weeks,
accurately simulating distinct behavioral archetypes:
- High Performers (88-98%)
- Chronic Low Attendance (<65%)
- Consistently Declining Trajectories
- Improving/Recovery Trajectories
- Subject-Specific Absentees (e.g., AI or Maths aversion)
- Day-of-Week Skippers (Monday/Friday clustering)
- Hour 1 / Morning Chronic Absentees
- Sudden Anomaly Plunges
"""

import os
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Seed for reproducible realistic data
random.seed(42)
np.random.seed(42)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_CSV_PATH = os.path.join(DATA_DIR, "sample_attendance.csv")

DEPARTMENTS = ["Computer Science", "Information Technology", "AI & Data Science", "Electronics & Comm"]
SECTIONS = ["A", "B"]
YEARS = [2, 3]

FIRST_NAMES = [
    "Aarav", "Aditi", "Akash", "Ananya", "Arjun", "Bhavya", "Chetan", "Deepak", "Divya", "Eshwar",
    "Gautam", "Gayathri", "Harish", "Ishaan", "Janani", "Karthik", "Kavya", "Keerthi", "Lokesh", "Madhav",
    "Meera", "Mithun", "Nandhini", "Naveen", "Nikhil", "Nithya", "Pavithra", "Pranav", "Pooja", "Rahul",
    "Rajesh", "Rakshita", "Rithika", "Rohan", "Sanjay", "Santhosh", "Saravanan", "Shalini", "Shreya", "Siddharth",
    "Sneha", "Srikanth", "Sudhir", "Surya", "Swetha", "Tarun", "Vaishnavi", "Varun", "Vignesh", "Vikram",
    "Vishal", "Yogesh", "Abinaya", "Ajay", "Aravind", "Archana", "Ashwin", "Balaji", "Chandran", "Deepika",
    "Dinesh", "Ganesh", "Geetha", "Hariharan", "Hemalatha", "Indira", "Jagadeesh", "Jeevitha", "Kamalesh", "Kishore",
    "Lakshmi", "Manikandan", "Manju", "Manoj", "Monisha", "Mukesh", "Muralidharan", "Nalini", "Narendran", "Pavithran",
    "Praveen", "Priyanka", "Raghavan", "Ramkumar", "Revathi", "Rohit", "Sabari", "Sandhya", "Saran", "Sasikumar",
    "Sathish", "Shanmugam", "Sharanya", "Shiva", "Sindhu", "Sowmya", "Srinivasan", "Subash", "Suresh", "Thanush",
    "Uma", "Vasanth", "Venkatesh", "Vijay", "Vinoth", "Yuvan"
]

LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Patel", "Rao", "Gupta", "Menon", "Krishnan",
    "Sundaram", "Balaji", "Karthikeyan", "Subramanian", "Natarajan", "Ramaswamy", "Venkatesan",
    "Choudhury", "Pillai", "Bhatt", "Deshmukh", "Joshi", "Naidu", "Shetty", "Chatterjee", "Banerjee"
]

SUBJECTS_DEF = [
    {"subject_id": "SUB_CS301", "subject_code": "CS301", "subject_name": "Data Structures & Algorithms", "faculty_name": "Prof. R. Venkatesh"},
    {"subject_id": "SUB_CS302", "subject_code": "CS302", "subject_name": "Operating Systems", "faculty_name": "Dr. Ananya Sharma"},
    {"subject_id": "SUB_CS303", "subject_code": "CS303", "subject_name": "Database Management Systems", "faculty_name": "Prof. K. Sundaram"},
    {"subject_id": "SUB_CS304", "subject_code": "CS304", "subject_name": "Artificial Intelligence & ML", "faculty_name": "Dr. Priya Nair"},
    {"subject_id": "SUB_CS305", "subject_code": "CS305", "subject_name": "Discrete Mathematics", "faculty_name": "Prof. S. Balaji"},
    {"subject_id": "SUB_CS306", "subject_code": "CS306", "subject_name": "Computer Networks", "faculty_name": "Dr. M. Karthik"}
]


def generate_students(num_students: int = 104) -> pd.DataFrame:
    """Generates synthetic student profiles with assigned behavioral archetypes."""
    students = []
    archetypes = (
        ["REGULAR_HIGH"] * 44 +          # ~42%
        ["CHRONIC_LOW"] * 12 +           # ~12%
        ["DECLINING_TREND"] * 14 +       # ~13%
        ["IMPROVING_TREND"] * 8 +        # ~8%
        ["SUBJECT_STRUGGLER_AI"] * 6 +   # ~6%
        ["SUBJECT_STRUGGLER_MATH"] * 4 + # ~4%
        ["MONDAY_SKIPPER"] * 5 +         # ~5%
        ["FRIDAY_SKIPPER"] * 4 +         # ~4%
        ["MORNING_HOUR1_SKIPPER"] * 4 +  # ~4%
        ["SUDDEN_ANOMALY_DROP"] * 3      # ~3%
    )
    random.shuffle(archetypes)
    
    for i in range(num_students):
        fname = FIRST_NAMES[i % len(FIRST_NAMES)]
        lname = LAST_NAMES[(i * 3 + 7) % len(LAST_NAMES)]
        name = f"{fname} {lname}"
        dept = DEPARTMENTS[i % len(DEPARTMENTS)]
        yr = YEARS[(i // 2) % len(YEARS)]
        sec = SECTIONS[(i // 4) % len(SECTIONS)]
        reg_no = f"21{dept[:2].upper()}{yr}{sec}{101 + i:03d}"
        s_id = f"STU_{1001 + i}"
        archetype = archetypes[i % len(archetypes)]
        
        students.append({
            "student_id": s_id,
            "register_number": reg_no,
            "name": name,
            "department": dept,
            "year": yr,
            "section": sec,
            "email": f"{fname.lower()}.{lname.lower()[:3]}{101+i}@college.edu",
            "archetype": archetype
        })
        
    return pd.DataFrame(students)


def generate_attendance_dataset(students_df: pd.DataFrame, num_weeks: int = 14) -> pd.DataFrame:
    """
    Generates 14 weeks of attendance records based on student archetypes.
    Schedule: Mon-Fri, 5 hours/day, 1 subject per hour (rotating schedule).
    """
    start_date = datetime(2024, 1, 8)  # A Monday
    subjects = SUBJECTS_DEF
    
    # Weekly timetable mapping: Day of week (0=Mon, 4=Fri) -> list of 5 subject indices
    timetable = {
        0: [0, 1, 2, 3, 4], # Mon: CS301, CS302, CS303, CS304, CS305
        1: [1, 2, 3, 4, 5], # Tue: CS302, CS303, CS304, CS305, CS306
        2: [2, 3, 4, 5, 0], # Wed: CS303, CS304, CS305, CS306, CS301
        3: [3, 4, 5, 0, 1], # Thu: CS304, CS305, CS306, CS301, CS302
        4: [4, 5, 0, 1, 2], # Fri: CS305, CS306, CS301, CS302, CS303
    }
    
    records = []
    
    for week in range(1, num_weeks + 1):
        for day_idx in range(5):  # Mon-Fri
            current_date = start_date + timedelta(weeks=week - 1, days=day_idx)
            date_str = current_date.strftime("%Y-%m-%d")
            day_of_week = day_idx  # 0=Mon, 4=Fri
            
            daily_subjects = timetable[day_idx]
            
            for hour_idx, sub_idx in enumerate(daily_subjects, start=1):
                subject = subjects[sub_idx]
                sub_id = subject["subject_id"]
                sub_code = subject["subject_code"]
                
                for _, student in students_df.iterrows():
                    s_id = student["student_id"]
                    arch = student["archetype"]
                    
                    # Calculate attendance probability based on archetype
                    prob_present = 0.95  # Default baseline
                    
                    if arch == "REGULAR_HIGH":
                        prob_present = random.uniform(0.92, 0.98)
                        
                    elif arch == "CHRONIC_LOW":
                        prob_present = random.uniform(0.45, 0.62)
                        
                    elif arch == "DECLINING_TREND":
                        # Starts high, progressively plunges
                        if week <= 4:
                            prob_present = 0.92
                        elif week <= 8:
                            prob_present = 0.78
                        elif week <= 11:
                            prob_present = 0.65
                        else:
                            prob_present = 0.48
                            
                    elif arch == "IMPROVING_TREND":
                        # Starts low, steadily recovers
                        if week <= 4:
                            prob_present = 0.60
                        elif week <= 8:
                            prob_present = 0.74
                        elif week <= 11:
                            prob_present = 0.88
                        else:
                            prob_present = 0.95
                            
                    elif arch == "SUBJECT_STRUGGLER_AI":
                        if sub_code == "CS304":  # AI Subject
                            prob_present = random.uniform(0.40, 0.55)
                        else:
                            prob_present = random.uniform(0.88, 0.96)
                            
                    elif arch == "SUBJECT_STRUGGLER_MATH":
                        if sub_code == "CS305":  # Discrete Maths
                            prob_present = random.uniform(0.42, 0.58)
                        else:
                            prob_present = random.uniform(0.90, 0.97)
                            
                    elif arch == "MONDAY_SKIPPER":
                        if day_of_week == 0:  # Monday
                            prob_present = 0.38
                        else:
                            prob_present = random.uniform(0.90, 0.96)
                            
                    elif arch == "FRIDAY_SKIPPER":
                        if day_of_week == 4:  # Friday
                            prob_present = 0.35
                        else:
                            prob_present = random.uniform(0.89, 0.96)
                            
                    elif arch == "MORNING_HOUR1_SKIPPER":
                        if hour_idx == 1:  # 1st Hour
                            prob_present = 0.30
                        else:
                            prob_present = random.uniform(0.92, 0.98)
                            
                    elif arch == "SUDDEN_ANOMALY_DROP":
                        if week <= 11:
                            prob_present = random.uniform(0.90, 0.96)
                        else:  # Sudden drop in last 3 weeks
                            prob_present = random.uniform(0.35, 0.48)
                            
                    status = "Present" if random.random() < prob_present else "Absent"
                    
                    records.append({
                        "student_id": s_id,
                        "subject_id": sub_id,
                        "date": date_str,
                        "status": status,
                        "hour": hour_idx,
                        "week": week
                    })
                    
    return pd.DataFrame(records)


def generate_and_seed_database(num_students: int = 104, num_weeks: int = 14, db_path: str = None) -> dict:
    """Generates all synthetic entities and writes to SQLite database and CSV."""
    from database.database import init_db, reset_database, insert_students_bulk, insert_subjects_bulk, insert_attendance_bulk, get_database_summary, DB_PATH
    
    target_db = db_path if db_path is not None else DB_PATH
    reset_database(target_db)
    
    # 1. Generate Students
    students_df = generate_students(num_students)
    clean_students_df = students_df.drop(columns=["archetype"])
    insert_students_bulk(clean_students_df, db_path=target_db)
    
    # 2. Subjects
    subjects_df = pd.DataFrame(SUBJECTS_DEF)
    insert_subjects_bulk(subjects_df, db_path=target_db)
    
    # 3. Attendance
    attendance_df = generate_attendance_dataset(students_df, num_weeks=num_weeks)
    insert_attendance_bulk(attendance_df, db_path=target_db)
    
    # Also export combined sample CSV for user testing/upload demo
    full_sample_df = attendance_df.merge(
        students_df[["student_id", "register_number", "name", "department", "year", "section"]],
        on="student_id"
    ).merge(
        subjects_df[["subject_id", "subject_code", "subject_name"]],
        on="subject_id"
    )
    
    # Reorder columns cleanly for CSV export
    csv_export_df = full_sample_df[[
        "student_id", "register_number", "name", "department", "year", "section",
        "subject_code", "subject_name", "date", "status", "hour", "week"
    ]]
    try:
        csv_export_df.to_csv(SAMPLE_CSV_PATH, index=False)
    except Exception:
        pass
    
    summary = get_database_summary(db_path=target_db)
    return summary


if __name__ == "__main__":
    print("Generating and seeding synthetic attendance dataset...")
    summary = generate_and_seed_database()
    print("Seeding complete! Summary:", summary)
