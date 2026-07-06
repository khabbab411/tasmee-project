from flask import render_template, request, redirect, url_for, session

from web.auth import authenticate

from database import get_all_submissions


def register_routes(app):

    @app.route("/", methods=["GET", "POST"])
    def login():

        if "teacher_id" in session:
            return redirect(url_for("dashboard"))

        error = None

        if request.method == "POST":

            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            teacher = authenticate(username, password)

            if teacher:

                session["teacher_id"] = teacher["id"]
                session["teacher_name"] = teacher["full_name"]
                session["teacher_role"] = teacher["role"]

                return redirect(url_for("dashboard"))

            error = "اسم المستخدم أو كلمة المرور غير صحيحة."

        return f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>مقرأة زاد الفرقان</title>
<style>
body{{font-family:Tahoma;background:#f5f5f5;text-align:center;margin-top:80px}}
form{{display:inline-block;background:white;padding:25px;border-radius:10px}}
input{{display:block;width:250px;padding:10px;margin:10px 0}}
button{{padding:10px 20px}}
p{{color:red}}
</style>
</head>
<body>

<h2>📖 مقرأة زاد الفرقان</h2>

<form method="POST">
<input name="username" placeholder="اسم المستخدم">
<input type="password" name="password" placeholder="كلمة المرور">
<button type="submit">تسجيل الدخول</button>
</form>

<p>{error or ""}</p>

</body>
</html>
"""

    @app.route("/dashboard")
    def dashboard():
        if "teacher_id" not in session:
            return redirect(url_for("login"))
        return f"""
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
        <meta charset="UTF-8">
        <title>لوحة التحكم</title>
        <style>
        body {{ margin:0; font-family:Tahoma; background:#f3f5f7; }}
        .header {{ background:#0b6b4b; color:white; padding:18px; font-size:22px; text-align:center; }}
        .container {{ width:90%; margin:auto; margin-top:30px; }}
        .card {{ background:white; padding:20px; border-radius:12px; margin-bottom:20px; box-shadow:0 0 10px rgba(0,0,0,.08); }}
        .btn{{ display:inline-block; padding:12px 20px; background:#0b6b4b; color:white; text-decoration:none; border-radius:8px; margin:8px; }}
        </style>
        </head>
        <body>
        <div class="header"> 📖 مقرأة زاد الفرقان </div>
        <div class="container">
        <div class="card">
        <h2>مرحباً {session["teacher_name"]}</h2>
        <p>صلاحيتك : {session["teacher_role"]}</p>
        </div>
        <div class="card">
        <a class="btn" href="/submissions">📥 التسميعات الجديدة</a>
        <a class="btn" href="/students">👥 الطلاب</a>
        <a class="btn" href="/reports">📊 الإحصائيات</a>
        <a class="btn" href="/logout">🚪 تسجيل الخروج</a>
        </div>
        </div>
        </body>
        </html>
        """

    @app.route("/submissions")
    def submissions():
        if "teacher_id" not in session:
            return redirect(url_for("login"))
        return "<h2>📥 صفحة التسميعات (قريباً)</h2>"

    @app.route("/students")
    def students():
        if "teacher_id" not in session:
            return redirect(url_for("login"))
        return "<h2>👥 صفحة الطلاب (قريباً)</h2>"

    @app.route("/reports")
    def reports():
        if "teacher_id" not in session:
            return redirect(url_for("login"))
        return "<h2>📊 صفحة الإحصائيات (قريباً)</h2>"

    @app.route("/submissions")
def submissions():

    if "teacher_id" not in session:
        return redirect(url_for("login"))

    rows = get_all_submissions()

    return render_template(
        "submissions.html",
        submissions=rows
    )

    @app.route("/logout")
    def logout():

        session.clear()

        return redirect(url_for("login"))
