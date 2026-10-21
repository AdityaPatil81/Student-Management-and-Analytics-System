# 🎓 EduPulse - Student Management & Analytics System

A Streamlit web app for managing students, marks and attendance, with ML-based score prediction and automated low-attendance email alerts. Data is stored in MySQL.

## Features

**Student portal**
- View marks, attendance and subject-wise performance charts
- ML score prediction for the next exam (Linear Regression)
- Personalized study suggestions and action plan

**Faculty portal**
- Add, edit and delete student records (including parent email)
- Mark attendance in bulk and record marks
- Class-wide analytics and individual student forecasts
- Automatic email warnings to students and parents when attendance falls below a set threshold (default 75%)

## Tech Stack

Python, Streamlit, MySQL, scikit-learn, pandas, NumPy, Plotly

## Setup

1. **Clone the repo**
```bash
   git clone https://github.com/AdityaPatil81/Student-Management-and-Analytics-System.git
   cd Student-Management-and-Analytics-System
```

2. **Install dependencies**
```bash
   pip install -r requirements.txt
```

3. **Start MySQL** and make sure the credentials in `DB_CONFIG` (top of `app.py`) match your setup. The database and tables are created automatically on first run.

4. **(Optional) Configure email.** Create `.streamlit/secrets.toml`:
```toml
   [smtp]
   host = "smtp.gmail.com"
   port = 587
   username = "your_email@gmail.com"
   password = "your_gmail_app_password"
   sender_email = "your_email@gmail.com"
   sender_name = "EduPulse Academic Office"
   use_tls = true
```
   Without this, emails run in simulation mode and nothing is actually sent.

5. **Run the app**
```bash
   streamlit run app.py
```

## Default Demo Accounts

| Role | Username | Password |
|---|---|---|
| Faculty | `faculty` | `faculty123` |
| Student | `student1` | `student123` |

Change these passwords before using the app with real data.

## Project Structure

```
├── app.py              # Main application
├── requirements.txt    # Python dependencies
├── .gitignore
└── README.md
```

## Author

Aditya Patil