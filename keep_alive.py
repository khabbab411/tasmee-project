from flask import Flask, render_template
from threading import Thread
import os
import logging

# تقليل ضجيج السجلات لـ Flask
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask('')

@app.route('/')
def home():
        # هذه الرسالة ستظهر لك عند فتح الرابط في المتصفح
    return render_template("login.html")

def run():
    port = int(os.environ.get('PORT', 8080))
    print(f"📡 سيرفر الاستيقاظ يعمل على المنفذ {port}...")
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
