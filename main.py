import logging
import os
import uuid
from pathlib import Path
from datetime import datetime
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from keep_alive import keep_alive
from database import (
    init_database, 
    get_user, 
    save_user, 
    update_user_state,
    save_submission,
    update_submission_reply,
    get_submission,
    get_today_report
)

# إعداد السجلات
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# إعدادات المنطقة الزمنية
MECCA_TIMEZONE = pytz.timezone('Asia/Riyadh')

# متغيرات البيئة
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GROUP_ID = int(os.environ.get("TEACHERS_GROUP_ID", "-1004344713055"))

# مجلد حفظ الملفات الصوتية
VOICE_FOLDER = Path("data/voices")
VOICE_FOLDER.mkdir(parents=True, exist_ok=True)

# تخزين مؤقت
waiting_for_reply = {}
pending_user_actions = {}

# ========== دوال لوحات المفاتيح ==========

def get_main_menu_keyboard():
    keyboard = [[KeyboardButton("🎤 إرسال تسميع"), KeyboardButton("❓ سؤال المعلم")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_submission_type_keyboard():
    keyboard = [[KeyboardButton("📖 ورد الحفظ"), KeyboardButton("🔄 ورد المراجعة")], [KeyboardButton("🔙 رجوع للقائمة الرئيسية")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_question_type_keyboard():
    keyboard = [[KeyboardButton("🎙️ سؤال صوتي"), KeyboardButton("✍️ سؤال نصي")], [KeyboardButton("🔙 رجوع للقائمة الرئيسية")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ========== دوال مساعدة ==========

async def save_voice_file(bot, file_id):
    telegram_file = await bot.get_file(file_id)
    filename = f"{uuid.uuid4()}.ogg"
    filepath = VOICE_FOLDER / filename
    await telegram_file.download_to_drive(str(filepath))
    return filename

async def send_teacher_reply(context, student_id, submission_id, submission_type, student_name, reply_type, reply_content):
    """إرسال رد المعلم للطالب وتحديث قاعدة البيانات"""
    try:
        if reply_type == "text":
            await context.bot.send_message(
                chat_id=student_id,
                text=f"💌 وصلك رد من المعلمة بخصوص: [{submission_type}]\n\n{reply_content}"
            )
        else:  # voice
            caption = f"💌 وصلك رد صوتي من المعلمة بخصوص: [{submission_type}]"
            await context.bot.send_voice(
                chat_id=student_id,
                voice=reply_content,
                caption=caption
            )
        
        update_submission_reply(submission_id, reply_type, reply_content)
        logger.info(f"تم إرسال رد {reply_type} للطالب {student_name}")
        return True
    except Exception as e:
        logger.exception(f"فشل إرسال الرد للطالب {student_name}")
        return False

# ========== معالجات البوت ==========

async def start(update: Update, context):
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        try:
            user = get_user(user_id)
            if user and user['name']:
                await update.message.reply_text(f"أهلاً بك مجدداً يا {user['name']}! 👋", reply_markup=get_main_menu_keyboard())
                update_user_state(user_id, "main_menu")
            else:
                save_user(user_id, "", "awaiting_name")
                await update.message.reply_text("أهلاً بك في حلقة القرآن! 🌸\nالرجاء إدخال اسمك الكامل (ثلاثي) للبدء.", reply_markup=ReplyKeyboardRemove())
        except Exception as e:
            logger.exception(f"خطأ في start للمستخدم {user_id}")

async def handle_text(update: Update, context):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    text = update.message.text
    
    try:
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
                pending_user_actions[user_id] = {
                    "type": "question", 
                    "subtype": "سؤال_نصي", 
                    "text_content": text, 
                    "file_id": None, 
                    "original_message_id": update.message.message_id
                }
                await update.message.reply_text(
                    "وصلني سؤالك النصي، هل تودين إرساله?", 
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ إرسال", callback_data="confirm_send")], 
                        [InlineKeyboardButton("❌ إلغاء", callback_data="confirm_resend")]
                    ])
                )
                update_user_state(user_id, "awaiting_confirmation")

        elif chat_id == GROUP_ID:
            teacher_id = update.effective_user.id
            if teacher_id in waiting_for_reply:
                data = waiting_for_reply[teacher_id]
                if data["type"] == "text":
                    success = await send_teacher_reply(
                        context,
                        data["student_id"],
                        data["submission_id"],
                        data["submission_type"],
                        data["student_name"],
                        "text",
                        text
                    )
                    if success:
                        await update.message.reply_text(f"✅ تم إرسال الرد النصي إلى {data['student_name']}")
                        del waiting_for_reply[teacher_id]
                    else:
                        await update.message.reply_text("❌ فشل إرسال الرد، حاول مرة أخرى")
    except Exception as e:
        logger.exception(f"خطأ في handle_text للمستخدم {user_id}")

async def handle_voice(update: Update, context):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    try:
        user = get_user(user_id)

        if chat_type == "private":
            if user and user.get("state") in ["awaiting_hifz_submission", "awaiting_murajaah_submission", "awaiting_voice_question"]:
                sub_type = "حفظ" if user["state"] == "awaiting_hifz_submission" else "مراجعة" if user["state"] == "awaiting_murajaah_submission" else "سؤال_صوتي"
                pending_user_actions[user_id] = {
                    "type": "submission" if "submission" in user["state"] else "question", 
                    "subtype": sub_type, 
                    "file_id": update.message.voice.file_id, 
                    "text_content": None, 
                    "original_message_id": update.message.message_id
                }
                await update.message.reply_text(
                    "وصلني تسجيلك، يمكنك المعاينة قبل الإرسال.", 
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ إرسال للمعلمة", callback_data="confirm_send")], 
                        [InlineKeyboardButton("❌ إعادة التسجيل", callback_data="confirm_resend")]
                    ])
                )
                update_user_state(user_id, "awaiting_confirmation")

        elif chat_id == GROUP_ID:
            teacher_id = update.effective_user.id
            if teacher_id in waiting_for_reply:
                data = waiting_for_reply[teacher_id]
                if data["type"] == "voice":
                    success = await send_teacher_reply(
                        context,
                        data["student_id"],
                        data["submission_id"],
                        data["submission_type"],
                        data["student_name"],
                        "voice",
                        update.message.voice.file_id
                    )
                    if success:
                        await update.message.reply_text(f"✅ تم إرسال الرد الصوتي إلى {data['student_name']}")
                        del waiting_for_reply[teacher_id]
                    else:
                        await update.message.reply_text("❌ فشل إرسال الرد، حاول مرة أخرى")
    except Exception as e:
        logger.exception(f"خطأ في handle_voice للمستخدم {user_id}")

async def handle_callback(update: Update, context):
    query = update.callback_query
    callback_data = query.data
    await query.answer()
    
    try:
        if callback_data == "confirm_send":
            user_id = query.from_user.id
            user = get_user(user_id)
            if user_id in pending_user_actions:
                action = pending_user_actions.pop(user_id)
                
                # حفظ الملف الصوتي إذا وجد
                saved_voice = None
                if action["file_id"]:
                    saved_voice = await save_voice_file(
                        context.bot,
                        action["file_id"]
                    )
                
                # حفظ التسميع في قاعدة البيانات
                submission_id = save_submission(
                    user_id, 
                    action["subtype"], 
                    saved_voice, 
                    action["text_content"], 
                    action["original_message_id"]
                )
                
                title = "🎤 تسميع جديد" if action['type'] == 'submission' else "❓ سؤال جديد"
                caption = f"{title} - {action['subtype']}\nالطالبة: {user['name']}"
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("رد نصي ✍️", callback_data=f"r_t_{submission_id}"), 
                     InlineKeyboardButton("رد صوتي 🎙️", callback_data=f"r_v_{submission_id}")]
                ])
                
                # إرسال للمجموعة
                if action["file_id"]:
                    await context.bot.send_voice(chat_id=GROUP_ID, voice=action["file_id"], caption=caption, reply_markup=markup)
                else:
                    await context.bot.send_message(chat_id=GROUP_ID, text=f"{caption}\n\n{action['text_content']}", reply_markup=markup)
                
                await query.edit_message_text("✅ تم الإرسال للمعلمة بنجاح.")
                update_user_state(user_id, "main_menu")
                logger.info(f"تم إرسال تسميع جديد {submission_id} من المستخدم {user_id}")

        elif callback_data == "confirm_resend":
            user_id = query.from_user.id
            pending_user_actions.pop(user_id, None)
            await query.edit_message_text("تم إلغاء الإرسال.")
            update_user_state(user_id, "main_menu")
            logger.info(f"تم إلغاء الإرسال من المستخدم {user_id}")

        elif callback_data.startswith("r_"):
            parts = callback_data.split("_")
            submission_id = int(parts[2])
            r_type = "text" if parts[1] == "t" else "voice"
            
            submission = get_submission(submission_id)
            if submission:
                waiting_for_reply[query.from_user.id] = {
                    "student_id": submission["user_id"], 
                    "student_name": submission["name"], 
                    "submission_id": submission_id, 
                    "submission_type": submission["submission_type"], 
                    "type": r_type
                }
                msg = f"⏳ بانتظار الرد {'النصي' if r_type == 'text' else 'الصوتي'} لـ {submission['name']}..."
                if query.message.voice:
                    await query.edit_message_caption(caption=f"{query.message.caption}\n\n{msg}")
                else:
                    await query.edit_message_text(text=f"{query.message.text}\n\n{msg}")
                logger.info(f"المعلم {query.from_user.id} يجهز رد {r_type} للتسميع {submission_id}")
    except Exception as e:
        logger.exception(f"خطأ في handle_callback")

async def report_command(update: Update, context):
    if update.effective_chat.id != GROUP_ID:
        return
    
    try:
        rows = get_today_report()
        today_prefix = datetime.now(MECCA_TIMEZONE).strftime('%Y-%m-%d')
        
        if not rows:
            await update.message.reply_text(f"لا توجد إحصائيات لليوم ({today_prefix}).")
            return
            
        stats = {}
        total_submissions = 0
        for row in rows:
            total_submissions += 1
            name = row["name"]
            stype = row["submission_type"]
            if name not in stats:
                stats[name] = {}
            stats[name][stype] = stats[name].get(stype, 0) + 1
        
        report = f"📊 إحصائية حلقة اليوم ({today_prefix}):\n"
        report += f"✅ إجمالي التفاعلات: {total_submissions}\n"
        report += f"👥 عدد الطالبات: {len(stats)}\n\n"
        
        for i, (name, s) in enumerate(stats.items(), 1):
            details = [f"{k}{f': {v}' if v > 1 else ''}" for k, v in s.items()]
            report += f"{i}. {name} ({', '.join(details)})\n"
        
        await update.message.reply_text(report)
        logger.info(f"تم إرسال تقرير لليوم {today_prefix}")
    except Exception as e:
        logger.exception("خطأ في report_command")

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    # تهيئة قاعدة البيانات
    init_database()
    
    # تشغيل خادم الاستيقاظ
    keep_alive()
    
    # بناء التطبيق
    app = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_text))
    app.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE, handle_voice))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(GROUP_ID), handle_text))
    app.add_handler(MessageHandler(filters.VOICE & filters.Chat(GROUP_ID), handle_voice))
    
    # تشغيل البوت
    logger.info("🚀 بدء تشغيل البوت...")
    app.run_polling(drop_pending_updates=True, close_loop=False)

if __name__ == "__main__":
    main()
