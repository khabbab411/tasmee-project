import sqlite3
from datetime import datetime
import pytz
from werkzeug.security import generate_password_hash

DATABASE_NAME = "users.db"
MECCA_TIMEZONE = pytz.timezone("Asia/Riyadh")


def get_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_connection()
    c = conn.cursor()

    c.execute("PRAGMA foreign_keys = ON")

    c.execute("""
        CREATE TABLE IF NOT EXISTS students(
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            state TEXT,
            last_submission_date TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS submissions(
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            submission_type TEXT,
            file_id TEXT,
            text_content TEXT,
            timestamp TEXT,
            status TEXT,
            teacher_reply_type TEXT,
            teacher_reply_content TEXT,
            original_message_id INTEGER,
            group_message_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES students(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS teachers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'teacher',
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    c.execute("SELECT COUNT(*) FROM teachers")

    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO teachers
            (username,password,full_name,role,is_active,created_at)
            VALUES(?,?,?,?,?,?)
        """,(
            "admin",
            generate_password_hash("123456"),
            "مدير مقرأة زاد الفرقان",
            "admin",
            1,
            datetime.now(MECCA_TIMEZONE).isoformat()
        ))

    conn.commit()
    conn.close()
