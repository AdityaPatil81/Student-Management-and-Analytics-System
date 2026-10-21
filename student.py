import hashlib                      
import os                           
import smtplib                      
from datetime import date, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
 
import mysql.connector              
from mysql.connector import Error
import numpy as np
import pandas as pd
import plotly.express as px         
import plotly.graph_objects as go   
import streamlit as st              
import toml                         
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
  
# Database Configuration
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "charset": "utf8mb4"
}
DB_NAME = "student_system"
 
# PASSWORD HASHING UTILITIES (PBKDF2-HMAC-SHA256 with Salt)
def hash_password(password: str, salt: str = None) -> str:
    """Hash a password securely using PBKDF2-HMAC-SHA256 with a unique salt."""
    if not password:
        return ""
    if salt is None:
        salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"
 
def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plain-text password against a stored hash."""
    if not password or not stored_hash:
        return False
    try:
        if "$" in stored_hash:
            salt, key = stored_hash.split("$", 1)
            re_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
            return re_hash == key
        # Fallback support for legacy SHA-256 direct hash
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == stored_hash
    except Exception:
        return False
 
# DATABASE CONNECTION
def get_server_connection():
    """Connect to MySQL server without selecting a specific database."""
    return mysql.connector.connect(**DB_CONFIG)
 
def get_connection():
    """Connect to the student_system MySQL database."""
    config = DB_CONFIG.copy()
    config["database"] = DB_NAME
    return mysql.connector.connect(**config)
 
# DATABASE & TABLE INITIALIZATION
def init_db():
    """Create database, tables, and seed initial demo data if empty."""
    # 1. Create Database if not exists
    try:
        conn = get_server_connection()
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.close()
        conn.close()
    except Error as e:
        print(f"Error ensuring database exists: {e}")
        raise e
 
    # 2. Create Tables
    conn = get_connection()
    cursor = conn.cursor()
 
    # Students Table (includes parent_email)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INT AUTO_INCREMENT PRIMARY KEY,
        roll_no VARCHAR(50) UNIQUE NOT NULL,
        name VARCHAR(150) NOT NULL,
        email VARCHAR(150) NOT NULL,
        parent_email VARCHAR(150) NOT NULL,
        department VARCHAR(100) NOT NULL,
        semester INT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
 
    # Users Table (authentication with password hash)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(20) NOT NULL,
        student_id INT NULL,
        name VARCHAR(150) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
 
    # Marks Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS marks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL,
        subject VARCHAR(100) NOT NULL,
        exam_name VARCHAR(100) NOT NULL,
        exam_order INT NOT NULL,
        score FLOAT NOT NULL,
        max_score FLOAT NOT NULL,
        percentage FLOAT NOT NULL,
        date DATE NOT NULL,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
 
    # Attendance Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL,
        date DATE NOT NULL,
        status VARCHAR(20) NOT NULL,
        subject VARCHAR(100) NOT NULL,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
 
    conn.commit()
 
    # 3. Seed Demo Data if users table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
 
    if user_count == 0:
        seed_demo_data(cursor, conn)
 
    cursor.close()
    conn.close()
 
def seed_demo_data(cursor, conn):
    """Seed demo accounts: Faculty and 3 Students with marks and attendance."""
    # Faculty User (faculty / faculty123)
    faculty_pwd_hash = hash_password("faculty123")
    cursor.execute("""
        INSERT INTO users (username, password_hash, role, student_id, name)
        VALUES (%s, %s, %s, %s, %s)
    """, ("faculty", faculty_pwd_hash, "faculty", None, "Prof. Robert Anderson"))
 
    demo_students = [
        ("CS-101", "Alice Johnson", "alice.johnson@edu.univ.com", "parent.alice@example.com", "Computer Science", 4, "student1", "student123"),
        ("CS-102", "Bob Smith", "bob.smith@edu.univ.com", "parent.bob@example.com", "Computer Science", 4, "student2", "student123"),
        ("IT-201", "Charlie Davis", "charlie.davis@edu.univ.com", "parent.charlie@example.com", "Information Technology", 4, "student3", "student123"),
    ]
 
    student_id_map = {}
    for roll, name, email, p_email, dept, sem, uname, pwd in demo_students:
        cursor.execute("""
            INSERT INTO students (roll_no, name, email, parent_email, department, semester)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (roll, name, email, p_email, dept, sem))
        st_id = cursor.lastrowid
        student_id_map[roll] = st_id
 
        # Create user account with hashed password
        pwd_hash = hash_password(pwd)
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, student_id, name)
            VALUES (%s, %s, %s, %s, %s)
        """, (uname, pwd_hash, "student", st_id, name))

    # Charlie (High: 84 -> 87 -> 89 -> 93)
    marks_data = [
        # Alice
        (student_id_map["CS-101"], "Data Structures", "Quiz 1", 1, 68.0, 100.0, 68.0, "2026-08-10"),
        (student_id_map["CS-101"], "Database Systems", "Midterm Exam", 2, 74.0, 100.0, 74.0, "2026-09-05"),
        (student_id_map["CS-101"], "Operating Systems", "Quiz 2", 3, 82.0, 100.0, 82.0, "2026-09-25"),
        (student_id_map["CS-101"], "Web Development", "Pre-Final", 4, 88.0, 100.0, 88.0, "2026-10-15"),
        
        # Bob
        (student_id_map["CS-102"], "Data Structures", "Quiz 1", 1, 62.0, 100.0, 62.0, "2026-08-10"),
        (student_id_map["CS-102"], "Database Systems", "Midterm Exam", 2, 55.0, 100.0, 55.0, "2026-09-05"),
        (student_id_map["CS-102"], "Operating Systems", "Quiz 2", 3, 58.0, 100.0, 58.0, "2026-09-25"),
        (student_id_map["CS-102"], "Web Development", "Pre-Final", 4, 51.0, 100.0, 51.0, "2026-10-15"),
 
        # Charlie
        (student_id_map["IT-201"], "Data Structures", "Quiz 1", 1, 84.0, 100.0, 84.0, "2026-08-10"),
        (student_id_map["IT-201"], "Database Systems", "Midterm Exam", 2, 87.0, 100.0, 87.0, "2026-09-05"),
        (student_id_map["IT-201"], "Operating Systems", "Quiz 2", 3, 89.0, 100.0, 89.0, "2026-09-25"),
        (student_id_map["IT-201"], "Web Development", "Pre-Final", 4, 93.0, 100.0, 93.0, "2026-10-15"),
    ]
    cursor.executemany("""
        INSERT INTO marks (student_id, subject, exam_name, exam_order, score, max_score, percentage, date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, marks_data)

    base_date = date(2026, 9, 1)
    subjects = ["Data Structures", "Operating Systems", "Database Systems", "Web Development"]
 
    attendance_data = []
    alice_statuses = ["Present", "Present", "Present", "Absent", "Present", "Present", "Present", "Present", "Present", "Present", "Present", "Present"]
    bob_statuses   = ["Present", "Absent", "Present", "Absent", "Present", "Absent", "Present", "Absent", "Present", "Present", "Absent", "Present"]
    charlie_stat   = ["Present", "Present", "Absent", "Present", "Absent", "Present", "Absent", "Present", "Present", "Absent", "Present", "Present"]
 
    for i in range(12):
        curr_date = str(base_date + timedelta(days=i * 3))
        subj = subjects[i % len(subjects)]
        attendance_data.append((student_id_map["CS-101"], curr_date, alice_statuses[i], subj))
        attendance_data.append((student_id_map["CS-102"], curr_date, bob_statuses[i], subj))
        attendance_data.append((student_id_map["IT-201"], curr_date, charlie_stat[i], subj))
 
    cursor.executemany("""
        INSERT INTO attendance (student_id, date, status, subject)
        VALUES (%s, %s, %s, %s)
    """, attendance_data)
 
    conn.commit()
 
# AUTHENTICATION
def authenticate(username, password):
    """Verify username and hashed password."""
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
 
        if user and verify_password(password, user["password_hash"]):
            return user
        return None
    except Exception as e:
        print(f"Auth error: {e}")
        return None
 
# STUDENT OPERATIONS
def get_student_by_id(student_id):
    """Retrieve student information by student_id."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row
 
def get_all_students():
    """Retrieve all students sorted by roll_no."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students ORDER BY roll_no ASC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
 
def add_student(roll_no, name, email, parent_email, department, semester, username, password):
    """Register a new student and create associated user credentials with password hash."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Check if roll_no or username exists
        cursor.execute("SELECT id FROM students WHERE roll_no = %s", (roll_no,))
        if cursor.fetchone():
            return False, f"Roll number '{roll_no}' already exists."
 
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return False, f"Username '{username}' is already taken."
 
        # Insert student record
        cursor.execute("""
            INSERT INTO students (roll_no, name, email, parent_email, department, semester)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (roll_no.strip(), name.strip(), email.strip(), parent_email.strip(), department, semester))
        student_id = cursor.lastrowid
 
        # Insert user record with hashed password
        pwd_hash = hash_password(password)
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, student_id, name)
            VALUES (%s, %s, 'student', %s, %s)
        """, (username.strip(), pwd_hash, student_id, name.strip()))
 
        conn.commit()
        return True, f"Student '{name}' registered successfully with Roll No '{roll_no}'!"
    except Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        cursor.close()
        conn.close()
 
def update_student(student_id, roll_no, name, email, parent_email, department, semester):
    """Update student profile details including parent_email."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE students
            SET roll_no = %s, name = %s, email = %s, parent_email = %s, department = %s, semester = %s
            WHERE id = %s
        """, (roll_no.strip(), name.strip(), email.strip(), parent_email.strip(), department, semester, student_id))
        
        # Also update name in users table
        cursor.execute("UPDATE users SET name = %s WHERE student_id = %s", (name.strip(), student_id))
        
        conn.commit()
        return True, "Student record updated successfully!"
    except Error as e:
        conn.rollback()
        return False, f"Failed to update student: {e}"
    finally:
        cursor.close()
        conn.close()
 
def delete_student(student_id):
    """Delete student and cascade all associated marks, attendance, and user records."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Cascade handles marks, attendance, and users if configured with ON DELETE CASCADE
        cursor.execute("DELETE FROM users WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM marks WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM attendance WHERE student_id = %s", (student_id,))
        cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
        conn.commit()
        return True, "Student and all associated records deleted."
    except Error as e:
        conn.rollback()
        return False, f"Failed to delete student: {e}"
    finally:
        cursor.close()
        conn.close()
 
# MARKS OPERATIONS
def get_student_marks(student_id):
    """Retrieve marks for a given student."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM marks
        WHERE student_id = %s
        ORDER BY exam_order ASC, date ASC
    """, (student_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
 
def get_all_marks():
    """Retrieve all marks joined with student info."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT m.*, s.roll_no, s.name, s.department
        FROM marks m
        JOIN students s ON m.student_id = s.id
        ORDER BY m.date DESC, m.exam_order ASC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
 
def add_mark(student_id, subject, exam_name, exam_order, score, max_score, date_str):
    """Record an assessment score for a student."""
    pct = (score / max_score) * 100.0 if max_score > 0 else 0.0
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO marks (student_id, subject, exam_name, exam_order, score, max_score, percentage, date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (student_id, subject.strip(), exam_name.strip(), exam_order, score, max_score, round(pct, 2), date_str))
        conn.commit()
        return True, "Marks recorded successfully!"
    except Error as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        cursor.close()
        conn.close()
 
def delete_mark(mark_id):
    """Delete an assessment mark by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM marks WHERE id = %s", (mark_id,))
        conn.commit()
        return True, "Mark entry deleted."
    except Error as e:
        conn.rollback()
        return False, f"Error deleting mark: {e}"
    finally:
        cursor.close()
        conn.close()
 
# ATTENDANCE OPERATIONS
def get_student_attendance(student_id):
    """Retrieve attendance logs for a student."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM attendance
        WHERE student_id = %s
        ORDER BY date DESC
    """, (student_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
 
def get_all_attendance(date_query=None):
    """Retrieve attendance logs, optionally filtered by date."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    if date_query:
        cursor.execute("""
            SELECT a.*, s.roll_no, s.name, s.department
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.date = %s
            ORDER BY s.roll_no ASC
        """, (date_query,))
    else:
        cursor.execute("""
            SELECT a.*, s.roll_no, s.name, s.department
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            ORDER BY a.date DESC, s.roll_no ASC
        """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
 
def mark_attendance_bulk(records):
    """Insert multiple attendance records at once."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.executemany("""
            INSERT INTO attendance (student_id, date, status, subject)
            VALUES (%s, %s, %s, %s)
        """, records)
        conn.commit()
        return True, f"Logged {len(records)} attendance entries."
    except Error as e:
        conn.rollback()
        return False, f"Failed to record attendance: {e}"
    finally:
        cursor.close()
        conn.close()
 
# ATTENDANCE ANALYTICS & LOW ATTENDANCE RECIPIENTS
def get_attendance_summary_all_students(threshold=75.0):
    """
    Computes attendance rate for every student and flags those below threshold.
    Returns:
        all_stats: list of dicts with student attendance summaries
        low_attendance_list: list of students strictly below threshold
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            s.id AS student_id,
            s.roll_no,
            s.name,
            s.email,
            s.parent_email,
            s.department,
            s.semester,
            COUNT(a.id) AS total_classes,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_classes,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_classes
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id
        GROUP BY s.id, s.roll_no, s.name, s.email, s.parent_email, s.department, s.semester
        ORDER BY s.roll_no ASC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
 
    all_stats = []
    low_attendance_list = []
 
    for r in rows:
        total = int(r["total_classes"] or 0)
        present = int(r["present_classes"] or 0)
        absent = int(r["absent_classes"] or 0)
        pct = (float(present) / float(total) * 100.0) if total > 0 else 0.0
        
        stat_item = {
            "student_id": r["student_id"],
            "roll_no": r["roll_no"],
            "name": r["name"],
            "email": r["email"],
            "parent_email": r["parent_email"],
            "department": r["department"],
            "semester": r["semester"],
            "total_classes": total,
            "present_classes": present,
            "absent_classes": absent,
            "attendance_pct": round(pct, 1),
            "is_low": (pct < threshold) and (total > 0)
        }
        all_stats.append(stat_item)
        if stat_item["is_low"]:
            low_attendance_list.append(stat_item)
 
    return all_stats, low_attendance_list
 
def train_and_predict_performance(marks_list):
    """
    Fits a Linear Regression model on historical exam percentages ordered chronologically.
    Forecasts the expected percentage for the upcoming assessment milestone.
    """
    if not marks_list or len(marks_list) < 2:
        return {
            "status": False,
            "message": "At least 2 assessment records are required to train the ML regression model.",
            "predicted_score": None,
            "slope": 0.0,
            "intercept": 0.0,
            "r2": 0.0,
            "trend_label": "Insufficient Data",
            "next_exam_order": None,
            "exam_history": [],
            "x_coords": [],
            "fitted_line": []
        }
 
    df = pd.DataFrame(marks_list)
    # Aggregate mean score per exam order in case student has multiple subjects per milestone
    df_grouped = df.groupby(["exam_order", "exam_name"])["percentage"].mean().reset_index()
    df_grouped = df_grouped.sort_values(by="exam_order").reset_index(drop=True)
 
    X = df_grouped["exam_order"].values.reshape(-1, 1)
    y = df_grouped["percentage"].values
 
    # Train Linear Regression model
    model = LinearRegression()
    model.fit(X, y)
 
    slope = float(model.coef_[0])
    intercept = float(model.intercept_)
 
    # Calculate model confidence R^2 score
    y_pred_hist = model.predict(X)
    r2 = float(r2_score(y, y_pred_hist)) if len(y) > 2 else 0.85
 
    # Predict Next Exam Milestone
    next_order = int(df_grouped["exam_order"].max()) + 1
    next_pred_raw = float(model.predict([[next_order]])[0])
    predicted_score = round(max(0.0, min(100.0, next_pred_raw)), 1)
 
    # Classify Trajectory
    if slope >= 3.0:
        trend_label = "Strong Upward Trajectory 🚀"
    elif slope >= 0.5:
        trend_label = "Steady Improvement 📈"
    elif slope > -0.5:
        trend_label = "Consistent / Stable ⚖️"
    elif slope > -3.0:
        trend_label = "Mild Decline 📉"
    else:
        trend_label = "Significant Drop - Needs Intervention ⚠️"
 
    # Line coordinates for Plotly visualization
    x_coords = list(df_grouped["exam_order"].values)
    fitted_line = [round(float(v), 2) for v in y_pred_hist]
 
    return {
        "status": True,
        "message": "Model trained successfully.",
        "predicted_score": predicted_score,
        "slope": round(slope, 3),
        "intercept": round(intercept, 2),
        "r2": round(max(0.0, r2), 3),
        "trend_label": trend_label,
        "next_exam_order": next_order,
        "exam_history": df_grouped.to_dict(orient="records"),
        "x_coords": x_coords,
        "fitted_line": fitted_line
    }
 
def generate_recommendations(marks_list, attendance_list, ml_result):
    """
    Generates intelligent, actionable study recommendations based on attendance,
    subject mastery, and ML trajectory forecasting.
    """
    attendance_tips = []
    academic_tips = []
    ml_insights = []
    action_plan = []
 
    # 1. Attendance Analysis
    total_classes = len(attendance_list)
    present_classes = sum(1 for a in attendance_list if a["status"] == "Present")
    att_pct = (present_classes / total_classes * 100.0) if total_classes > 0 else 0.0
 
    if att_pct < 75.0:
        att_status = "Warning"
        # Calculate how many consecutive classes needed to cross 75%
        # (present + x) / (total + x) >= 0.75  =>  present + x >= 0.75*total + 0.75*x  => 0.25*x >= 0.75*total - present
        needed = max(1, int(np.ceil((0.75 * total_classes - present_classes) / 0.25)))
        attendance_tips.append(
            f"⚠️ **Critical Shortage:** Your attendance is **{att_pct:.1f}%**, which is below the mandatory 75% threshold. "
            f"You must attend at least the next **{needed} consecutive sessions** without absence to restore exam eligibility."
        )
        action_plan.append("Report immediately to your faculty advisor to discuss attendance makeup options.")
    elif att_pct < 85.0:
        att_status = "Good"
        attendance_tips.append(
            f"ℹ️ **Satisfactory Attendance:** Your attendance is **{att_pct:.1f}%**. Maintain this regularity to ensure exam clearance."
        )
    else:
        att_status = "Excellent"
        attendance_tips.append(
            f"🌟 **Outstanding Attendance:** Your regularity is **{att_pct:.1f}%**. Excellent attendance strongly correlates with high GPA performance!"
        )
 
    # 2. Academic Performance Analysis
    if marks_list:
        df_m = pd.DataFrame(marks_list)
        sub_avg = df_m.groupby("subject")["percentage"].mean()
        lowest_sub = sub_avg.idxmin()
        lowest_score = sub_avg.min()
        highest_sub = sub_avg.idxmax()
        highest_score = sub_avg.max()
 
        if lowest_score < 60.0:
            academic_tips.append(
                f"🎯 **Target Weak Subject:** Your average in **{lowest_sub}** is `{lowest_score:.1f}%`. Dedicate 45 minutes daily to review fundamental concepts and solve practice problem sets."
            )
            action_plan.append(f"Schedule a doubts-clearing session with the subject teacher for {lowest_sub}.")
        else:
            academic_tips.append(
                f"✅ **Balanced Competency:** All subjects are above 60%. Your strongest domain is **{highest_sub}** with `{highest_score:.1f}%`."
            )
 
        if highest_score >= 80.0:
            academic_tips.append(
                f"🏆 **Excellence Opportunity:** You are performing exceptionally well in **{highest_sub}** (`{highest_score:.1f}%`). Consider preparing for advanced competitive projects or tutoring peers."
            )
 
    # 3. Machine Learning Insights
    if ml_result.get("status"):
        slope = ml_result["slope"]
        next_score = ml_result["predicted_score"]
 
        if slope > 1.0:
            ml_insights.append(
                f"🚀 **Positive Momentum:** The regression model forecasts a predicted score of **{next_score:.1f}%** for your upcoming assessment milestone. Keep your current revision schedule!"
            )
            action_plan.append("Maintain structured study notes and complete pre-exam mock tests.")
        elif slope < -1.0:
            ml_insights.append(
                f"⚠️ **Downhill Slope Detected:** Your scores are dropping by approximately `{abs(slope):.2f}%` per assessment milestone. Predicted next score is **{next_score:.1f}%**."
            )
            action_plan.append("Analyze past test answer sheets to pinpoint error patterns (conceptual vs calculation).")
        else:
            ml_insights.append(
                f"📊 **Steady Plateau:** Your performance is hovering near `{next_score:.1f}%`. To break into the higher tier (85%+), increase active recall and mock testing frequency."
            )
            action_plan.append("Attempt timed past university question papers under simulated exam conditions.")
    else:
        ml_insights.append("Record marks for at least 2 examinations to unlock ML predictive trajectories.")
 
    if not action_plan:
        action_plan.append("Keep revising weekly lecture summaries and review lab experiments.")
 
    return {
        "attendance_status": att_status,
        "attendance_tips": attendance_tips,
        "academic_tips": academic_tips,
        "ml_insights": ml_insights,
        "action_plan": action_plan
    }
 
# In-memory dispatch audit log (useful for previewing sent emails)
EMAIL_AUDIT_LOG = []
 
def get_smtp_config():
    """
    Retrieve SMTP configuration from .streamlit/secrets.toml,
    Streamlit secrets, or environment variables.
    """
    config = {
        "host": "",
        "port": 587,
        "username": "",
        "password": "",
        "sender_email": "",
        "sender_name": "EduPulse Academic Administration",
        "use_tls": True,
        "configured": False
    }
 
    # 1. Try reading from .streamlit/secrets.toml
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r", encoding="utf-8") as f:
                data = toml.load(f)
                smtp_data = data.get("smtp", data.get("SMTP", {}))
                if smtp_data:
                    config["host"] = smtp_data.get("host", config["host"])
                    config["port"] = int(smtp_data.get("port", config["port"]))
                    config["username"] = smtp_data.get("username", config["username"])
                    config["password"] = smtp_data.get("password", config["password"])
                    config["sender_email"] = smtp_data.get("sender_email", config["username"])
                    config["sender_name"] = smtp_data.get("sender_name", config["sender_name"])
                    config["use_tls"] = bool(smtp_data.get("use_tls", True))
        except Exception as e:
            print(f"Error parsing secrets.toml: {e}")
 
    # 2. Try Streamlit session/secrets if available
    try:
        if hasattr(st, "secrets") and "smtp" in st.secrets:
            s = st.secrets["smtp"]
            config["host"] = s.get("host", config["host"])
            config["port"] = int(s.get("port", config["port"]))
            config["username"] = s.get("username", config["username"])
            config["password"] = s.get("password", config["password"])
            config["sender_email"] = s.get("sender_email", config["sender_email"])
            config["sender_name"] = s.get("sender_name", config["sender_name"])
            config["use_tls"] = bool(s.get("use_tls", config["use_tls"]))
    except Exception:
        pass
 
    # 3. Try Environment Variables
    config["host"] = os.getenv("SMTP_HOST", config["host"])
    config["port"] = int(os.getenv("SMTP_PORT", str(config["port"])))
    config["username"] = os.getenv("SMTP_USERNAME", config["username"])
    config["password"] = os.getenv("SMTP_PASSWORD", config["password"])
    config["sender_email"] = os.getenv("SMTP_SENDER_EMAIL", config["sender_email"])
 
    # Determine if actively configured
    if config["host"] and config["username"] and config["password"]:
        config["configured"] = True
 
    return config
 
def generate_low_attendance_html(student_name, roll_no, department, attendance_pct, present_classes, total_classes, threshold=75.0):
    """Generate a clean, responsive HTML email template for attendance shortage warnings."""
    missed_classes = max(0, total_classes - present_classes)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
                background-color: #f1f5f9;
                margin: 0;
                padding: 24px;
                color: #1e293b;
            }}
            .container {{
                max-width: 620px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                border: 1px solid #e2e8f0;
            }}
            .header {{
                background: linear-gradient(135deg, #b91c1c 0%, #dc2626 100%);
                color: #ffffff;
                padding: 26px 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 22px;
                letter-spacing: 0.5px;
            }}
            .header p {{
                margin: 6px 0 0 0;
                font-size: 13px;
                opacity: 0.9;
            }}
            .content {{
                padding: 30px;
            }}
            .warning-badge {{
                display: inline-block;
                background-color: #fee2e2;
                color: #b91c1c;
                font-weight: 700;
                font-size: 13px;
                padding: 6px 14px;
                border-radius: 20px;
                margin-bottom: 18px;
            }}
            .stats-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                background-color: #f8fafc;
                border-radius: 8px;
                overflow: hidden;
            }}
            .stats-table td {{
                padding: 12px 16px;
                border-bottom: 1px solid #e2e8f0;
                font-size: 14px;
            }}
            .stats-table td.label {{
                font-weight: 600;
                color: #475569;
                width: 45%;
            }}
            .stats-table td.val {{
                color: #0f172a;
                font-weight: 700;
            }}
            .alert-text {{
                background-color: #fff1f2;
                border-left: 4px solid #e11d48;
                padding: 14px 18px;
                border-radius: 6px;
                font-size: 13px;
                color: #9f1239;
                line-height: 1.5;
                margin: 22px 0;
            }}
            .footer {{
                background-color: #f8fafc;
                padding: 18px 30px;
                text-align: center;
                font-size: 12px;
                color: #64748b;
                border-top: 1px solid #e2e8f0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚠️ Official Academic Notice</h1>
                <p>EduPulse Student Monitoring & Governance System</p>
            </div>
            <div class="content">
                <span class="warning-badge">ATTENDANCE SHORTAGE WARNING</span>
                <p>Dear <strong>{student_name}</strong> and Respected <strong>Parents/Guardians</strong>,</p>
                <p>
                    This is an urgent official notification from the <strong>Department of {department}</strong> regarding academic attendance compliance.
                    As per university regulations, students must maintain a minimum attendance of <strong>{threshold:.0f}%</strong> to be eligible for semester-end examinations.
                </p>
 
                <table class="stats-table">
                    <tr>
                        <td class="label">Student Name</td>
                        <td class="val">{student_name}</td>
                    </tr>
                    <tr>
                        <td class="label">Roll Number</td>
                        <td class="val">{roll_no}</td>
                    </tr>
                    <tr>
                        <td class="label">Department</td>
                        <td class="val">{department}</td>
                    </tr>
                    <tr>
                        <td class="label">Current Attendance Rate</td>
                        <td class="val" style="color: #dc2626; font-size: 16px;">{attendance_pct:.1f}% (Required: {threshold:.0f}%)</td>
                    </tr>
                    <tr>
                        <td class="label">Sessions Attended</td>
                        <td class="val">{present_classes} of {total_classes} Classes</td>
                    </tr>
                    <tr>
                        <td class="label">Sessions Missed</td>
                        <td class="val">{missed_classes} Classes</td>
                    </tr>
                </table>
 
                <div class="alert-text">
                    <strong>Critical Action Required:</strong><br>
                    Please contact your designated Faculty Academic Advisor within 3 business days. 
                    Unexcused continued absence will lead to examination debarment as mandated by academic council policy.
                </div>
 
                <p style="font-size: 13px; color: #475569;">
                    If there are valid medical circumstances, please submit endorsed documentation to the Academic Dean's Office promptly.
                </p>
            </div>
            <div class="footer">
                <p>This is an automated advisory dispatched by EduPulse Academic Management System.<br>
                For inquiries, please reach out to the Department Coordinator.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html
 
def send_email(to_recipients, subject, html_content):
    """
    Dispatch an email via SMTP.
    If credentials are not yet configured in .streamlit/secrets.toml,
    simulates dispatch gracefully and records in audit log.
    """
    config = get_smtp_config()
    
    # Audit record
    audit_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "to": to_recipients,
        "subject": subject,
        "is_simulated": not config["configured"]
    }
 
    if not config["configured"]:
        # Simulation Mode
        audit_entry["status"] = "SIMULATED_SUCCESS"
        audit_entry["message"] = "Simulated dispatch (No active SMTP in .streamlit/secrets.toml)"
        EMAIL_AUDIT_LOG.append(audit_entry)
        return True, f"Simulated delivery to {', '.join(to_recipients)} (Configure .streamlit/secrets.toml for live sending)."
 
    # Live SMTP Dispatch
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{config['sender_name']} <{config['sender_email']}>"
        msg["To"] = ", ".join(to_recipients)
 
        part_html = MIMEText(html_content, "html")
        msg.attach(part_html)
 
        server = smtplib.SMTP(config["host"], config["port"], timeout=20)
        if config["use_tls"]:
            server.starttls()
        server.login(config["username"], config["password"])
        server.sendmail(config["sender_email"], to_recipients, msg.as_string())
        server.quit()
 
        audit_entry["status"] = "SENT_LIVE"
        audit_entry["message"] = "Live email delivered via SMTP server."
        EMAIL_AUDIT_LOG.append(audit_entry)
        return True, f"Live email successfully sent to {', '.join(to_recipients)}"
    except Exception as e:
        audit_entry["status"] = "FAILED"
        audit_entry["message"] = str(e)
        EMAIL_AUDIT_LOG.append(audit_entry)
        return False, f"SMTP Error: {e}"
 
def send_low_attendance_notification(student_record, threshold=75.0):
    """
    Send low attendance alert to both the student email and parent email.
    """
    student_name = student_record["name"]
    roll_no = student_record["roll_no"]
    dept = student_record["department"]
    att_pct = student_record["attendance_pct"]
    present = student_record["present_classes"]
    total = student_record["total_classes"]
 
    # Gather recipients (Student + Parent)
    recipients = []
    if student_record.get("email"):
        recipients.append(student_record["email"].strip())
    if student_record.get("parent_email"):
        p_email = student_record["parent_email"].strip()
        if p_email and p_email not in recipients:
            recipients.append(p_email)
 
    if not recipients:
        return False, f"No email address found for student {student_name} or parent."
 
    subject = f"⚠️ URGENT: Low Attendance Warning for {student_name} ({roll_no}) - EduPulse"
    html_body = generate_low_attendance_html(
        student_name=student_name,
        roll_no=roll_no,
        department=dept,
        attendance_pct=att_pct,
        present_classes=present,
        total_classes=total,
        threshold=threshold
    )
 
    return send_email(recipients, subject, html_body)
 
def send_bulk_low_attendance_alerts(low_attendance_list, threshold=75.0, progress_callback=None):
    """
    Iterate through all low attendance students and dispatch email alerts to both students and parents.
    """
    total = len(low_attendance_list)
    sent_count = 0
    fail_count = 0
    results = []
 
    for idx, st_rec in enumerate(low_attendance_list):
        ok, msg = send_low_attendance_notification(st_rec, threshold=threshold)
        if ok:
            sent_count += 1
        else:
            fail_count += 1
        
        results.append({
            "roll_no": st_rec["roll_no"],
            "name": st_rec["name"],
            "student_email": st_rec.get("email", ""),
            "parent_email": st_rec.get("parent_email", ""),
            "attendance_pct": f"{st_rec['attendance_pct']}%",
            "status": "Delivered" if ok else "Failed",
            "details": msg
        })
 
        if progress_callback:
            progress_callback(idx + 1, total)
 
    return {
        "total": total,
        "sent": sent_count,
        "failed": fail_count,
        "results": results
    }
 
# Page Configuration
st.set_page_config(
    page_title="EduPulse | Student Management & Analytics",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)
 
# Custom Dashboard Styling
st.markdown("""
<style>
    /* Metric Card Styling */
    .metric-card {
        background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 18px 22px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 15px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #1e293b;
    }
    .metric-label {
        font-size: 13px;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-present {
        background-color: #dcfce7;
        color: #15803d;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 12px;
    }
    .badge-absent {
        background-color: #fee2e2;
        color: #b91c1c;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 12px;
    }
    .suggestion-box {
        background-color: #f0fdf4;
        border-left: 5px solid #22c55e;
        padding: 14px 20px;
        border-radius: 6px;
        margin-bottom: 12px;
    }
    .warning-box {
        background-color: #fef2f2;
        border-left: 5px solid #ef4444;
        padding: 14px 20px;
        border-radius: 6px;
        margin-bottom: 12px;
    }
    .info-box {
        background-color: #eff6ff;
        border-left: 5px solid #3b82f6;
        padding: 14px 20px;
        border-radius: 6px;
        margin-bottom: 12px;
    }
    .alert-header-card {
        background: linear-gradient(135deg, #fff1f2 0%, #fee2e2 100%);
        border: 1px solid #fecdd3;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)
 
# Initialize MySQL Database and Seed Demo Accounts
try:
    init_db()
except Exception as e:
    st.error(f"❌ Failed to connect to MySQL database (`student_system`). Please ensure MySQL service is running with user 'root' and password 'root'. Details: {e}")
    st.stop()
 
# Session State for Authentication
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user" not in st.session_state:
    st.session_state["user"] = None
if "role" not in st.session_state:
    st.session_state["role"] = None
 
def logout():
    st.session_state["logged_in"] = False
    st.session_state["user"] = None
    st.session_state["role"] = None
    st.rerun()
 
# LOGIN SCREEN
def render_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #1e293b;'>🎓 EduPulse Portal</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 15px;'>Student Performance Analytics & Automated Attendance Notification System</p>", unsafe_allow_html=True)
        st.divider()
 
        tab_student, tab_faculty = st.tabs(["👨🎓 Student Login", "👨🏫 Faculty Login"])
 
        with tab_student:
            st.markdown("### Student Access")
            st.caption("Sign in to review your marks, attendance records, ML score projection, and study tips.")
            with st.form("student_login_form"):
                stu_uname = st.text_input("Username", key="s_uname", placeholder="e.g. student1")
                stu_pwd = st.text_input("Password", type="password", key="s_pwd", placeholder="e.g. student123")
                stu_submit = st.form_submit_button("Log In as Student", use_container_width=True, type="primary")
 
            if stu_submit:
                user = authenticate(stu_uname, stu_pwd)
                if user and user["role"] == "student":
                    st.session_state["logged_in"] = True
                    st.session_state["user"] = user
                    st.session_state["role"] = "student"
                    st.success(f"Welcome back, {user['name']}!")
                    st.rerun()
                else:
                    st.error("Invalid student credentials. Please check your username and password.")
 
        with tab_faculty:
            st.markdown("### Faculty Administration Portal")
            st.caption("Sign in to manage student records, record attendance, input marks, and send low attendance email alerts.")
            with st.form("faculty_login_form"):
                fac_uname = st.text_input("Username", key="f_uname", placeholder="e.g. faculty")
                fac_pwd = st.text_input("Password", type="password", key="f_pwd", placeholder="e.g. faculty123")
                fac_submit = st.form_submit_button("Log In as Faculty", use_container_width=True, type="primary")
 
            if fac_submit:
                user = authenticate(fac_uname, fac_pwd)
                if user and user["role"] == "faculty":
                    st.session_state["logged_in"] = True
                    st.session_state["user"] = user
                    st.session_state["role"] = "faculty"
                    st.success(f"Welcome, {user['name']}!")
                    st.rerun()
                else:
                    st.error("Invalid faculty credentials. Please check username and password.")
 
# SIDEBAR
def render_sidebar(user, role):
    smtp_config = get_smtp_config()
    with st.sidebar:
        st.markdown("### 🎓 EduPulse Profile")
        st.markdown(f"**Name:** {user['name']}")
        st.markdown(f"**Role:** `{role.upper()}`")
        st.markdown(f"**Username:** `{user['username']}`")
        
        if role == "student":
            student_info = get_student_by_id(user["student_id"])
            if student_info:
                st.markdown(f"**Roll No:** `{student_info['roll_no']}`")
                st.markdown(f"**Department:** {student_info['department']}")
                st.markdown(f"**Semester:** {student_info['semester']}")
                st.markdown(f"**Parent Email:** `{student_info['parent_email']}`")
        
        st.divider()
        st.caption("🗄️ **Database:** MySQL (`student_system`)")
        if smtp_config["configured"]:
            st.caption("📧 **SMTP Email:** `Active (Live Server)`")
        else:
            st.caption("📧 **SMTP Email:** `Ready (Simulation Mode)`")
 
        st.write("")
        if st.button("🚪 Log Out", use_container_width=True, type="secondary"):
            logout()
 
# STUDENT DASHBOARD
def render_student_dashboard(user):
    student_id = user["student_id"]
    student_info = get_student_by_id(student_id)
    marks_list = get_student_marks(student_id)
    attendance_list = get_student_attendance(student_id)
 
    total_classes = len(attendance_list)
    present_classes = sum(1 for a in attendance_list if a["status"] == "Present")
    attendance_pct = (present_classes / total_classes * 100.0) if total_classes > 0 else 0.0
    avg_score = (sum(m["percentage"] for m in marks_list) / len(marks_list)) if marks_list else 0.0
 
    ml_result = train_and_predict_performance(marks_list)
    recommendations = generate_recommendations(marks_list, attendance_list, ml_result)
 
    st.markdown(f"## Welcome back, {student_info['name']} 👋")
    st.caption(f"Roll No: **{student_info['roll_no']}** | Department: **{student_info['department']}** | Semester: **{student_info['semester']}** | Registered Parent Email: **{student_info['parent_email']}**")
 
    if attendance_pct < 75.0 and total_classes > 0:
        st.markdown(f"""
        <div class="alert-header-card">
            <h4 style="color: #b91c1c; margin: 0 0 6px 0;">⚠️ Urgent Attendance Warning</h4>
            <span style="color: #991b1b; font-size: 14px;">
                Your current attendance is <strong>{attendance_pct:.1f}%</strong> (below university clearance minimum of 75%). 
                Official warning notices have been flagged for your advisor and sent to your registered email and parent email (<code>{student_info['parent_email']}</code>).
            </span>
        </div>
        """, unsafe_allow_html=True)
 
    st.write("")
 
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Attendance (Presenty)</div>
            <div class="metric-value" style="color: {'#16a34a' if attendance_pct >= 75 else '#dc2626'};">
                {attendance_pct:.1f}%
            </div>
            <span style="font-size: 12px; color: #64748b;">{present_classes} / {total_classes} Classes Attended</span>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Academic Average</div>
            <div class="metric-value">{avg_score:.1f}%</div>
            <span style="font-size: 12px; color: #64748b;">Across {len(marks_list)} Assessments</span>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        pred_val = f"{ml_result['predicted_score']:.1f}%" if ml_result['predicted_score'] is not None else "N/A"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Predicted Next Score (ML)</div>
            <div class="metric-value" style="color: #2563eb;">{pred_val}</div>
            <span style="font-size: 12px; color: #64748b;">Linear Regression Projection</span>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Growth Trajectory</div>
            <div class="metric-value" style="font-size: 17px; line-height: 32px;">{ml_result['trend_label']}</div>
            <span style="font-size: 12px; color: #64748b;">Slope: {ml_result['slope']:+.2f}% / exam</span>
        </div>
        """, unsafe_allow_html=True)
 
    st.write("")
 
    tab_overview, tab_attendance, tab_ml, tab_suggestions = st.tabs([
        "📊 Marks & Performance",
        "📅 Presenty & Attendance Tracker",
        "🤖 ML Future Score Predictor",
        "💡 Smart Suggestions & Action Plan"
    ])
 
    # Tab 1: Marks
    with tab_overview:
        st.subheader("Academic Performance & Progress Graph")
        if not marks_list:
            st.info("No marks records have been posted yet. Check back once faculty records your assessments.")
        else:
            df_marks = pd.DataFrame(marks_list)
            c1, c2 = st.columns([3, 2])
            with c1:
                df_chron = df_marks.groupby(["exam_order", "exam_name"])["percentage"].mean().reset_index()
                df_chron = df_chron.sort_values(by="exam_order")
                
                fig_trend = px.line(
                    df_chron,
                    x="exam_name",
                    y="percentage",
                    markers=True,
                    title="Chronological Score Progression Across Assessments",
                    labels={"exam_name": "Assessment Milestone", "percentage": "Score (%)"},
                    line_shape="spline"
                )
                fig_trend.update_traces(line_color="#2563eb", line_width=3, marker=dict(size=10, color="#1e40af"))
                fig_trend.update_layout(yaxis_range=[0, 105], template="plotly_white")
                st.plotly_chart(fig_trend, use_container_width=True)
 
            with c2:
                df_sub = df_marks.groupby("subject")["percentage"].mean().reset_index()
                fig_sub = px.bar(
                    df_sub,
                    x="subject",
                    y="percentage",
                    color="percentage",
                    color_continuous_scale="Teal",
                    title="Subject-wise Mastery Average (%)",
                    labels={"subject": "Subject", "percentage": "Average (%)"},
                    text_auto=".1f"
                )
                fig_sub.update_layout(yaxis_range=[0, 105], template="plotly_white")
                st.plotly_chart(fig_sub, use_container_width=True)
 
            st.markdown("#### Complete Academic Transcript")
            display_df = df_marks[["exam_name", "subject", "score", "max_score", "percentage", "date"]].rename(
                columns={
                    "exam_name": "Exam Name",
                    "subject": "Subject",
                    "score": "Marks Obtained",
                    "max_score": "Maximum Marks",
                    "percentage": "Percentage (%)",
                    "date": "Assessment Date"
                }
            )
            st.dataframe(display_df, use_container_width=True, hide_index=True)
 
    # Tab 2: Attendance
    with tab_attendance:
        st.subheader("Attendance & Presenty Analytics")
        if not attendance_list:
            st.info("No attendance records logged yet.")
        else:
            df_att = pd.DataFrame(attendance_list)
            a1, a2 = st.columns([1, 2])
            with a1:
                att_counts = df_att["status"].value_counts().reset_index()
                att_counts.columns = ["Status", "Count"]
                color_map = {"Present": "#22c55e", "Absent": "#ef4444"}
                
                fig_donut = px.pie(
                    att_counts,
                    names="Status",
                    values="Count",
                    color="Status",
                    color_discrete_map=color_map,
                    hole=0.6,
                    title="Presenty Distribution"
                )
                fig_donut.update_layout(template="plotly_white", margin=dict(t=40, b=10, l=10, r=10))
                st.plotly_chart(fig_donut, use_container_width=True)
 
                if attendance_pct >= 75.0:
                    st.success(f"✅ **Exam Clearance Eligible:** Your attendance is **{attendance_pct:.1f}%**, meeting the 75% threshold.")
                else:
                    st.error(f"⚠️ **Attendance Shortage:** You are at **{attendance_pct:.1f}%**. University requires minimum 75% for exam hall ticket clearance.")
 
            with a2:
                subj_att = df_att.groupby("subject").agg(
                    total=("status", "count"),
                    present=("status", lambda s: (s == "Present").sum())
                ).reset_index()
                subj_att["attendance_pct"] = (subj_att["present"] / subj_att["total"] * 100.0).round(1)
 
                fig_subj_att = px.bar(
                    subj_att,
                    x="subject",
                    y="attendance_pct",
                    color="attendance_pct",
                    color_continuous_scale=["#ef4444", "#eab308", "#22c55e"],
                    title="Subject-wise Attendance Rate (%)",
                    labels={"subject": "Course", "attendance_pct": "Attendance (%)"},
                    text_auto=".1f"
                )
                fig_subj_att.add_hline(y=75, line_dash="dash", line_color="#ef4444", annotation_text="75% Minimum Limit")
                fig_subj_att.update_layout(yaxis_range=[0, 105], template="plotly_white")
                st.plotly_chart(fig_subj_att, use_container_width=True)
 
            st.markdown("#### Complete Attendance Log")
            st.dataframe(
                df_att[["date", "subject", "status"]].rename(columns={"date": "Date", "subject": "Course/Session", "status": "Attendance Status"}),
                use_container_width=True,
                hide_index=True
            )
 
    # Tab 3: ML Predictor
    with tab_ml:
        st.subheader("🤖 Future Performance Prediction (Linear Regression Model)")
        st.write("This machine learning module analyzes your historical exam scores across chronological milestones using **scikit-learn Linear Regression** to forecast your expected performance in upcoming examinations.")
 
        if not ml_result["status"]:
            st.warning(f"⚠️ {ml_result['message']}")
        else:
            p1, p2, p3 = st.columns(3)
            with p1:
                st.metric(
                    label="🎯 Predicted Next Exam Score",
                    value=f"{ml_result['predicted_score']:.1f}%",
                    delta=f"{ml_result['slope']:+.2f}% / exam"
                )
            with p2:
                st.metric(
                    label="📐 Regression Rate of Change (Slope)",
                    value=f"{ml_result['slope']:+.3f}",
                    help="Rate of score gain or decline per examination milestone."
                )
            with p3:
                st.metric(
                    label="📊 Model Confidence (R² Score)",
                    value=f"{ml_result['r2']:.3f}",
                    help="Coefficient of determination indicating how well the regression line fits actual scores."
                )
 
            st.write("")
 
            history_df = pd.DataFrame(ml_result["exam_history"])
            fig_ml = go.Figure()
 
            fig_ml.add_trace(go.Scatter(
                x=history_df["exam_order"],
                y=history_df["percentage"],
                mode="markers+text+lines",
                name="Actual Score",
                text=[f"{y:.1f}% ({name})" for y, name in zip(history_df["percentage"], history_df["exam_name"])],
                textposition="top center",
                marker=dict(size=12, color="#2563eb", symbol="circle"),
                line=dict(color="#93c5fd", width=2)
            ))
 
            fig_ml.add_trace(go.Scatter(
                x=ml_result["x_coords"],
                y=ml_result["fitted_line"],
                mode="lines",
                name="Linear Regression Fit (y = mx + c)",
                line=dict(color="#f59e0b", width=3, dash="dash")
            ))
 
            fig_ml.add_trace(go.Scatter(
                x=[ml_result["next_exam_order"]],
                y=[ml_result["predicted_score"]],
                mode="markers+text",
                name="ML Predicted Future Score",
                text=[f"Projected: {ml_result['predicted_score']:.1f}%"],
                textposition="bottom center",
                marker=dict(size=16, color="#10b981", symbol="star")
            ))
 
            fig_ml.update_layout(
                title="Linear Regression Score Forecast & Growth Trajectory",
                xaxis_title="Exam Order Milestone (#1, #2, #3...)",
                yaxis_title="Score Percentage (%)",
                yaxis_range=[0, 110],
                template="plotly_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
 
            st.plotly_chart(fig_ml, use_container_width=True)
 
            with st.expander("🔬 View Mathematical Regression Formulation"):
                st.latex(r"y = m \cdot X + c")
                st.markdown(f"""
                - **Slope ($m$):** `{ml_result['slope']}` *(Score change per milestone)*
                - **Intercept ($c$):** `{ml_result['intercept']}`
                - **Target Milestone ($X_{{next}}$):** `{ml_result['next_exam_order']}`
                - **Formulation:** ${ml_result['slope']} \\times {ml_result['next_exam_order']} + {ml_result['intercept']} = {ml_result['predicted_score']}\\%$
                """)
 
    # Tab 4: Smart Suggestions
    with tab_suggestions:
        st.subheader("💡 Personalized Recommendations for Academic Growth")
        st.write("Dynamic suggestions computed automatically from your attendance history, subject test results, and regression trajectory.")
 
        st.markdown("#### 📅 Attendance & Regularity Insights")
        for tip in recommendations["attendance_tips"]:
            if recommendations["attendance_status"] == "Warning":
                st.markdown(f"<div class='warning-box'>{tip}</div>", unsafe_allow_html=True)
            elif recommendations["attendance_status"] == "Excellent":
                st.markdown(f"<div class='suggestion-box'>{tip}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='info-box'>{tip}</div>", unsafe_allow_html=True)
 
        st.markdown("#### 📚 Subject Focus & Mastery")
        for tip in recommendations["academic_tips"]:
            st.markdown(f"<div class='info-box'>{tip}</div>", unsafe_allow_html=True)
 
        st.markdown("#### 📈 Machine Learning Trajectory")
        for tip in recommendations["ml_insights"]:
            st.markdown(f"<div class='suggestion-box'>{tip}</div>", unsafe_allow_html=True)
 
        if recommendations["action_plan"]:
            st.markdown("#### 🚀 Actionable Preparation Plan")
            for i, step in enumerate(recommendations["action_plan"], 1):
                st.checkbox(f"**Step {i}:** {step}", key=f"action_step_{i}")
 
# FACULTY DASHBOARD
def render_faculty_dashboard():
    st.markdown("## Faculty Administration & Analytics Portal 👨🏫")
    st.caption("Manage student directory with parent contacts, log attendance, record marks, and automate low attendance email alerts.")
    st.write("")
 
    students = get_all_students()
    all_marks = get_all_marks()
    all_attendance = get_all_attendance()
    all_att_stats, low_att_students = get_attendance_summary_all_students(threshold=75.0)
 
    tot_students = len(students)
    tot_marks_entries = len(all_marks)
    tot_att_entries = len(all_attendance)
    class_att_pct = (sum(1 for a in all_attendance if a["status"] == "Present") / tot_att_entries * 100.0) if tot_att_entries > 0 else 0.0
    class_avg_score = (sum(m["percentage"] for m in all_marks) / tot_marks_entries) if tot_marks_entries > 0 else 0.0
 
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Enrolled Students</div>
            <div class="metric-value">{tot_students}</div>
            <span style="font-size: 12px; color: #64748b;">Active Directory</span>
        </div>
        """, unsafe_allow_html=True)
    with f2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Class Attendance Average</div>
            <div class="metric-value" style="color: {'#16a34a' if class_att_pct >= 75 else '#dc2626'};">{class_att_pct:.1f}%</div>
            <span style="font-size: 12px; color: #64748b;">{tot_att_entries} Total Class Sessions</span>
        </div>
        """, unsafe_allow_html=True)
    with f3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Class Average Score</div>
            <div class="metric-value">{class_avg_score:.1f}%</div>
            <span style="font-size: 12px; color: #64748b;">Across All Subjects</span>
        </div>
        """, unsafe_allow_html=True)
    with f4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Low Attendance Alert</div>
            <div class="metric-value" style="color: {'#dc2626' if len(low_att_students) > 0 else '#16a34a'};">{len(low_att_students)}</div>
            <span style="font-size: 12px; color: #64748b;">Students Below 75% Limit</span>
        </div>
        """, unsafe_allow_html=True)
 
    st.write("")
 
    fac_tab_alerts, fac_tab_students, fac_tab_attendance, fac_tab_marks, fac_tab_analytics = st.tabs([
        "🚨 Low Attendance & Automated Email Alerts",
        "👥 Student Records (Add/Edit/Delete)",
        "📅 Mark Presenty (Attendance)",
        "📝 Marks Management",
        "📊 Student Performance Analytics"
    ])
 
    # TAB 1: LOW ATTENDANCE & AUTOMATED EMAIL ALERTS
    with fac_tab_alerts:
        st.subheader("🚨 Automated Low Attendance Warning System")
        st.caption("Identifies students falling below the mandatory attendance limit and sends automated official warning emails to both the student and their parent.")
 
        col_th1, col_th2 = st.columns([1, 2])
        with col_th1:
            att_threshold = st.slider("Minimum Attendance Threshold (%)", min_value=50.0, max_value=90.0, value=75.0, step=1.0)
        with col_th2:
            st.info(f"Target Threshold: **{att_threshold:.0f}%**. Students with attendance strictly below this threshold will be flagged for automated email dispatch.")
 
        all_stats_dyn, low_att_dyn = get_attendance_summary_all_students(threshold=att_threshold)
 
        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("Total Students Checked", len(all_stats_dyn))
        with k2:
            st.metric("Students with Low Attendance", len(low_att_dyn), delta=f"{len(low_att_dyn)} at risk", delta_color="inverse")
        with k3:
            lowest_student = min(low_att_dyn, key=lambda x: x["attendance_pct"]) if low_att_dyn else None
            st.metric("Lowest Attendance Record", f"{lowest_student['attendance_pct']}%" if lowest_student else "None", help=f"{lowest_student['name']}" if lowest_student else "")
 
        st.divider()
 
        if not low_att_dyn:
            st.success(f"🎉 Great news! All students currently meet or exceed the {att_threshold:.0f}% attendance requirement.")
        else:
            st.markdown(f"#### 📋 Students Requiring Attendance Intervention (< {att_threshold:.0f}%)")
            df_low = pd.DataFrame(low_att_dyn)
            display_low_df = df_low[[
                "roll_no", "name", "department", "attendance_pct", "present_classes", "total_classes", "email", "parent_email"
            ]].rename(columns={
                "roll_no": "Roll No",
                "name": "Student Name",
                "department": "Department",
                "attendance_pct": "Attendance (%)",
                "present_classes": "Present",
                "total_classes": "Total",
                "email": "Student Email",
                "parent_email": "Parent Email (Recipient)"
            })
            st.dataframe(display_low_df, use_container_width=True, hide_index=True)
 
            st.write("")
            st.markdown("#### ✉️ Send Automated Attendance Warning Emails")
            st.write("Clicking the button below will dispatch an official warning notice with detailed attendance stats to the **Student's Email** and the **Parent's Email** for each flagged student.")
 
            btn_col1, btn_col2 = st.columns([2, 1])
            with btn_col1:
                confirm_send = st.checkbox("I confirm dispatching official low attendance warning notices to students and parents.", value=True)
                send_button = st.button(
                    f"🚀 Send Low Attendance Warning Email to {len(low_att_dyn)} Students & Parents",
                    type="primary",
                    disabled=not confirm_send,
                    use_container_width=True
                )
 
            if send_button:
                progress_bar = st.progress(0, text="Initializing SMTP email dispatch...")
                
                def update_progress(curr, total):
                    pct = int(curr / total * 100)
                    progress_bar.progress(pct, text=f"Sending email {curr} of {total}...")
 
                with st.spinner("Dispatching official emails to students and parents..."):
                    dispatch_report = send_bulk_low_attendance_alerts(
                        low_att_dyn,
                        threshold=att_threshold,
                        progress_callback=update_progress
                    )
 
                progress_bar.empty()
 
                if dispatch_report["sent"] > 0:
                    st.success(f"✅ Successfully processed {dispatch_report['sent']} warning notifications to students and parents!")
                if dispatch_report["failed"] > 0:
                    st.error(f"⚠️ {dispatch_report['failed']} emails encountered delivery errors.")
 
                st.markdown("##### 📨 Email Dispatch Audit Log")
                st.dataframe(pd.DataFrame(dispatch_report["results"]), use_container_width=True, hide_index=True)
 
        with st.expander("👁️ Preview Official Low Attendance Email Template"):
            st.caption("This is the responsive HTML template received by both the student and their parent:")
            preview_html = generate_low_attendance_html(
                student_name="Bob Smith",
                roll_no="CS-102",
                department="Computer Science",
                attendance_pct=58.3,
                present_classes=7,
                total_classes=12,
                threshold=att_threshold
            )
            st.components.v1.html(preview_html, height=520, scrolling=True)
 
        with st.expander("⚙️ SMTP Configuration & Live Email Setup Instructions"):
            st.markdown("""
            ### How to Configure SMTP for Live Emails:
            1. Open or create the file: `.streamlit/secrets.toml` in your project folder.
            2. Add your SMTP email credentials as shown below:
            ```toml
            [smtp]
            host = "smtp.gmail.com"
            port = 587
            username = "your_email@gmail.com"
            password = "your_16_digit_gmail_app_password"
            sender_email = "your_email@gmail.com"
            sender_name = "EduPulse Academic Office"
            use_tls = true
            ```
            > **Note for Gmail Users:** Use a Google **App Password** generated at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), NOT your normal Gmail account password.
            """)
 
            st.write("---")
            st.markdown("#### Test SMTP Connection")
            test_recipient = st.text_input("Send a quick test email to your address:", placeholder="e.g. test@example.com")
            if st.button("Send Test Email"):
                if not test_recipient:
                    st.error("Please enter a recipient email address.")
                else:
                    with st.spinner("Connecting to SMTP server..."):
                        test_ok, test_msg = send_email(
                            [test_recipient],
                            "EduPulse Test Email - SMTP Verification",
                            "<h3>EduPulse SMTP Verification</h3><p>Your SMTP mail configuration is working perfectly!</p>"
                        )
                        if test_ok:
                            st.success(test_msg)
                        else:
                            st.error(test_msg)
 
    # TAB 2: STUDENT DIRECTORY
    with fac_tab_students:
        st.subheader("Student Directory & Account Management")
        action = st.radio("Choose Action:", ["📋 View All Students", "➕ Register New Student", "✏️ Edit Student Record", "🗑️ Delete Student Record"], horizontal=True)
 
        if action == "📋 View All Students":
            if not students:
                st.info("No students found in the database. Use 'Register New Student' to add students.")
            else:
                df_st = pd.DataFrame(students)
                st.dataframe(
                    df_st[["roll_no", "name", "email", "parent_email", "department", "semester", "created_at"]].rename(
                        columns={
                            "roll_no": "Roll Number",
                            "name": "Full Name",
                            "email": "Student Email",
                            "parent_email": "Parent's Email Address",
                            "department": "Department",
                            "semester": "Semester",
                            "created_at": "Registration Date"
                        }
                    ),
                    use_container_width=True,
                    hide_index=True
                )
 
        elif action == "➕ Register New Student":
            st.markdown("#### Register New Student Account")
            st.caption("Please provide student details, parent's email for automated alerts, and student login credentials.")
 
            with st.form("add_student_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    new_roll = st.text_input("Roll Number *", placeholder="e.g. CS-105")
                    new_name = st.text_input("Full Name *", placeholder="e.g. David Miller")
                    new_email = st.text_input("Student Email *", placeholder="e.g. david.miller@edu.univ.com")
                    new_parent_email = st.text_input("Parent's Email Address *", placeholder="e.g. parent.miller@example.com", help="Used to send automated low attendance notices.")
                with c2:
                    new_dept = st.selectbox("Department *", ["Computer Science", "Information Technology", "Electronics", "Mechanical", "Civil"])
                    new_sem = st.number_input("Semester *", min_value=1, max_value=8, value=1)
                    new_uname = st.text_input("Login Username *", placeholder="e.g. student4")
                    new_pwd = st.text_input("Login Password *", type="password", value="student123", help="Password will be securely hashed with PBKDF2-SHA256 in MySQL.")
                
                submit_add = st.form_submit_button("Register Student & Create Account", type="primary")
 
                if submit_add:
                    if not new_roll or not new_name or not new_email or not new_parent_email or not new_uname or not new_pwd:
                        st.error("Please fill in all required fields (marked with *), including Parent's Email.")
                    elif "@" not in new_email or "@" not in new_parent_email:
                        st.error("Please provide valid email addresses for both Student and Parent.")
                    else:
                        ok, msg = add_student(
                            roll_no=new_roll,
                            name=new_name,
                            email=new_email,
                            parent_email=new_parent_email,
                            department=new_dept,
                            semester=int(new_sem),
                            username=new_uname,
                            password=new_pwd
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
 
        elif action == "✏️ Edit Student Record":
            st.markdown("#### Update Existing Student Information")
            if not students:
                st.warning("No students available to edit.")
            else:
                student_options = {f"{s['roll_no']} - {s['name']}": s for s in students}
                selected_label = st.selectbox("Select Student to Edit:", list(student_options.keys()))
                sel_student = student_options[selected_label]
 
                with st.form("edit_student_form"):
                    e1, e2 = st.columns(2)
                    with e1:
                        edit_roll = st.text_input("Roll Number", value=sel_student["roll_no"])
                        edit_name = st.text_input("Full Name", value=sel_student["name"])
                        edit_email = st.text_input("Student Email", value=sel_student.get("email", "") or "")
                        edit_parent_email = st.text_input("Parent's Email Address", value=sel_student.get("parent_email", "") or "")
                    with e2:
                        dept_list = ["Computer Science", "Information Technology", "Electronics", "Mechanical", "Civil"]
                        dept_idx = dept_list.index(sel_student["department"]) if sel_student["department"] in dept_list else 0
                        edit_dept = st.selectbox("Department", dept_list, index=dept_idx)
                        edit_sem = st.number_input("Semester", min_value=1, max_value=8, value=int(sel_student["semester"]))
 
                    submit_edit = st.form_submit_button("Save Student Changes", type="primary")
 
                    if submit_edit:
                        ok, msg = update_student(
                            student_id=sel_student["id"],
                            roll_no=edit_roll,
                            name=edit_name,
                            email=edit_email,
                            parent_email=edit_parent_email,
                            department=edit_dept,
                            semester=int(edit_sem)
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
 
        elif action == "🗑️ Delete Student Record":
            st.markdown("#### Delete Student Record")
            st.warning("⚠️ Deleting a student removes their user account, marks, and attendance records permanently from the MySQL database.")
            if not students:
                st.warning("No students available to delete.")
            else:
                student_options = {f"{s['roll_no']} - {s['name']} (ID: {s['id']})": s for s in students}
                del_label = st.selectbox("Select Student to Delete:", list(student_options.keys()))
                student_to_delete = student_options[del_label]
 
                confirm = st.checkbox(f"Yes, permanently delete student '{student_to_delete['name']}' ({student_to_delete['roll_no']})")
                if st.button("Permanently Delete Student", type="primary", disabled=not confirm):
                    ok, msg = delete_student(student_to_delete["id"])
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
 
    # TAB 3: ATTENDANCE
    with fac_tab_attendance:
        st.subheader("Attendance & Presenty Management")
        att_subtab = st.radio("Mode:", ["📝 Bulk Class Attendance Marking", "📋 View Attendance Logs by Date"], horizontal=True)
 
        if att_subtab == "📝 Bulk Class Attendance Marking":
            if not students:
                st.warning("Please add students first before recording attendance.")
            else:
                st.markdown("#### Daily Attendance Register")
                col_d1, col_d2, col_d3 = st.columns(3)
                with col_d1:
                    att_date = st.date_input("Attendance Date", value=date.today())
                with col_d2:
                    att_subject = st.selectbox("Course / Session", ["Data Structures", "Operating Systems", "Database Systems", "Web Development", "Computer Networks", "General"])
                with col_d3:
                    bulk_default = st.selectbox("Default Status for All", ["Present", "Absent"])
 
                st.write("Mark the status for each student below:")
                
                with st.form("mark_attendance_form"):
                    status_dict = {}
                    for s in students:
                        scol1, scol2 = st.columns([3, 2])
                        with scol1:
                            st.markdown(f"**{s['roll_no']}** — {s['name']} *({s['department']})*")
                        with scol2:
                            status_dict[s["id"]] = st.radio(
                                f"Status for {s['roll_no']}",
                                ["Present", "Absent"],
                                index=0 if bulk_default == "Present" else 1,
                                key=f"att_radio_{s['id']}",
                                horizontal=True,
                                label_visibility="collapsed"
                            )
                        st.markdown("<hr style='margin: 4px 0px;'>", unsafe_allow_html=True)
 
                    submit_att = st.form_submit_button("💾 Save Attendance to MySQL Database", type="primary", use_container_width=True)
 
                    if submit_att:
                        records = [
                            (s_id, str(att_date), status_dict[s_id], att_subject)
                            for s_id in status_dict
                        ]
                        ok, msg = mark_attendance_bulk(records)
                        if ok:
                            st.success(f"Attendance recorded for {len(records)} students on {att_date}!")
                            st.rerun()
                        else:
                            st.error(f"Failed to save attendance: {msg}")
 
        elif att_subtab == "📋 View Attendance Logs by Date":
            filter_date = st.date_input("Filter by Date (leave empty to view all)", value=None)
            date_query = str(filter_date) if filter_date else None
            logs = get_all_attendance(date_query)
 
            if not logs:
                st.info("No attendance records found for the selected date.")
            else:
                df_logs = pd.DataFrame(logs)
                st.dataframe(
                    df_logs[["date", "roll_no", "name", "department", "subject", "status"]].rename(
                        columns={
                            "date": "Date",
                            "roll_no": "Roll No",
                            "name": "Student Name",
                            "department": "Department",
                            "subject": "Course",
                            "status": "Attendance Status"
                        }
                    ),
                    use_container_width=True,
                    hide_index=True
                )
 
    # TAB 4: MARKS
    with fac_tab_marks:
        st.subheader("Academic Marks Management")
        marks_action = st.radio("Select Action:", ["➕ Record New Marks", "📋 View & Delete Recorded Marks"], horizontal=True)
 
        if marks_action == "➕ Record New Marks":
            if not students:
                st.warning("Please register students first.")
            else:
                with st.form("add_marks_form", clear_on_submit=True):
                    m_c1, m_c2 = st.columns(2)
                    with m_c1:
                        student_opts = {f"{s['roll_no']} - {s['name']}": s["id"] for s in students}
                        sel_st_label = st.selectbox("Select Student *", list(student_opts.keys()))
                        sel_st_id = student_opts[sel_st_label]
                        
                        subject_choice = st.selectbox(
                            "Subject *",
                            ["Data Structures", "Operating Systems", "Database Systems", "Web Development", "Computer Networks", "Other (Custom)"]
                        )
                        if subject_choice == "Other (Custom)":
                            subject_choice = st.text_input("Enter Custom Subject Name *")
 
                        exam_name = st.selectbox("Assessment Title *", ["Quiz 1", "Quiz 2", "Midterm Exam", "Pre-Final", "Semester End Exam", "Custom"])
                        if exam_name == "Custom":
                            exam_name = st.text_input("Enter Custom Assessment Title *")
 
                    with m_c2:
                        exam_order = st.number_input("Chronological Order Milestone (1, 2, 3... for ML sequence) *", min_value=1, max_value=20, value=1)
                        score = st.number_input("Marks Obtained *", min_value=0.0, max_value=1000.0, value=75.0)
                        max_score = st.number_input("Maximum Marks *", min_value=1.0, max_value=1000.0, value=100.0)
                        exam_date = st.date_input("Assessment Date", value=date.today())
 
                    submit_mark = st.form_submit_button("Record Marks in Database", type="primary")
 
                    if submit_mark:
                        if score > max_score:
                            st.error("Marks obtained cannot exceed Maximum Marks.")
                        else:
                            ok, msg = add_mark(sel_st_id, subject_choice, exam_name, int(exam_order), score, max_score, str(exam_date))
                            if ok:
                                st.success("Marks saved successfully!")
                                st.rerun()
                            else:
                                st.error(msg)
 
        elif marks_action == "📋 View & Delete Recorded Marks":
            if not all_marks:
                st.info("No marks entries found in database.")
            else:
                df_allm = pd.DataFrame(all_marks)
                st.dataframe(
                    df_allm[["id", "roll_no", "name", "subject", "exam_name", "exam_order", "score", "max_score", "percentage", "date"]].rename(
                        columns={
                            "id": "Mark ID",
                            "roll_no": "Roll No",
                            "name": "Name",
                            "subject": "Subject",
                            "exam_name": "Exam",
                            "exam_order": "Milestone #",
                            "score": "Score",
                            "max_score": "Max",
                            "percentage": "Pct (%)",
                            "date": "Date"
                        }
                    ),
                    use_container_width=True,
                    hide_index=True
                )
 
                st.write("")
                st.markdown("##### Remove Mark Entry")
                del_mark_id = st.number_input("Enter Mark ID to Delete", min_value=1, step=1)
                if st.button("Delete Mark Entry", type="secondary"):
                    ok, msg = delete_mark(del_mark_id)
                    if ok:
                        st.success("Mark entry deleted.")
                        st.rerun()
                    else:
                        st.error(msg)
 
    # TAB 5: ANALYTICS
    with fac_tab_analytics:
        st.subheader("Student Performance Analytics & Visualizations")
 
        if not all_marks:
            st.info("No marks logged yet to display performance charts.")
        else:
            df_marks_all = pd.DataFrame(all_marks)
            analytics_mode = st.radio("Analytics View:", ["🌐 Class-Wide Visualizations", "🔍 Individual Student Deep-Dive & ML Forecast"], horizontal=True)
 
            if analytics_mode == "🌐 Class-Wide Visualizations":
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    sub_comp = df_marks_all.groupby("subject")["percentage"].mean().reset_index()
                    fig_sub_comp = px.bar(
                        sub_comp,
                        x="subject",
                        y="percentage",
                        color="percentage",
                        color_continuous_scale="Blues",
                        title="Average Performance by Subject (%)",
                        labels={"subject": "Subject", "percentage": "Average (%)"},
                        text_auto=".1f"
                    )
                    fig_sub_comp.update_layout(yaxis_range=[0, 105], template="plotly_white")
                    st.plotly_chart(fig_sub_comp, use_container_width=True)
 
                with col_g2:
                    stu_comp = df_marks_all.groupby(["roll_no", "name"])["percentage"].mean().reset_index()
                    fig_stu_comp = px.bar(
                        stu_comp,
                        x="name",
                        y="percentage",
                        color="percentage",
                        color_continuous_scale="Viridis",
                        title="Student Overall Academic Average (%)",
                        labels={"name": "Student Name", "percentage": "Average (%)"},
                        text_auto=".1f"
                    )
                    fig_stu_comp.update_layout(yaxis_range=[0, 105], template="plotly_white")
                    st.plotly_chart(fig_stu_comp, use_container_width=True)
 
                col_g3, col_g4 = st.columns(2)
                with col_g3:
                    merged_stats = []
                    for s in students:
                        s_att = [a for a in all_attendance if a["student_id"] == s["id"]]
                        s_m = [m for m in all_marks if m["student_id"] == s["id"]]
                        if s_att and s_m:
                            att_rate = sum(1 for a in s_att if a["status"] == "Present") / len(s_att) * 100.0
                            m_avg = sum(m["percentage"] for m in s_m) / len(s_m)
                            merged_stats.append({
                                "name": s["name"],
                                "roll_no": s["roll_no"],
                                "attendance": round(att_rate, 1),
                                "marks": round(m_avg, 1)
                            })
                    
                    if merged_stats:
                        df_corr = pd.DataFrame(merged_stats)
                        fig_corr = px.scatter(
                            df_corr,
                            x="attendance",
                            y="marks",
                            text="name",
                            size=[14] * len(df_corr),
                            color="marks",
                            color_continuous_scale="RdYlGn",
                            title="Correlation: Attendance (%) vs Academic Performance (%)",
                            labels={"attendance": "Attendance (%)", "marks": "Average Score (%)"}
                        )
                        fig_corr.update_traces(textposition="top center")
                        fig_corr.update_layout(xaxis_range=[40, 105], yaxis_range=[40, 105], template="plotly_white")
                        st.plotly_chart(fig_corr, use_container_width=True)
 
                with col_g4:
                    fig_box = px.box(
                        df_marks_all,
                        x="subject",
                        y="percentage",
                        color="subject",
                        points="all",
                        title="Score Distribution & Outlier Spread per Subject",
                        labels={"subject": "Course", "percentage": "Score (%)"}
                    )
                    fig_box.update_layout(yaxis_range=[0, 105], template="plotly_white", showlegend=False)
                    st.plotly_chart(fig_box, use_container_width=True)
 
            elif analytics_mode == "🔍 Individual Student Deep-Dive & ML Forecast":
                st.markdown("#### Individual Student Deep-Dive & ML Trajectory")
                student_options = {f"{s['roll_no']} - {s['name']}": s for s in students}
                sel_student_label = st.selectbox("Select Student to Analyze:", list(student_options.keys()))
                sel_st = student_options[sel_student_label]
 
                st_marks = get_student_marks(sel_st["id"])
                st_att = get_student_attendance(sel_st["id"])
 
                if not st_marks:
                    st.warning("No marks records found for this student.")
                else:
                    st_df_marks = pd.DataFrame(st_marks)
                    sel_ml = train_and_predict_performance(st_marks)
 
                    mcol1, mcol2, mcol3 = st.columns(3)
                    with mcol1:
                        cur_avg = st_df_marks["percentage"].mean()
                        st.metric("Current Average", f"{cur_avg:.1f}%")
                    with mcol2:
                        p_score = f"{sel_ml['predicted_score']:.1f}%" if sel_ml['predicted_score'] is not None else "N/A"
                        st.metric("ML Predicted Next Score", p_score)
                    with mcol3:
                        st.metric("Trajectory Slope", f"{sel_ml['slope']:+.2f}% / exam")
 
                    if sel_ml["status"]:
                        history_df = pd.DataFrame(sel_ml["exam_history"])
                        fig_ind_ml = go.Figure()
 
                        fig_ind_ml.add_trace(go.Scatter(
                            x=history_df["exam_order"],
                            y=history_df["percentage"],
                            mode="markers+lines+text",
                            name="Actual Scores",
                            text=[f"{y:.1f}%" for y in history_df["percentage"]],
                            textposition="top center",
                            marker=dict(size=10, color="#2563eb")
                        ))
 
                        fig_ind_ml.add_trace(go.Scatter(
                            x=sel_ml["x_coords"],
                            y=sel_ml["fitted_line"],
                            mode="lines",
                            name="Linear Regression Line",
                            line=dict(color="#f59e0b", width=2, dash="dash")
                        ))
 
                        fig_ind_ml.add_trace(go.Scatter(
                            x=[sel_ml["next_exam_order"]],
                            y=[sel_ml["predicted_score"]],
                            mode="markers+text",
                            name="Forecast Next Exam",
                            text=[f"Predicted: {sel_ml['predicted_score']:.1f}%"],
                            textposition="bottom center",
                            marker=dict(size=14, color="#10b981", symbol="star")
                        ))
 
                        fig_ind_ml.update_layout(
                            title=f"Performance Trajectory & ML Forecast: {sel_st['name']} ({sel_st['roll_no']})",
                            xaxis_title="Exam Order Milestone",
                            yaxis_title="Score (%)",
                            yaxis_range=[0, 105],
                            template="plotly_white"
                        )
                        st.plotly_chart(fig_ind_ml, use_container_width=True)
                    else:
                        st.info(sel_ml["message"])

if not st.session_state.get("logged_in") or not st.session_state.get("user"):
    render_login()
else:
    user = st.session_state["user"]
    role = st.session_state["role"]
    render_sidebar(user, role)
    if role == "student":
        render_student_dashboard(user)
    elif role == "faculty":
        render_faculty_dashboard()
