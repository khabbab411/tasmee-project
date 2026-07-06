from flask import render_template, request, redirect, url_for, session

from web.auth import authenticate


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
        <div style="font-family:Tahoma;text-align:center;margin-top:60px">

            <h2>📖 مقرأة زاد الفرقان</h2>

            <h3>مرحبًا {session['teacher_name']}</h3>

            <p>تم تسجيل الدخول بنجاح.</p>

            <br>

            <a href="/logout">
                تسجيل الخروج
            </a>

        </div>
        """

    @app.route("/logout")
    def logout():

        session.clear()

        return redirect(url_for("login"))
