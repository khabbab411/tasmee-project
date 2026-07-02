import os
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash
import pytz

DATABASE_URL = os.environ["DATABASE_URL"]
MECCA_TIMEZONE = pytz.timezone("Asia/Riyadh")


def get_connection():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )


def init_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students(
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            state TEXT,
            last_submission_date TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions(
            submission_id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES students(user_id) ON DELETE CASCADE,
            submission_type TEXT,
            file_id TEXT,
            text_content TEXT,
            timestamp TEXT,
            status TEXT,
            teacher_reply_type TEXT,
            teacher_reply_content TEXT,
            original_message_id BIGINT,
            group_message_id BIGINT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS teachers(
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'teacher',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TEXT
        )
    """)

    cur.execute("SELECT COUNT(*) AS count FROM teachers")
    result = cur.fetchone()

    if result["count"] == 0:
        cur.execute("""
            INSERT INTO teachers
            (username, password, full_name, role, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            "admin",
            generate_password_hash("123456"),
            "مدير مقرأة زاد الفرقان",
            "admin",
            True,
            datetime.now(MECCA_TIMEZONE).isoformat()
        ))

    conn.commit()
    cur.close()
    conn.close()
