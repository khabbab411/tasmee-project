from flask import Flask, render_template
from threading import Thread
import os
import logging

# تقليل رسائل Flask
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

app = Flask(__name__)

# الصفحة الرئيسية (سيتم تحويلها لاحقًا لتسجيل الدخول)
@app.route("/")
def login():
    return render_template("login.html")

# لوحة المعلمات (سنطورها لاحقًا)
@app.route("/dashboard")
def dashboard():
    return "<h2>لوحة المعلمات</h2>"

def run():
    port = int(os.environ.get("PORT", 8080))
    print(f"📡 Web Server Running on Port {port}")
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
