import logging
import os
import time
import sqlite3
from datetime import datetime
import pytz # لإدارة التوقيتات

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from keep_alive import keep_alive

# 1. إعداد السجلات (Logs)
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. إعداد قاعدة البيانات (SQLite) ---
DATABASE_NAME = 'users.db'
MECCA_TIMEZONE = pytz.timezone('Asia/Riyadh') # توقيت مكة المكرمة

def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    
    # جدول الطلاب (يحتوي على حالة الطالب الحالية)
    c.execute('PRAGMA foreign_keys = ON')
    c.execute('CREATE TABLE IF NOT EXISTS students
                 (user_id INTEGER PRIMARY KEY, name TEXT, state TEXT, last_submission_date TEXT)')
    
    # جدول التسميعات والأسئلة
    c.execute('CREATE TABLE IF NOT EXISTS submissions
                 (submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  submission_type TEXT, -- حفظ, مراجعة, سؤال_صوتي, سؤال_نصي
                  file_id TEXT, -- لملفات الصوت
                  text_content TEXT, -- للنصوص
                  timestamp TEXT, -- تاريخ ووقت الإرسال
                  status TEXT, -- pending, replied
                  teacher_reply_type TEXT, -- text, voice
                  teacher_reply_content TEXT, -- file_id or text
                  original_message_id INTEGER, -- ID الرسالة الأصلية للطالبة
                  group_message_id INTEGER, -- ID الرسالة في مجموعة المعلمات
                  FOREIGN KEY (user_id) REFERENCES students(user_id))')
    
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

def update_last_submission_date(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    today_mecca = datetime.now(MECCA_TIMEZONE).strftime('%Y-%m-%d')
    c.execute("UPDATE students SET last_submission_date=? WHERE user_id=?", (today_mecca, user_id))
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

def update_submission_group_message_id(submission_id, group_message_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("UPDATE submissions SET group_message_id=? WHERE submission_id=?", (group_message_id, submission_id))
    conn.commit()
    conn.close()

def get_pending_submission(submission_id):
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, submission_type, file_id, text_content, original_message_id FROM submissions WHERE submission_id=? AND status='pending'", (submission_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "submission_type": row[1], "file_id": row[2], "text_content": row[3], "original_message_id": row[4]}
    return None

def get_todays_submissions_for_report():
    conn = sqlite3.connect(DATABASE_NAME)
    c = conn.cursor()
    today_mecca = datetime.now(MECCA_TIMEZONE).strftime('%Y-%m-%d')
    c.execute("SELECT s.name, sub.submission_type FROM submissions sub JOIN students s ON sub.user_id = s.user_id WHERE DATE(sub.timestamp) = ?", (today_mecca,))
    rows = c.fetchall()
    conn.close()
    return rows

# --- 3. الإعدادات ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8871655491:AAEWD5WQxJUeBBngKxe8u2OJonKcVsQo4sg")
GROUP_ID = int(os.environ.get("TEACHERS_GROUP_ID", "-1004344713055"))

# مخزن مؤقت لانتظار الرد (لا يحتاج قاعدة بيانات لأنه لحظي)
waiting_for_reply = {} # {teacher_id: {"student_id": xxx, "student_name": xxx, "submission_id": xxx, "type": "text/voice"}}

# مخزن مؤقت للتسميعات/الأسئلة التي تنتظر تأكيد الطالبة
# {user_id: {"type": "submission/question", "subtype": "حفظ/مراجعة/سؤال_صوتي/سؤال_نصي", "file_id": "xxx", "text_content": "xxx", "original_message_id": xxx}}
pending_user_actions = {}

# --- 4. الدوال المساعدة ---
def is_valid_name(name: str) -> bool:
    name = name.strip()
    return len(name) >= 5 and len(name.split()) >= 2

# --- 5. لوحات المفاتيح (Keyboards) ---
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎤 إرسال تسميع", callback_data="menu_submit")],
        [InlineKeyboardButton("❓ سؤال المعلم", callback_data="menu_question")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_submission_type_keyboard():
    keyboard = [
        [InlineKeyboardButton("📖 ورد الحفظ", callback_data="submit_type_hifz")],
        [InlineKeyboardButton("🔄 ورد المراجعة", callback_data="submit_type_murajaah")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_question_type_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎙️ سؤال صوتي", callback_data="question_type_voice")],
        [InlineKeyboardButton("✍️ سؤال نصي", callback_data="question_type_text")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirm_submission_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ إرسال للمعلمة", callback_data="confirm_send")],
        [InlineKeyboardButton("❌ إعادة التسجيل", callback_data="confirm_resend")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- 6. معالجات البوت ---
async def start(update: Update, context):
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        user = get_user(user_id)
        if user and user['name']:
            # إذا كان مسجلاً، نرسل له القائمة الرئيسية مباشرة
            await update.message.reply_text(f"أهلاً بك مجدداً يا {user['name']}!", reply_markup=get_main_menu_keyboard())
            update_user_state(user_id, "main_menu")
        else:
            # إذا لم يكن مسجلاً، نطلب الاسم
            save_user(user_id, "", "awaiting_name")
            await update.message.reply_text("أهلاً بك! الرجاء إدخال اسمك الكامل (ثلاثي) للبدء.")

async def handle_text(update: Update, context):
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    text = update.message.text
    user = get_user(user_id)

    if chat_type == "private":
        if user and user.get("state") == "awaiting_name":
            if is_valid_name(text):
                save_user(user_id, text, "main_menu")
                await update.message.reply_text(f"تم حفظ اسمك يا {text}.", reply_markup=get_main_menu_keyboard())
            else:
                await update.message.reply_text("الاسم قصير جداً، يرجى إرسال اسمك الثلاثي.")
        elif user and user.get("state") == "awaiting_text_question":
            pending_user_actions[user_id] = {
                "type": "question",
                "subtype": "سؤال_نصي",
                "text_content": text,
                "original_message_id": update.message.message_id
            }
            await update.message.reply_text("وصلني سؤالك النصي، هل أنت متأكد من الإرسال؟", reply_markup=get_confirm_submission_keyboard())
            update_user_state(user_id, "awaiting_confirmation")
        else:
            # إذا أرسل نصاً وهو في حالة غير متوقعة، نعيده للقائمة الرئيسية
            await update.message.reply_text("أمر غير مفهوم. الرجاء استخدام الأزرار.", reply_markup=get_main_menu_keyboard())
            update_user_state(user_id, "main_menu")
    
    elif chat_type == "group" and update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply and waiting_for_reply[teacher_id]["type"] == "text":
            student_id = waiting_for_reply[teacher_id]["student_id"]
            submission_id = waiting_for_reply[teacher_id]["submission_id"]
            submission_type = waiting_for_reply[teacher_id]["submission_type"]
            student_name = waiting_for_reply[teacher_id]["student_name"]

            # إرسال الرد للطالبة
            await context.bot.send_message(chat_id=student_id, text=f"💌 وصلك رد من المعلمة بخصوص: [{submission_type}]\n\n{text}")
            
            # تحديث حالة التسميع في قاعدة البيانات
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute("UPDATE submissions SET status='replied', teacher_reply_type='text', teacher_reply_content=? WHERE submission_id=?", (text, submission_id))
            conn.commit()
            conn.close()

            await update.message.reply_text(f"✅ تم إرسال الرد النصي إلى {student_name}")
            del waiting_for_reply[teacher_id]

async def handle_voice(update: Update, context):
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    user = get_user(user_id)

    if chat_type == "private":
        if user and user.get("state") in ["awaiting_hifz_submission", "awaiting_murajaah_submission", "awaiting_voice_question"]:
            submission_type = "حفظ" if user["state"] == "awaiting_hifz_submission" else \
                              "مراجعة" if user["state"] == "awaiting_murajaah_submission" else \
                              "سؤال_صوتي"
            
            pending_user_actions[user_id] = {
                "type": "submission" if "submission" in user["state"] else "question",
                "subtype": submission_type,
                "file_id": update.message.voice.file_id,
                "original_message_id": update.message.message_id
            }
            await update.message.reply_text("وصلني تسجيلك، يمكنك الاستماع إليه بالأعلى للتأكد.", reply_markup=get_confirm_submission_keyboard())
            update_user_state(user_id, "awaiting_confirmation")
        else:
            await update.message.reply_text("أمر غير مفهوم. الرجاء استخدام الأزرار.", reply_markup=get_main_menu_keyboard())
            update_user_state(user_id, "main_menu")
    
    elif chat_type == "group" and update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply and waiting_for_reply[teacher_id]["type"] == "voice":
            student_id = waiting_for_reply[teacher_id]["student_id"]
            submission_id = waiting_for_reply[teacher_id]["submission_id"]
            submission_type = waiting_for_reply[teacher_id]["submission_type"]
            student_name = waiting_for_reply[teacher_id]["student_name"]

            # إرسال الرد للطالبة
            await context.bot.send_voice(chat_id=student_id, voice=update.message.voice.file_id)
            await context.bot.send_message(chat_id=student_id, text=f"💌 وصلك رد صوتي من المعلمة بخصوص: [{submission_type}]")

            # تحديث حالة التسميع في قاعدة البيانات
            conn = sqlite3.connect(DATABASE_NAME)
            c = conn.cursor()
            c.execute("UPDATE submissions SET status='replied', teacher_reply_type='voice', teacher_reply_content=? WHERE submission_id=?", (update.message.voice.file_id, submission_id))
            conn.commit()
            conn.close()

            await update.message.reply_text(f"✅ تم إرسال الرد الصوتي إلى {student_name}")
            del waiting_for_reply[teacher_id]

async def handle_callback(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user(user_id)
    callback_data = query.data

    await query.answer() # يجب الرد على الكولباك كويري

    if not user: # لو المستخدم غير مسجل
        await query.edit_message_text("الرجاء إرسال /start أولاً للبدء.")
        return

    current_state = user.get("state")

    if callback_data == "menu_submit":
        await query.edit_message_text("الرجاء اختيار نوع التسميع:", reply_markup=get_submission_type_keyboard())
        update_user_state(user_id, "awaiting_submission_type")
    elif callback_data == "menu_question":
        await query.edit_message_text("الرجاء اختيار نوع السؤال:", reply_markup=get_question_type_keyboard())
        update_user_state(user_id, "awaiting_question_type")
    elif callback_data == "back_to_main_menu":
        pending_user_actions.pop(user_id, None) # مسح أي إجراء معلق
        await query.edit_message_text("أهلاً بك مجدداً في القائمة الرئيسية.", reply_markup=get_main_menu_keyboard())
        update_user_state(user_id, "main_menu")
    
    # أنواع التسميع
    elif callback_data == "submit_type_hifz":
        await query.edit_message_text("ممتاز! الرجاء تسجيل ورد الحفظ الآن.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_to_main_menu")]]))
        update_user_state(user_id, "awaiting_hifz_submission")
    elif callback_data == "submit_type_murajaah":
        await query.edit_message_text("ممتاز! الرجاء تسجيل ورد المراجعة الآن.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_to_main_menu")]]))
        update_user_state(user_id, "awaiting_murajaah_submission")
    
    # أنواع الأسئلة
    elif callback_data == "question_type_voice":
        await query.edit_message_text("الرجاء تسجيل سؤالك الصوتي الآن.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_to_main_menu")]]))
        update_user_state(user_id, "awaiting_voice_question")
    elif callback_data == "question_type_text":
        await query.edit_message_text("الرجاء كتابة سؤالك النصي الآن.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_to_main_menu")]]))
        update_user_state(user_id, "awaiting_text_question")

    # تأكيد الإرسال أو إعادة التسجيل
    elif callback_data == "confirm_send":
        if user_id in pending_user_actions and current_state == "awaiting_confirmation":
            action_data = pending_user_actions.pop(user_id)
            submission_type = action_data["subtype"]
            student_name = user["name"]

            caption_prefix = "🎤 تسميع جديد" if action_data["type"] == "submission" else "❓ سؤال جديد"
            caption_emoji = "📖" if submission_type == "حفظ" else "🔄" if submission_type == "مراجعة" else "🎙️" if submission_type == "سؤال_صوتي" else "✍️"
            caption_text = f"{caption_prefix} {caption_emoji} - {submission_type}: {student_name}\nID: {user_id}"

            message_to_group = None
            if action_data["file_id"]:
                message_to_group = await context.bot.send_voice(chat_id=GROUP_ID, voice=action_data["file_id"], caption=caption_text)
            elif action_data["text_content"]:
                message_to_group = await context.bot.send_message(chat_id=GROUP_ID, text=f"{caption_text}\n\n{action_data['text_content']}")
            
            if message_to_group:
                submission_id = save_submission(user_id, submission_type, action_data.get("file_id"), action_data.get("text_content"), action_data["original_message_id"])
                update_submission_group_message_id(submission_id, message_to_group.message_id)
                update_last_submission_date(user_id)
                await query.edit_message_text("✅ تم إرسال طلبك للمعلمات.", reply_markup=get_main_menu_keyboard())
                update_user_state(user_id, "main_menu")
            else:
                await query.edit_message_text("حدث خطأ أثناء الإرسال، الرجاء المحاولة مرة أخرى.", reply_markup=get_main_menu_keyboard())
                update_user_state(user_id, "main_menu")
        else:
            await query.edit_message_text("لا يوجد طلب معلق للإرسال.", reply_markup=get_main_menu_keyboard())
            update_user_state(user_id, "main_menu")

    elif callback_data == "confirm_resend":
        if user_id in pending_user_actions and current_state == "awaiting_confirmation":
            action_data = pending_user_actions.pop(user_id)
            if action_data["type"] == "submission":
                if action_data["subtype"] == "حفظ":
                    await query.edit_message_text("تم إلغاء التسجيل. الرجاء تسجيل ورد الحفظ الآن.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_to_main_menu")]]))
                    update_user_state(user_id, "awaiting_hifz_submission")
                elif action_data["subtype"] == "مراجعة":
                    await query.edit_message_text("تم إلغاء التسجيل. الرجاء تسجيل ورد المراجعة الآن.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_to_main_menu")]]))
                    update_user_state(user_id, "awaiting_murajaah_submission")
            elif action_data["type"] == "question":
                if action_data["subtype"] == "سؤال_صوتي":
                    await query.edit_message_text("تم إلغاء السؤال. الرجاء تسجيل سؤالك الصوتي الآن.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_to_main_menu")]]))
                    update_user_state(user_id, "awaiting_voice_question")
                elif action_data["subtype"] == "سؤال_نصي":
                    await query.edit_message_text("تم إلغاء السؤال. الرجاء كتابة سؤالك النصي الآن.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_to_main_menu")]]))
                    update_user_state(user_id, "awaiting_text_question")
        else:
            await query.edit_message_text("لا يوجد طلب معلق لإعادة التسجيل.", reply_markup=get_main_menu_keyboard())
            update_user_state(user_id, "main_menu")

    # معالج أمر /report للمعلمات
async def report_command(update: Update, context):
    user_id = update.effective_user.id
    if user_id != GROUP_ID: # يمكن تعديل هذا الشرط ليشمل معرفات معلمات محددة
        await update.message.reply_text("عذراً، هذا الأمر مخصص للمعلمات فقط.")
        return
    
    submissions_data = get_todays_submissions_for_report()
    
    if not submissions_data:
        await update.message.reply_text("لا توجد تسميعات أو أسئلة اليوم حتى الآن.")
        return
    
    report_text = f"📊 إحصائية حلقة اليوم ({datetime.now(MECCA_TIMEZONE).strftime('%Y-%m-%d')})\n\n"
    
    total_submissions = len(submissions_data)
    unique_students = set()
    hifz_count = 0
    murajaah_count = 0
    voice_question_count = 0
    text_question_count = 0
    
    student_submissions = {}

    for name, sub_type in submissions_data:
        unique_students.add(name)
        if sub_type == "حفظ":
            hifz_count += 1
        elif sub_type == "مراجعة":
            murajaah_count += 1
        elif sub_type == "سؤال_صوتي":
            voice_question_count += 1
        elif sub_type == "سؤال_نصي":
            text_question_count += 1
        
        if name not in student_submissions:
            student_submissions[name] = {"حفظ": 0, "مراجعة": 0, "سؤال_صوتي": 0, "سؤال_نصي": 0}
        student_submissions[name][sub_type] += 1

    report_text += f"✅ إجمالي التفاعلات: {total_submissions}\n"
    report_text += f"👥 عدد الطالبات المشاركات: {len(unique_students)}\n\n"
    report_text += f"📖 ورد الحفظ: {hifz_count}\n"
    report_text += f"🔄 ورد المراجعة: {murajaah_count}\n"
    report_text += f"🎙️ أسئلة صوتية: {voice_question_count}\n"
    report_text += f"✍️ أسئلة نصية: {text_question_count}\n\n"
    report_text += "**قائمة الطالبات وتفاعلاتهن:**\n"

    for i, (name, subs) in enumerate(student_submissions.items(), 1):
        details = []
        if subs["حفظ"] > 0:
            details.append(f"حفظ: {subs['حفظ']}" if subs["حفظ"] > 1 else "حفظ")
        if subs["مراجعة"] > 0:
            details.append(f"مراجعة: {subs['مراجعة']}" if subs["مراجعة"] > 1 else "مراجعة")
        if subs["سؤال_صوتي"] > 0:
            details.append(f"سؤال صوتي: {subs['سؤال_صوتي']}" if subs["سؤال_صوتي"] > 1 else "سؤال صوتي")
        if subs["سؤال_نصي"] > 0:
            details.append(f"سؤال نصي: {subs['سؤال_نصي']}" if subs["سؤال_نصي"] > 1 else "سؤال نصي")
        
        report_text += f"{i}. {name} ({', '.join(details)})\n"

    await update.message.reply_text(report_text)

# --- 7. تشغيل البوت مع نظام الحماية ---
def main():
    init_db() # تهيئة قاعدة البيانات
    keep_alive() # تشغيل سيرفر الاستيقاظ
    
    print("⏳ جاري الانتظار 10 ثوانٍ لضمان استقرار الاتصال...")
    time.sleep(10)
    
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", report_command)) # أمر الإحصائيات
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_text))
    application.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE, handle_voice))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # معالجة الرسائل في المجموعة (للمعلمات)
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
