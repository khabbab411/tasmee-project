from database import get_connection
from werkzeug.security import check_password_hash


def authenticate(username, password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM teachers
        WHERE username = %s
        AND is_active = TRUE
        """,
        (username,)
    )

    teacher = cur.fetchone()

    cur.close()
    conn.close()

    if teacher is None:
        return None

    if not check_password_hash(teacher["password"], password):
        return None

    return teacher
