from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "✅ البوت شغال واستجابة السيرفر سريعة"

def run():
    # Render يمرر المنفذ تلقائياً عبر متغير البيئة PORT
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 بدء تشغيل سيرفر Flask على المنفذ: {port}")
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True  # جعل الخيط يعمل في الخلفية بشكل مستقل
    t.start()
