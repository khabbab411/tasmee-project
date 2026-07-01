from flask import Flask, render_template
from threading import Thread
import os
import logging

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

app = Flask(__name__)

# سنستخدمه لاحقًا لحفظ جلسة تسجيل الدخول
app.secret_key = os.environ.get("SECRET_KEY", "zadaalfurqan-secret-key")


@app.route("/")
def login():
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    return """
    <h2 style="font-family:Tahoma;text-align:center;margin-top:60px;">
    مرحبًا بك في لوحة مقرأة زاد الفرقان
    </h2>
    """


def run():
    port = int(os.environ.get("PORT", 8080))
    print(f"📡 Web Server Running on Port {port}")
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
