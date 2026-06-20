import logging
import os
import time
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from keep_alive import keep_alive

# 1. إعداد السجلات (Logs)
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. إعداد قاعدة البيانات (SQLite) ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (user_id INTEGER PRIMARY KEY, name TEXT, step TEXT)''')
    conn.commit()
    conn.close()

def save_user(user_id, name, step):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO students (user_id, name, step) VALUES (?, ?, ?)", (user_id, name, step))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT name, step FROM students WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"name": row[0], "step": row[1]}
    return None

# --- 3. الإعدادات ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "ضع_التوكن_هنا")
GROUP_ID = int(os.environ.get("TEACHERS_GROUP_ID", "ضع_ID_المجموعة_هنا"))

# مخزن مؤقت لانتظار الرد (لا يحتاج قاعدة بيانات لأنه لحظي)
waiting_for_reply = {}

# --- 4. الدوال المساعدة ---
def is_valid_name(name: str) -> bool:
    name = name.strip()
    return len(name) >= 5 and len(name.split()) >= 2

# --- 5. معالجات البوت ---
async def start(update: Update, context):
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        user = get_user(user_id)
        if user and user['name']:
            await update.message.reply_text(f"أهلاً بك مجدداً يا {user['name']}! يمكنك إرسال صوتية التسميع الآن.")
            save_user(user_id, user['name'], "awaiting_voice")
        else:
            save_user(user_id, "", "awaiting_name")
            await update.message.reply_text("أهلاً بك! الرجاء إدخال اسمك الكامل (ثلاثي) للبدء.")

async def handle_text(update: Update, context):
    user_id = update.effective_user.id
    text = update.message.text
    if update.effective_chat.type == "private":
        user = get_user(user_id)
        if user and user.get("step") == "awaiting_name":
            if is_valid_name(text):
                save_user(user_id, text, "awaiting_voice")
                await update.message.reply_text(f"تم حفظ اسمك يا {text}. الآن أرسل صوتية التسميع.")
            else:
                await update.message.reply_text("الاسم قصير جداً، يرجى إرسال اسمك الثلاثي.")
    
    elif update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply and waiting_for_reply[teacher_id]["type"] == "text":
            student_id = waiting_for_reply[teacher_id]["student_id"]
            await context.bot.send_message(chat_id=student_id, text=f"ملاحظة نصية من المعلمة:\n{text}")
            await update.message.reply_text(f"✅ تم إرسال الرد إلى {waiting_for_reply[teacher_id]['student_name']}")
            del waiting_for_reply[teacher_id]

async def handle_voice(update: Update, context):
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        user = get_user(user_id)
        if user and user.get("name"):
            name = user["name"]
            keyboard = [[InlineKeyboardButton("رد نصي", callback_data=f"r_t_{user_id}_{name}"),
                         InlineKeyboardButton("رد صوتي", callback_data=f"r_v_{user_id}_{name}")]]
            await context.bot.send_voice(chat_id=GROUP_ID, voice=update.message.voice.file_id,
                                         caption=f"تسميع: {name}",
                                         reply_markup=InlineKeyboardMarkup(keyboard))
            await update.message.reply_text("✅ تم إرسال تسميعك للمعلمات.")
        else:
            await update.message.reply_text("يرجى إرسال /start أولاً.")
    
    elif update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply and waiting_for_reply[teacher_id]["type"] == "voice":
            student_id = waiting_for_reply[teacher_id]["student_id"]
            await context.bot.send_voice(chat_id=student_id, voice=update.message.voice.file_id)
            await update.message.reply_text(f"✅ تم إرسال الرد الصوتي إلى {waiting_for_reply[teacher_id]['student_name']}")
            del waiting_for_reply[teacher_id]

async def handle_callback(update: Update, context):
    query = update.callback_query
    data = query.data.split('_')
    waiting_for_reply[query.from_user.id] = {
        "type": "text" if data[1] == "t" else "voice",
        "student_id": int(data[2]),
        "student_name": data[3]
    }
    msg = "اكتب الرد النصي الآن:" if data[1] == "t" else "أرسل الرد الصوتي الآن:"
    await query.edit_message_caption(caption=query.message.caption + f"\n\n⏳ {msg}")
    await query.answer()

# --- 6. تشغيل البوت مع نظام الحماية ---
def main():
    init_db() # تهيئة قاعدة البيانات
    keep_alive() # تشغيل سيرفر الاستيقاظ
    
    print("⏳ جاري الانتظار 10 ثوانٍ لضمان استقرار الاتصال...")
    time.sleep(10)
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_text))
    application.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE, handle_voice))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & filters.Chat(GROUP_ID), handle_text))
    application.add_handler(MessageHandler(filters.VOICE & filters.Chat(GROUP_ID), handle_voice))

    print("🚀 البوت بدأ العمل بنجاح...")
    
    # حلقة لانهائية لضمان إعادة التشغيل التلقائي عند حدوث خطأ
    while True:
        try:
            application.run_polling(drop_pending_updates=True, close_loop=False)
        except Exception as e:
            logger.error(f"⚠️ خطأ في الاتصال، إعادة المحاولة بعد 5 ثوانٍ: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
