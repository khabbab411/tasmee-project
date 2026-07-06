import logging
import os
import time
import asyncio
from datetime import datetime
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from keep_alive import keep_alive
from database import get_connection, init_database

# 1. إعداد السجلات
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. إعدادات المنطقة الزمنية ---
MECCA_TIMEZONE = pytz.timezone('Asia/Riyadh')

# --- 3. الإعدادات ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8871655491:AAEWD5WQxJUeBBngKxe8u2OJonKcVsQo4sg")
GROUP_ID = int(os.environ.get("TEACHERS_GROUP_ID", "-1004344713055"))

waiting_for_reply = {}
pending_user_actions = {}

# --- 4. دوال قاعدة البيانات (PostgreSQL) ---

def save_user(user_id, name, state):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO students (user_id, name, state) 
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET name = %s, state = %s
    """, (user_id, name, state, name, state))
    conn.commit()
    cur.close()
    conn.close()

def get_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, state FROM students WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {"name": row["name"], "state": row["state"]}
    return None

def update_user_state(user_id, state):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE students SET state = %s WHERE user_id = %s", (state, user_id))
    conn.commit()
    cur.close()
    conn.close()

# --- 5. لوحات المفاتيح الثابتة (Reply Keyboard) ---

def get_main_menu_keyboard():
    keyboard = [[KeyboardButton("🎤 إرسال تسميع"), KeyboardButton("❓ سؤال المعلم")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_submission_type_keyboard():
    keyboard = [[KeyboardButton("📖 ورد الحفظ"), KeyboardButton("🔄 ورد المراجعة")], [KeyboardButton("🔙 رجوع للقائمة الرئيسية")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_question_type_keyboard():
    keyboard = [[KeyboardButton("🎙️ سؤال صوتي"), KeyboardButton("✍️ سؤال نصي")], [KeyboardButton("🔙 رجوع للقائمة الرئيسية")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- 6. معالجات البوت ---

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
            pending_user_actions[user_id] = {"type": "question", "subtype": "سؤال_نصي", "text_content": text, "file_id": None, "original_message_id": update.message.message_id}
            await update.message.reply_text("وصلني سؤالك النصي، هل تودين إرساله?", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ إرسال", callback_data="confirm_send")], [InlineKeyboardButton("❌ إلغاء", callback_data="confirm_resend")]]))
            update_user_state(user_id, "awaiting_confirmation")

    elif chat_id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply:
            data = waiting_for_reply[teacher_id]
            if data["type"] == "text":
                await context.bot.send_message(chat_id=data["student_id"], text=f"💌 وصلك رد من المعلمة بخصوص: [{data['submission_type']}]\n\n{text}")
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("UPDATE submissions SET status='replied', teacher_reply_type='text', teacher_reply_content=%s WHERE submission_id=%s", (text, data["submission_id"]))
                conn.commit()
                cur.close()
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
            pending_user_actions[user_id] = {"type": "submission" if "submission" in user["state"] else "question", "subtype": sub_type, "file_id": update.message.voice.file_id, "text_content": None, "original_message_id": update.message.message_id}
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
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("UPDATE submissions SET status='replied', teacher_reply_type='voice', teacher_reply_content=%s WHERE submission_id=%s", (update.message.voice.file_id, data["submission_id"]))
                conn.commit()
                cur.close()
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
            conn = get_connection()
            cur = conn.cursor()
            timestamp = datetime.now(MECCA_TIMEZONE).isoformat()
            cur.execute("""
                INSERT INTO submissions 
                (user_id, submission_type, file_id, text_content, timestamp, status, original_message_id) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING submission_id
            """, (user_id, action["subtype"], action["file_id"], action["text_content"], timestamp, 'pending', action["original_message_id"]))
            sub_id = cur.fetchone()["submission_id"]
            conn.commit()
            cur.close()
            conn.close()
            
            title = "🎤 تسميع جديد" if action['type'] == 'submission' else "❓ سؤال جديد"
            caption = f"{title} - {action['subtype']}\nالطالبة: {user['name']}"
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("رد نصي ✍️", callback_data=f"r_t_{sub_id}"), InlineKeyboardButton("رد صوتي 🎙️", callback_data=f"r_v_{sub_id}")]])
            
            if action["file_id"]:
                await context.bot.send_voice(chat_id=GROUP_ID, voice=action["file_id"], caption=caption, reply_markup=markup)
            else:
                await context.bot.send_message(chat_id=GROUP_ID, text=f"{caption}\n\n{action['text_content']}", reply_markup=markup)
            
            await query.edit_message_text("✅ تم الإرسال للمعلمة بنجاح.")
            update_user_state(user_id, "main_menu")

    elif callback_data == "confirm_resend":
        user_id = query.from_user.id
        pending_user_actions.pop(user_id, None)
        await query.edit_message_text("تم إلغاء الإرسال.")
        update_user_state(user_id, "main_menu")

    elif callback_data.startswith("r_"):
        parts = callback_data.split("_")
        sub_id = int(parts[2])
        r_type = "text" if parts[1] == "t" else "voice"
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.user_id, s.name, sub.submission_type 
            FROM submissions sub JOIN students s ON sub.user_id = s.user_id 
            WHERE sub.submission_id = %s
        """, (sub_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            waiting_for_reply[query.from_user.id] = {"student_id": row["user_id"], "student_name": row["name"], "submission_id": sub_id, "submission_type": row["submission_type"], "type": r_type}
            msg = f"⏳ بانتظار الرد {'النصي' if r_type == 'text' else 'الصوتي'} لـ {row['name']}..."
            if query.message.voice:
                await query.edit_message_caption(caption=f"{query.message.caption}\n\n{msg}")
            else:
                await query.edit_message_text(text=f"{query.message.text}\n\n{msg}")

async def report_command(update: Update, context):
    if update.effective_chat.id != GROUP_ID: return
    conn = get_connection()
    cur = conn.cursor()
    today_prefix = datetime.now(MECCA_TIMEZONE).strftime('%Y-%m-%d')
    cur.execute("""
        SELECT s.name, sub.submission_type 
        FROM submissions sub JOIN students s ON sub.user_id = s.user_id 
        WHERE sub.timestamp LIKE %s
    """, (f"{today_prefix}%",))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    if not rows:
        await update.message.reply_text(f"لا توجد إحصائيات لليوم ({today_prefix}).")
        return
        
    stats = {}
    total_submissions = 0
    for row in rows:
        total_submissions += 1
        name = row["name"]
        stype = row["submission_type"]
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
    init_database()
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
            app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__": main()
