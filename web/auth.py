import sqlite3
from werkzeug.security import check_password_hash

DATABASE_NAME = "users.db"


def authenticate(username, password):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row

    teacher = conn.execute(
        """
        SELECT *
        FROM teachers
        WHERE username = ?
        AND is_active = 1
        """,
        (username,)
    ).fetchone()

    conn.close()

    if teacher is None:
        return None

    if not check_password_hash(teacher["password"], password):
        return None

    return teacher
