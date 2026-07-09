from flask import render_template, request, redirect, url_for, session, send_from_directory
from web.auth import authenticate
from database import get_all_submissions, get_submission_by_id
import os


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
body{{margin:0;font-family:Tahoma;background:#f3f5f7}}
.header{{background:#0b6b4b;color:white;padding:18px;font-size:22px;text-align:center}}
.container{{width:90%;margin:auto;margin-top:30px}}
.card{{background:white;padding:20px;border-radius:12px;margin-bottom:20px;box-shadow:0 0 10px rgba(0,0,0,.08)}}
.btn{{display:inline-block;padding:12px 20px;background:#0b6b4b;color:white;text-decoration:none;border-radius:8px;margin:8px}}
</style>
</head>
<body>

<div class="header">
📖 مقرأة زاد الفرقان
</div>

<div class="container">

<div class="card">
<h2>مرحباً {session["teacher_name"]}</h2>
<p>الصلاحية : {session["teacher_role"]}</p>
</div>

<div class="card">
<a class="btn" href="/submissions">📥 التسميعات</a>
<a class="btn" href="/students">👥 الطلاب</a>
<a class="btn" href="/reports">📊 الإحصائيات</a>
<a class="btn" href="/logout">🚪 تسجيل الخروج</a>
</div>

</div>

</body>
</html>
"""

    @app.route("/submission/<int:submission_id>")
    def submission(submission_id):
        if "teacher_id" not in session:
            return redirect(url_for("login"))
        s = get_submission_by_id(submission_id)

        print("FILE NAME:", s["file_id"])
        print("FILE EXISTS:", os.path.exists("data/voices/" + s["file_id"]) if s["file_id"] else "NO FILE")

        if not s:
            return "التسميع غير موجود"
        return f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">

<head>
<meta charset="UTF-8">
<title>التسميع</title>

<style>

body{{font-family:Tahoma;background:#f5f5f5;padding:40px}}

.card{{
background:white;
padding:20px;
border-radius:10px;
max-width:700px;
margin:auto;
}}

textarea{{
width:100%;
height:180px;
margin-top:15px;
}}

button{{
padding:12px 25px;
margin-top:15px;
}}

</style>

</head>

<body>

<div class="card">

<h2>{s["name"]}</h2>

<p><b>النوع:</b> {s["submission_type"]}</p>

<p><b>الحالة:</b> {s["status"]}</p>

<p><b>الوقت:</b> {s["timestamp"]}</p>

<hr>

<p>الصوت:</p>
{"<audio controls style='width:100%'><source src='/voices/" + s["file_id"] + "' type='audio/ogg'></audio>" if s["file_id"] else "لا يوجد ملف صوتي"}

<hr>

<form>

<textarea placeholder="اكتب رد المعلمة هنا..."></textarea>

<br>

<button disabled>
إرسال الرد (سنفعله بالخطوة التالية)
</button>

</form>

</div>

</body>

</html>
"""

    @app.route("/submissions")
    def submissions():
        if "teacher_id" not in session:
            return redirect(url_for("login"))
        rows = get_all_submissions()
        return render_template(
            "submissions.html",
            submissions=rows
        )

    @app.route("/students")
    def students():

        if "teacher_id" not in session:
            return redirect(url_for("login"))

        return "<h2 style='text-align:center'>👥 صفحة الطلاب (قريباً)</h2>"

    @app.route("/reports")
    def reports():

        if "teacher_id" not in session:
            return redirect(url_for("login"))

        return "<h2 style='text-align:center'>📊 صفحة الإحصائيات (قريباً)</h2>"

    @app.route("/voices/<filename>")
    def voices(filename):

        if "teacher_id" not in session:
            return redirect(url_for("login"))

        filepath = os.path.join("data", "voices", filename)

        print("VOICE PATH:", filepath)
        print("EXISTS:", os.path.exists(filepath))

        return send_from_directory(
            "data/voices",
            filename
        )

    @app.route("/logout")
    def logout():

        session.clear()

        return redirect(url_for("login"))
