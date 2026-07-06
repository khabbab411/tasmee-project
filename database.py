import os
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List
import pytz
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash

# إعداد السجلات
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]
MECCA_TIMEZONE = pytz.timezone("Asia/Riyadh")


def get_connection():
    """إنشاء اتصال بقاعدة البيانات"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_database():
    """إنشاء الجداول إذا لم تكن موجودة"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # جدول الطلاب
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students(
                user_id BIGINT PRIMARY KEY,
                name TEXT NOT NULL,
                state TEXT NOT NULL,
                last_submission_date DATE
            )
        """)

        # جدول التسميعات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS submissions(
                submission_id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES students(user_id) ON DELETE CASCADE,
                submission_type TEXT,
                file_id TEXT,
                text_content TEXT,
                timestamp TIMESTAMPTZ,
                status TEXT DEFAULT 'pending',
                teacher_reply_type TEXT,
                teacher_reply_content TEXT,
                original_message_id BIGINT,
                group_message_id BIGINT
            )
        """)

        # جدول المعلمات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS teachers(
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'teacher',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # إضافة مدير افتراضي
        cur.execute("SELECT COUNT(*) AS count FROM teachers")
        result = cur.fetchone()
        if result["count"] == 0:
            cur.execute("""
                INSERT INTO teachers
                (username, password, full_name, role, is_active)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                "admin",
                generate_password_hash("123456"),
                "مدير مقرأة زاد الفرقان",
                "admin",
                True
            ))

        conn.commit()
        cur.close()
        logger.info("تم إنشاء الجداول بنجاح")
    except Exception as e:
        logger.exception("فشل إنشاء الجداول")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


# ========== دوال الطلاب ==========

def save_user(user_id: int, name: str, state: str) -> None:
    """حفظ أو تحديث بيانات الطالب"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO students (user_id, name, state) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET name = %s, state = %s
        """, (user_id, name, state, name, state))
        conn.commit()
        cur.close()
        logger.info("تم حفظ المستخدم %s", user_id)
    except Exception as e:
        logger.exception("فشل حفظ المستخدم %s", user_id)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """جلب بيانات طالب"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, state FROM students WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        cur.close()
        if row:
            return {"name": row["name"], "state": row["state"]}
        return None
    except Exception as e:
        logger.exception("فشل جلب المستخدم %s", user_id)
        raise
    finally:
        if conn:
            conn.close()


def update_user_state(user_id: int, state: str) -> None:
    """تحديث حالة الطالب"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE students SET state = %s WHERE user_id = %s", (state, user_id))
        conn.commit()
        cur.close()
        logger.info("تم تحديث حالة المستخدم %s إلى %s", user_id, state)
    except Exception as e:
        logger.exception("فشل تحديث حالة المستخدم %s", user_id)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def update_last_submission_date(user_id: int) -> None:
    """تحديث تاريخ آخر تسميع للطالب"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE students SET last_submission_date = %s WHERE user_id = %s",
            (datetime.now(MECCA_TIMEZONE).date(), user_id)
        )
        conn.commit()
        cur.close()
        logger.info("تم تحديث تاريخ آخر تسميع للمستخدم %s", user_id)
    except Exception as e:
        logger.exception("فشل تحديث تاريخ آخر تسميع للمستخدم %s", user_id)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


# ========== دوال التسميعات ==========

def save_submission(
    user_id: int,
    submission_type: str,
    file_id: Optional[str],
    text_content: Optional[str],
    original_message_id: Optional[int]
) -> int:
    """حفظ تسميع جديد"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        timestamp = datetime.now(MECCA_TIMEZONE)
        cur.execute("""
            INSERT INTO submissions 
            (user_id, submission_type, file_id, text_content, timestamp, original_message_id) 
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING submission_id
        """, (user_id, submission_type, file_id, text_content, timestamp, original_message_id))
        submission_id = cur.fetchone()["submission_id"]
        conn.commit()
        cur.close()
        logger.info("تم حفظ تسميع جديد %s من المستخدم %s", submission_id, user_id)
        return submission_id
    except Exception as e:
        logger.exception("فشل حفظ التسميع للمستخدم %s", user_id)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def update_submission_reply(submission_id: int, reply_type: str, reply_content: str) -> None:
    """تحديث التسميع بالرد"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE submissions 
            SET status='replied', teacher_reply_type=%s, teacher_reply_content=%s 
            WHERE submission_id=%s
        """, (reply_type, reply_content, submission_id))
        conn.commit()
        cur.close()
        logger.info("تم تحديث الرد للتسميع %s", submission_id)
    except Exception as e:
        logger.exception("فشل تحديث الرد للتسميع %s", submission_id)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def get_submission(submission_id: int) -> Optional[Dict[str, Any]]:
    """جلب تسميع مع بيانات الطالب"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.user_id, s.name, sub.submission_type 
            FROM submissions sub 
            JOIN students s ON sub.user_id = s.user_id 
            WHERE sub.submission_id = %s
        """, (submission_id,))
        row = cur.fetchone()
        cur.close()
        return row
    except Exception as e:
        logger.exception("فشل جلب التسميع %s", submission_id)
        raise
    finally:
        if conn:
            conn.close()


def get_today_report() -> List[Dict[str, Any]]:
    """جلب إحصائيات اليوم"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        today = datetime.now(MECCA_TIMEZONE).date()
        cur.execute("""
            SELECT s.name, sub.submission_type 
            FROM submissions sub 
            JOIN students s ON sub.user_id = s.user_id 
            WHERE DATE(sub.timestamp) = %s
        """, (today,))
        rows = cur.fetchall()
        cur.close()
        return rows
    except Exception as e:
        logger.exception("فشل جلب تقرير اليوم")
        raise
    finally:
        if conn:
            conn.close()


def get_submissions_by_user(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """جلب آخر تسميعات الطالب"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT submission_id, submission_type, timestamp, status
            FROM submissions 
            WHERE user_id = %s 
            ORDER BY timestamp DESC 
            LIMIT %s
        """, (user_id, limit))
        rows = cur.fetchall()
        cur.close()
        return rows
    except Exception as e:
        logger.exception("فشل جلب تسميعات المستخدم %s", user_id)
        raise
    finally:
        if conn:
            conn.close()


def get_pending_submissions() -> List[Dict[str, Any]]:
    """جلب التسميعات المعلقة"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.user_id, s.name, sub.submission_id, sub.submission_type, sub.timestamp
            FROM submissions sub 
            JOIN students s ON sub.user_id = s.user_id 
            WHERE sub.status = 'pending'
            ORDER BY sub.timestamp ASC
        """)
        rows = cur.fetchall()
        cur.close()
        return rows
    except Exception as e:
        logger.exception("فشل جلب التسميعات المعلقة")
        raise
    finally:
        if conn:
            conn.close()


# ========== دوال المعلمات ==========

def authenticate_teacher(username: str, password: str) -> Optional[Dict[str, Any]]:
    """مصادقة المعلم"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, password, full_name, role, is_active
            FROM teachers 
            WHERE username = %s AND is_active = TRUE
        """, (username,))
        row = cur.fetchone()
        cur.close()
        
        if row and check_password_hash(row["password"], password):
            return {
                "id": row["id"],
                "username": row["username"],
                "full_name": row["full_name"],
                "role": row["role"],
                "is_active": row["is_active"]
            }
        return None
    except Exception as e:
        logger.exception("فشل مصادقة المعلم %s", username)
        raise
    finally:
        if conn:
            conn.close()


def get_teacher(teacher_id: int) -> Optional[Dict[str, Any]]:
    """جلب بيانات معلم"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, full_name, role, is_active, created_at
            FROM teachers 
            WHERE id = %s
        """, (teacher_id,))
        row = cur.fetchone()
        cur.close()
        return row
    except Exception as e:
        logger.exception("فشل جلب المعلم %s", teacher_id)
        raise
    finally:
        if conn:
            conn.close()


def get_teacher_by_username(username: str) -> Optional[Dict[str, Any]]:
    """جلب معلم بواسطة اسم المستخدم"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, full_name, role, is_active, created_at
            FROM teachers 
            WHERE username = %s
        """, (username,))
        row = cur.fetchone()
        cur.close()
        return row
    except Exception as e:
        logger.exception("فشل جلب المعلم %s", username)
        raise
    finally:
        if conn:
            conn.close()


def create_teacher(username: str, password: str, full_name: str, role: str = 'teacher') -> int:
    """إنشاء معلم جديد"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        hashed_password = generate_password_hash(password)
        cur.execute("""
            INSERT INTO teachers (username, password, full_name, role)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (username, hashed_password, full_name, role))
        teacher_id = cur.fetchone()["id"]
        conn.commit()
        cur.close()
        logger.info("تم إنشاء معلم جديد %s", username)
        return teacher_id
    except Exception as e:
        logger.exception("فشل إنشاء المعلم %s", username)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def update_teacher(
    teacher_id: int,
    full_name: Optional[str] = None,
    password: Optional[str] = None,
    is_active: Optional[bool] = None,
    role: Optional[str] = None
) -> None:
    """تحديث بيانات معلم"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        updates = []
        params = []
        
        if full_name is not None:
            updates.append("full_name = %s")
            params.append(full_name)
        if password is not None:
            updates.append("password = %s")
            params.append(generate_password_hash(password))
        if is_active is not None:
            updates.append("is_active = %s")
            params.append(is_active)
        if role is not None:
            updates.append("role = %s")
            params.append(role)
        
        if updates:
            params.append(teacher_id)
            query = f"UPDATE teachers SET {', '.join(updates)} WHERE id = %s"
            cur.execute(query, params)
            conn.commit()
            logger.info("تم تحديث المعلم %s", teacher_id)
        cur.close()
    except Exception as e:
        logger.exception("فشل تحديث المعلم %s", teacher_id)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def delete_teacher(teacher_id: int) -> None:
    """حذف معلم (تعطيل فقط)"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE teachers SET is_active = FALSE WHERE id = %s", (teacher_id,))
        conn.commit()
        cur.close()
        logger.info("تم تعطيل المعلم %s", teacher_id)
    except Exception as e:
        logger.exception("فشل تعطيل المعلم %s", teacher_id)
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def get_all_teachers(active_only: bool = True) -> List[Dict[str, Any]]:
    """جلب جميع المعلمين"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        query = """
            SELECT id, username, full_name, role, is_active, created_at
            FROM teachers
        """
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY id"
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        return rows
    except Exception as e:
        logger.exception("فشل جلب قائمة المعلمين")
        raise
    finally:
        if conn:
            conn.close()
