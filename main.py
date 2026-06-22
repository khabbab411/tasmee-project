import logging
import os
import time
import sqlite3
from datetime import datetime
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from keep_alive import keep_alive

# 1. إعداد السجلات
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. إعداد قاعدة البيانات ---
DATABASE_NAME = 'users.db'
MECCA_TIMEZONE = pytz.timezone('Asia/Riyadh')

def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute('PRAGMA foreign_keys = ON')
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (user_id INTEGER PRIMARY KEY, name TEXT, state TEXT, last_submission_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS submissions
                 (submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  submission_type TEXT,
                  file_id TEXT,
                  text_content TEXT,
                  timestamp TEXT,
                  status TEXT,
                  teacher_reply_type TEXT,
                  teacher_reply_content TEXT,
                  original_message_id INTEGER,
                  group_message_id INTEGER,
                  FOREIGN KEY (user_id) REFERENCES students(user_id))''')
    conn.commit()
    conn.close()

def save_user(user_id, name, state):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO students (user_id, name, state) VALUES (?, ?, ?)", (user_id, name, state))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT name, state FROM students WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"name": row[0], "state": row[1]}
    return None

def update_user_state(user_id, state):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("UPDATE students SET state=? WHERE user_id=?", (state, user_id))
    conn.commit()
    conn.close()

def save_submission(user_id, submission_type, file_id=None, text_content=None, original_message_id=None):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    timestamp = datetime.now(MECCA_TIMEZONE).isoformat()
    c.execute("INSERT INTO submissions (user_id, submission_type, file_id, text_content, timestamp, status, original_message_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (user_id, submission_type, file_id, text_content, timestamp, 'pending', original_message_id))
    submission_id = c.lastrowid
    conn.commit()
    conn.close()
    return submission_id

# --- 3. الإعدادات ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "ضع_التوكن_هنا")
GROUP_ID = int(os.environ.get("TEACHERS_GROUP_ID", "ضع_ID_المجموعة_هنا"))

waiting_for_reply = {}
pending_user_actions = {}

# --- 4. لوحات المفاتيح الثابتة (Reply Keyboard) ---
def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("🎤 إرسال تسميع"), KeyboardButton("❓ سؤال المعلم")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_submission_type_keyboard():
    keyboard = [
        [KeyboardButton("📖 ورد الحفظ"), KeyboardButton("🔄 ورد المراجعة")],
        [KeyboardButton("🔙 رجوع للقائمة الرئيسية")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_question_type_keyboard():
    keyboard = [
        [KeyboardButton("🎙️ سؤال صوتي"), KeyboardButton("✍️ سؤال نصي")],
        [KeyboardButton("🔙 رجوع للقائمة الرئيسية")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- 5. معالجات البوت ---
async def start(update: Update, context):
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        user = get_user(user_id)
        if user and user['name']:
            await update.message.reply_text(f"أهلاً بك مجدداً يا {user['name']}!", reply_markup=get_main_menu_keyboard())
            update_user_state(user_id, "main_menu")
        else:
            save_user(user_id, "", "awaiting_name")
            await update.message.reply_text("أهلاً بك! الرجاء إدخال اسمك الكامل (ثلاثي) للبدء.", reply_markup=ReplyKeyboardRemove())

async def handle_text(update: Update, context):
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    text = update.message.text
    user = get_user(user_id)

    if chat_type == "private":
        if user and user.get("state") == "awaiting_name":
            if len(text.strip().split()) >= 2:
                save_user(user_id, text, "main_menu")
                await update.message.reply_text(f"تم حفظ اسمك يا {text}.", reply_markup=get_main_menu_keyboard())
            else:
                await update.message.reply_text("الاسم قصير جداً، يرجى إرسال اسمك الثلاثي.")
        
        elif text == "🎤 إرسال تسميع":
            await update.message.reply_text("الرجاء اختيار نوع التسميع:", reply_markup=get_submission_type_keyboard())
            update_user_state(user_id, "awaiting_submission_type")
        
        elif text == "❓ سؤال المعلم":
            await update.message.reply_text("الرجاء اختيار نوع السؤال:", reply_markup=get_question_type_keyboard())
            update_user_state(user_id, "awaiting_question_type")
            
        elif text == "🔙 رجوع للقائمة الرئيسية":
            pending_user_actions.pop(user_id, None)
            await update.message.reply_text("أهلاً بك في القائمة الرئيسية.", reply_markup=get_main_menu_keyboard())
            update_user_state(user_id, "main_menu")

        elif text == "📖 ورد الحفظ":
            await update.message.reply_text("ممتاز! الرجاء تسجيل ورد الحفظ الآن.", reply_markup=get_submission_type_keyboard())
            update_user_state(user_id, "awaiting_hifz_submission")
        
        elif text == "🔄 ورد المراجعة":
            await update.message.reply_text("ممتاز! الرجاء تسجيل ورد المراجعة الآن.", reply_markup=get_submission_type_keyboard())
            update_user_state(user_id, "awaiting_murajaah_submission")

        elif text == "🎙️ سؤال صوتي":
            await update.message.reply_text("الرجاء تسجيل سؤالك الصوتي الآن.", reply_markup=get_question_type_keyboard())
            update_user_state(user_id, "awaiting_voice_question")

        elif text == "✍️ سؤال نصي":
            await update.message.reply_text("الرجاء كتابة سؤالك النصي الآن.", reply_markup=get_question_type_keyboard())
            update_user_state(user_id, "awaiting_text_question")

        elif user and user.get("state") == "awaiting_text_question":
            pending_user_actions[user_id] = {"type": "question", "subtype": "سؤال_نصي", "text_content": text, "file_id": None, "original_message_id": update.message.message_id}
            await update.message.reply_text("وصلني سؤالك النصي، هل أنت متأكد من الإرسال؟", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ إرسال للمعلمة", callback_data="confirm_send")], [InlineKeyboardButton("❌ إلغاء", callback_data="confirm_resend")]]))
            update_user_state(user_id, "awaiting_confirmation")

    elif chat_type == "group" and update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply:
            data = waiting_for_reply[teacher_id]
            if data["type"] == "text":
                await context.bot.send_message(chat_id=data["student_id"], text=f"💌 وصلك رد من المعلمة بخصوص: [{data['submission_type']}]\n\n{text}")
                conn = sqlite3.connect(DATABASE_NAME)
                c = conn.cursor()
                c.execute("UPDATE submissions SET status='replied', teacher_reply_type='text', teacher_reply_content=? WHERE submission_id=?", (text, data["submission_id"]))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"✅ تم إرسال الرد النصي إلى {data['student_name']}")
                del waiting_for_reply[teacher_id]

async def handle_voice(update: Update, context):
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    user = get_user(user_id)

    if chat_type == "private":
        if user and user.get("state") in ["awaiting_hifz_submission", "awaiting_murajaah_submission", "awaiting_voice_question"]:
            sub_type = "حفظ" if user["state"] == "awaiting_hifz_submission" else "مراجعة" if user["state"] == "awaiting_murajaah_submission" else "سؤال_صوتي"
            pending_user_actions[user_id] = {"type": "submission" if "submission" in user["state"] else "question", "subtype": sub_type, "file_id": update.message.voice.file_id, "text_content": None, "original_message_id": update.message.message_id}
            await update.message.reply_text("وصلني تسجيلك، يمكنك الاستماع إليه بالأعلى للتأكد.", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ إرسال للمعلمة", callback_data="confirm_send")], [InlineKeyboardButton("❌ إعادة التسجيل", callback_data="confirm_resend")]]))
            update_user_state(user_id, "awaiting_confirmation")

    elif chat_type == "group" and update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply:
            data = waiting_for_reply[teacher_id]
            if data["type"] == "voice":
                await context.bot.send_voice(chat_id=data["student_id"], voice=update.message.voice.file_id)
                await context.bot.send_message(chat_id=data["student_id"], text=f"💌 وصلك رد صوتي من المعلمة بخصوص: [{data['submission_type']}]")
                conn = sqlite3.connect(DATABASE_NAME)
                c = conn.cursor()
                c.execute("UPDATE submissions SET status='replied', teacher_reply_type='voice', teacher_reply_content=? WHERE submission_id=?", (update.message.voice.file_id, data["submission_id"]))
                conn.commit()
                conn.close()
                await update.message.reply_text(f"✅ تم إرسال الرد الصوتي إلى {data['student_name']}")
                del waiting_for_reply[teacher_id]

async def handle_callback(update: Update, context):
    query = update.callback_query
    callback_data = query.data
    await query.answer()

    if callback_data == "confirm_send":
        user_id = query.from_user.id
        user = get_user(user_id)
        if user_id in pending_user_actions:
            action = pending_user_actions.pop(user_id)
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            timestamp = datetime.now(MECCA_TIMEZONE).isoformat()
            c.execute("INSERT INTO submissions (user_id, submission_type, file_id, text_content, timestamp, status, original_message_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (user_id, action["subtype"], action["file_id"], action["text_content"], timestamp, 'pending', action["original_message_id"]))
            sub_id = c.lastrowid
            conn.commit()
            conn.close()
            
            caption = f"{'🎤 تسميع جديد' if action['type'] == 'submission' else '❓ سؤال جديد'} - {action['subtype']}: {user['name']}\nID: {user_id}"
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("رد ↩️", callback_data=f"rep_{sub_id}")]])
            
            if action["file_id"]:
                await context.bot.send_voice(chat_id=GROUP_ID, voice=action["file_id"], caption=caption, reply_markup=markup)
            else:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"{caption}\n\n{action['text_content']}", reply_markup=markup)
            
            await query.edit_message_text("✅ تم الإرسال للمعلمة بنجاح.")
            update_user_state(user_id, "main_menu")

    elif callback_data == "confirm_resend":
        user_id = query.from_user.id
        pending_user_actions.pop(user_id, None)
        await query.edit_message_text("تم الإلغاء. يمكنك البدء من جديد من القائمة.")
        update_user_state(user_id, "main_menu")

    elif callback_data.startswith("rep_"):
        sub_id = int(callback_data.split("_")[1])
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute("SELECT s.user_id, s.name, sub.submission_type FROM submissions sub JOIN students s ON sub.user_id = s.user_id WHERE sub.submission_id=?", (sub_id,))
        row = c.fetchone()
        conn.close()
        if row:
            waiting_for_reply[query.from_user.id] = {"student_id": row[0], "student_name": row[1], "submission_id": sub_id, "submission_type": row[2], "type": "text"}
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("نصي ✍️", callback_data=f"st_text_{sub_id}"), InlineKeyboardButton("صوتي 🎙️", callback_data=f"st_voice_{sub_id}")]])
            await context.bot.send_message(chat_id=GROUP_ID, text=f"الرد على {row[1]}: اختر النوع ثم أرسل ردك.", reply_markup=markup)

    elif callback_data.startswith("st_"):
        parts = callback_data.split("_")
        waiting_for_reply[query.from_user.id]["type"] = parts[1]
        await query.edit_message_text(f"الآن أرسل الرد {'النصي' if parts[1] == 'text' else 'الصوتي'}:")

async def report_command(update: Update, context):
    if update.effective_chat.id != GROUP_ID: return
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    today = datetime.now(MECCA_TIMEZONE).strftime('%Y-%m-%d')
    c.execute("SELECT s.name, sub.submission_type FROM submissions sub JOIN students s ON sub.user_id = s.user_id WHERE DATE(sub.timestamp) = ?", (today,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("لا توجد بيانات لليوم.")
        return
    report = f"📊 إحصائية اليوم ({today}):\n"
    stats = {}
    for name, stype in rows:
        if name not in stats: stats[name] = {}
        stats[name][stype] = stats[name].get(stype, 0) + 1
    for i, (name, s) in enumerate(stats.items(), 1):
        details = [f"{k}{f': {v}' if v > 1 else ''}" for k, v in s.items()]
        report += f"{i}. {name} ({', '.join(details)})\n"
    await update.message.reply_text(report)

def main():
    init_db()
    keep_alive()
    time.sleep(10)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_text))
    app.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE, handle_voice))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(GROUP_ID), handle_text))
    app.add_handler(MessageHandler(filters.VOICE & filters.Chat(GROUP_ID), handle_voice))
    while True:
        try:
            app.run_polling(drop_pending_updates=True, close_loop=False)
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__": main()
