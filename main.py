import logging
import os
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from keep_alive import keep_alive

# 1. إعداد السجلات (Logs)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. المخازن المؤقتة للبيانات
user_data = {}  # {user_id: {"name": "الاسم", "step": "المرحلة"}}
waiting_for_reply = {}  # {teacher_id: {"student_id": xxx, "student_name": xxx, "type": "text/voice"}}

# --- 3. الإعدادات (ضع بياناتك هنا) ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8871655491:AAEWD5WQxJUeBBngKxe8u2OJonKcVsQo4sg")
GROUP_ID = int(os.environ.get("TEACHERS_GROUP_ID", "-1004344713055"))

# --- 4. الدوال المساعدة ---
def is_valid_name(name: str) -> bool:
    name = name.strip()
    return len(name) >= 5 and len(name.split()) >= 2

# --- 5. معالجات البوت ---

# دالة البداية للطالبة
async def start(update: Update, context) -> None:
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        user_data[user_id] = {"step": "awaiting_name"}
        await update.message.reply_text(
            f"أهلاً بك يا {update.effective_user.first_name}! 👋\nالرجاء إدخال اسمك الكامل (ثلاثي على الأقل) للتسجيل."
        )

# معالجة النصوص (الاسم من الطالبة أو الرد النصي من المعلمة)
async def handle_text(update: Update, context) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    text = update.message.text

    if chat_type == "private":
        if user_id in user_data and user_data[user_id].get("step") == "awaiting_name":
            if is_valid_name(text):
                user_data[user_id] = {"name": text, "step": "awaiting_voice"}
                await update.message.reply_text(
                    f"شكراً لك يا {text}! تم حفظ اسمك.\nالآن، الرجاء إرسال صوتية التسميع."
                )
            else:
                await update.message.reply_text("الاسم غير صحيح. يرجى إرسال اسمك الثلاثي.")
    
    elif chat_type == "group" and update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply and waiting_for_reply[teacher_id]["type"] == "text":
            student_id = waiting_for_reply[teacher_id]["student_id"]
            student_name = waiting_for_reply[teacher_id]["student_name"]
            await context.bot.send_message(chat_id=student_id, text=f"ملاحظة من المعلمة:\n{text}")
            await update.message.reply_text(f"✅ تم إرسال الملاحظة إلى {student_name}")
            del waiting_for_reply[teacher_id]

# معالجة الصوتيات (التسميع من الطالبة أو الرد الصوتي من المعلمة)
async def handle_voice(update: Update, context) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type

    if chat_type == "private":
        if user_id in user_data and "name" in user_data[user_id]:
            name = user_data[user_id]["name"]
            keyboard = [
                [InlineKeyboardButton("رد نصي", callback_data=f"r_t_{user_id}_{name}"),
                 InlineKeyboardButton("رد صوتي", callback_data=f"r_v_{user_id}_{name}")]
            ]
            await context.bot.send_voice(
                chat_id=GROUP_ID,
                voice=update.message.voice.file_id,
                caption=f"تسميع من الطالبة: {name}\nID: {user_id}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await update.message.reply_text("✅ تم إرسال تسميعك إلى المعلمات")
        else:
            await update.message.reply_text("الرجاء إرسال /start أولاً.")
    
    elif chat_type == "group" and update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply and waiting_for_reply[teacher_id]["type"] == "voice":
            student_id = waiting_for_reply[teacher_id]["student_id"]
            student_name = waiting_for_reply[teacher_id]["student_name"]
            await context.bot.send_voice(chat_id=student_id, voice=update.message.voice.file_id)
            await update.message.reply_text(f"✅ تم إرسال الرد الصوتي إلى {student_name}")
            del waiting_for_reply[teacher_id]

# معالجة ضغط الأزرار في مجموعة المعلمات
async def handle_callback(update: Update, context) -> None:
    query = update.callback_query
    data = query.data.split('_')
    # r_t_user_id_name -> ['r', 't', 'user_id', 'name']
    
    teacher_id = query.from_user.id
    waiting_for_reply[teacher_id] = {
        "type": "text" if data[1] == "t" else "voice",
        "student_id": int(data[2]),
        "student_name": "_".join(data[3:])
    }
    
    msg = "الرجاء كتابة الرد النصي الآن:" if data[1] == "t" else "الرجاء إرسال الرد الصوتي الآن:"
    await query.edit_message_caption(
        caption=query.message.caption + f"\n\n⏳ {msg}",
        reply_markup=None
    )
    await query.answer()

# --- 6. الدالة الرئيسية ---
def main():
    # تشغيل سيرفر Flask لضمان بقاء البوت حياً على Render
    keep_alive()
    
    # انتظار لمدة 20 ثانية لضمان إغلاق أي اتصالات قديمة (حل مشكلة Conflict)
    print("⏳ جاري تنظيف الاتصالات القديمة... يرجى الانتظار 20 ثانية")
    time.sleep(20)
    
    # بناء تطبيق البوت
    application = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_text))
    application.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE, handle_voice))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & filters.Chat(GROUP_ID), handle_text))
    application.add_handler(MessageHandler(filters.VOICE & filters.Chat(GROUP_ID), handle_voice))

    # التشغيل مع مسح أي رسائل قديمة عالقة
    print("🚀 البوت بدأ العمل الآن بنجاح!")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
