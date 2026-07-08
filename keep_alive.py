from flask import Flask
from threading import Thread
import logging
import os

from web.routes import register_routes
from database import init_database

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

app = Flask(
    __name__,
    template_folder="web/templates",
    static_folder="web/static"
)
app.secret_key = os.environ.get("SECRET_KEY", "zadaalfurqan-secret-key")

# إنشاء الجداول قبل تشغيل الموقع
init_database()

register_routes(app)

def run():
    port = int(os.environ.get("PORT", 8080))
    print(f"📡 Web Server Running on Port {port}")
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
