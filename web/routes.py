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

        return "LOGIN PAGE"

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
