import logging
import os
import time
import sqlite3
import asyncio
from datetime import datetime
import pytz

import requests as http_requests
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

# --- 3. الإعدادات ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8871655491:AAEWD5WQxJUeBBngKxe8u2OJonKcVsQo4sg")
GROUP_ID = int(os.environ.get("TEACHERS_GROUP_ID", "-1004344713055"))
# رابط لوحة الويب ومفتاح API للربط
WEB_DASHBOARD_URL = os.environ.get("WEB_DASHBOARD_URL", "")
BOT_API_KEY = os.environ.get("BOT_API_KEY", "quran-circle-bot-key-2024")

waiting_for_reply = {}
pending_user_actions = {}

# --- دالة إرسال التسميع إلى لوحة الويب ---
def push_to_web_dashboard(student_telegram_id, student_name, submission_type, file_id=None, text_content=None, duration=None):
    """إرسال التسميع الجديد إلى لوحة الويب عبر API"""
    if not WEB_DASHBOARD_URL:
        logger.info("[Web Dashboard] URL not configured, skipping push.")
        return
    try:
        # تحويل نوع التسميع للصيغة المتوافقة مع لوحة الويب
        type_map = {
            "حفظ": "hifz",
            "مراجعة": "murajaah",
            "سؤال_صوتي": "question_voice",
            "سؤال_نصي": "question_text",
        }
        web_type = type_map.get(submission_type, "hifz")
        
        payload = {
            "studentTelegramId": student_telegram_id,
            "studentName": student_name,
            "submissionType": web_type,
            "fileId": file_id,
            "textContent": text_content,
            "duration": duration,
            "apiKey": BOT_API_KEY,
        }
        resp = http_requests.post(f"{WEB_DASHBOARD_URL}/api/bot/submission", json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info(f"[Web Dashboard] Submission pushed successfully for {student_name}")
        else:
            logger.warning(f"[Web Dashboard] Push failed: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.error(f"[Web Dashboard] Error pushing submission: {e}")

# --- 4. لوحات المفاتيح الثابتة (Reply Keyboard) ---
def get_main_menu_keyboard():
    keyboard = [[KeyboardButton("🎤 إرسال تسميع"), KeyboardButton("❓ سؤال المعلم")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_submission_type_keyboard():
    keyboard = [[KeyboardButton("📖 ورد الحفظ"), KeyboardButton("🔄 ورد المراجعة")], [KeyboardButton("🔙 رجوع للقائمة الرئيسية")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_question_type_keyboard():
    keyboard = [[KeyboardButton("🎙️ سؤال صوتي"), KeyboardButton("✍️ سؤال نصي")], [KeyboardButton("🔙 رجوع للقائمة الرئيسية")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- 5. معالجات البوت ---
async def start(update: Update, context):
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        user = get_user(user_id)
        if user and user['name']:
            await update.message.reply_text(f"أهلاً بك مجدداً يا {user['name']}! 👋", reply_markup=get_main_menu_keyboard())
            update_user_state(user_id, "main_menu")
        else:
            save_user(user_id, "", "awaiting_name")
            await update.message.reply_text("أهلاً بك في حلقة القرآن! 🌸\nالرجاء إدخال اسمك الكامل (ثلاثي) للبدء.", reply_markup=ReplyKeyboardRemove())

async def handle_text(update: Update, context):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    text = update.message.text
    user = get_user(user_id)

    if chat_type == "private":
        if user and user.get("state") == "awaiting_name":
            if len(text.strip().split()) >= 2:
                save_user(user_id, text, "main_menu")
                await update.message.reply_text(f"تم تسجيلك بنجاح يا {text}.", reply_markup=get_main_menu_keyboard())
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
            await update.message.reply_text("تمت العودة للقائمة الرئيسية.", reply_markup=get_main_menu_keyboard())
            update_user_state(user_id, "main_menu")
        elif text == "📖 ورد الحفظ":
            await update.message.reply_text("بانتظار تسجيل ورد الحفظ الآن. 📖", reply_markup=get_submission_type_keyboard())
            update_user_state(user_id, "awaiting_hifz_submission")
        elif text == "🔄 ورد المراجعة":
            await update.message.reply_text("بانتظار تسجيل ورد المراجعة الآن. 🔄", reply_markup=get_submission_type_keyboard())
            update_user_state(user_id, "awaiting_murajaah_submission")
        elif text == "🎙️ سؤال صوتي":
            await update.message.reply_text("الرجاء تسجيل سؤالك الصوتي الآن. 🎙️", reply_markup=get_question_type_keyboard())
            update_user_state(user_id, "awaiting_voice_question")
        elif text == "✍️ سؤال نصي":
            await update.message.reply_text("الرجاء كتابة سؤالك النصي الآن. ✍️", reply_markup=get_question_type_keyboard())
            update_user_state(user_id, "awaiting_text_question")
        elif user and user.get("state") == "awaiting_text_question":
            pending_user_actions[user_id] = {"type": "question", "subtype": "سؤال_نصي", "text_content": text, "file_id": None, "original_message_id": update.message.message_id, "duration": None}
            await update.message.reply_text("وصلني سؤالك النصي، هل تودين إرساله؟", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ إرسال", callback_data="confirm_send")], [InlineKeyboardButton("❌ إلغاء", callback_data="confirm_resend")]]))
            update_user_state(user_id, "awaiting_confirmation")

    elif chat_id == GROUP_ID:
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
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    user = get_user(user_id)

    if chat_type == "private":
        if user and user.get("state") in ["awaiting_hifz_submission", "awaiting_murajaah_submission", "awaiting_voice_question"]:
            sub_type = "حفظ" if user["state"] == "awaiting_hifz_submission" else "مراجعة" if user["state"] == "awaiting_murajaah_submission" else "سؤال_صوتي"
            voice_duration = update.message.voice.duration if update.message.voice else None
            pending_user_actions[user_id] = {"type": "submission" if "submission" in user["state"] else "question", "subtype": sub_type, "file_id": update.message.voice.file_id, "text_content": None, "original_message_id": update.message.message_id, "duration": voice_duration}
            await update.message.reply_text("وصلني تسجيلك، يمكنك المعاينة قبل الإرسال.", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ إرسال للمعلمة", callback_data="confirm_send")], [InlineKeyboardButton("❌ إعادة التسجيل", callback_data="confirm_resend")]]))
            update_user_state(user_id, "awaiting_confirmation")

    elif chat_id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply:
            data = waiting_for_reply[teacher_id]
            if data["type"] == "voice":
                caption = f"💌 وصلك رد صوتي من المعلمة بخصوص: [{data['submission_type']}]"
                await context.bot.send_voice(chat_id=data["student_id"], voice=update.message.voice.file_id, caption=caption)
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
            # حفظ الوقت بصيغة ISO وتاريخ اليوم بشكل منفصل لسهولة الإحصاء
            timestamp = datetime.now(MECCA_TIMEZONE).isoformat()
            c.execute("INSERT INTO submissions (user_id, submission_type, file_id, text_content, timestamp, status, original_message_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (user_id, action["subtype"], action["file_id"], action["text_content"], timestamp, 'pending', action["original_message_id"]))
            sub_id = c.lastrowid
            conn.commit()
            conn.close()
            
            title = "🎤 تسميع جديد" if action['type'] == 'submission' else "❓ سؤال جديد"
            # إزالة الـ ID من الكابشن كما طلب المستخدم
            caption = f"{title} - {action['subtype']}\nالطالبة: {user['name']}"
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("رد نصي ✍️", callback_data=f"r_t_{sub_id}"), InlineKeyboardButton("رد صوتي 🎙️", callback_data=f"r_v_{sub_id}")]])
            
            if action["file_id"]:
                await context.bot.send_voice(chat_id=GROUP_ID, voice=action["file_id"], caption=caption, reply_markup=markup)
            else:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"{caption}\n\n{action['text_content']}", reply_markup=markup)
            
            await query.edit_message_text("✅ تم الإرسال للمعلمة بنجاح.")
            update_user_state(user_id, "main_menu")
            
            # إرسال التسميع إلى لوحة الويب أيضاً
            push_to_web_dashboard(
                student_telegram_id=user_id,
                student_name=user['name'],
                submission_type=action['subtype'],
                file_id=action['file_id'],
                text_content=action['text_content'],
                duration=action.get('duration')
            )

    elif callback_data == "confirm_resend":
        user_id = query.from_user.id
        pending_user_actions.pop(user_id, None)
        await query.edit_message_text("تم إلغاء الإرسال.")
        update_user_state(user_id, "main_menu")

    elif callback_data.startswith("r_"):
        parts = callback_data.split("_")
        sub_id = int(parts[2])
        r_type = "text" if parts[1] == "t" else "voice"
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute("SELECT s.user_id, s.name, sub.submission_type FROM submissions sub JOIN students s ON sub.user_id = s.user_id WHERE sub.submission_id=?", (sub_id,))
        row = c.fetchone()
        conn.close()
        if row:
            waiting_for_reply[query.from_user.id] = {"student_id": row[0], "student_name": row[1], "submission_id": sub_id, "submission_type": row[2], "type": r_type}
            msg = f"⏳ بانتظار الرد {'النصي' if r_type == 'text' else 'الصوتي'} لـ {row[1]}..."
            if query.message.voice:
                await query.edit_message_caption(caption=f"{query.message.caption}\n\n{msg}")
            else:
                await query.edit_message_text(text=f"{query.message.text}\n\n{msg}")

async def report_command(update: Update, context):
    if update.effective_chat.id != GROUP_ID: return
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    # جلب إحصائيات اليوم بتوقيت مكة المكرمة
    today_prefix = datetime.now(MECCA_TIMEZONE).strftime('%Y-%m-%d')
    c.execute("SELECT s.name, sub.submission_type FROM submissions sub JOIN students s ON sub.user_id = s.user_id WHERE sub.timestamp LIKE ?", (f"{today_prefix}%",))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await update.message.reply_text(f"لا توجد إحصائيات لليوم ({today_prefix}).")
        return
        
    stats = {}
    total_submissions = 0
    for name, stype in rows:
        total_submissions += 1
        if name not in stats: stats[name] = {}
        stats[name][stype] = stats[name].get(stype, 0) + 1
    
    report = f"📊 إحصائية حلقة اليوم ({today_prefix}):\n"
    report += f"✅ إجمالي التفاعلات: {total_submissions}\n"
    report += f"👥 عدد الطالبات: {len(stats)}\n\n"
    
    for i, (name, s) in enumerate(stats.items(), 1):
        details = [f"{k}{f': {v}' if v > 1 else ''}" for k, v in s.items()]
        report += f"{i}. {name} ({', '.join(details)})\n"
    await update.message.reply_text(report)

def main():
    init_db()
    keep_alive()
    time.sleep(20)
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
