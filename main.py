import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from keep_alive import keep_alive

# إعداد السجلات
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# المخازن المؤقتة
user_data = {}
waiting_for_reply = {}

# --- الإعدادات ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8850523963:AAFq_4TqBSpdbWFwYY-T3vrlMkcEFsvk5DQ")
GROUP_ID = int(os.environ.get("TEACHERS_GROUP_ID", "-1003914929532"))

# --- الدوال المساعدة ---
def is_valid_name(name: str) -> bool:
    name = name.strip()
    return len(name) >= 5 and len(name.split()) >= 2

# --- معالجات البوت ---
async def start(update: Update, context) -> None:
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        user_data[user_id] = {"step": "awaiting_name"}
        await update.message.reply_text("أهلاً بك! الرجاء إدخال اسمك الكامل (ثلاثي) للبدء.")

async def handle_text(update: Update, context) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    text = update.message.text

    if chat_type == "private":
        if user_id in user_data and user_data[user_id].get("step") == "awaiting_name":
            if is_valid_name(text):
                user_data[user_id] = {"name": text, "step": "awaiting_voice"}
                await update.message.reply_text(f"تم حفظ اسمك يا {text}. الآن أرسل صوتية التسميع.")
            else:
                await update.message.reply_text("الاسم قصير جداً، يرجى إرسال اسمك الثلاثي.")
    
    elif chat_type == "group" and update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply and waiting_for_reply[teacher_id]["type"] == "text":
            student_id = waiting_for_reply[teacher_id]["student_id"]
            await context.bot.send_message(chat_id=student_id, text=f"ملاحظة نصية من المعلمة:\n{text}")
            await update.message.reply_text(f"✅ تم إرسال الرد إلى {waiting_for_reply[teacher_id]['student_name']}")
            del waiting_for_reply[teacher_id]

async def handle_voice(update: Update, context) -> None:
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        if user_id in user_data and "name" in user_data[user_id]:
            name = user_data[user_id]["name"]
            keyboard = [[InlineKeyboardButton("رد نصي", callback_data=f"r_t_{user_id}_{name}"),
                         InlineKeyboardButton("رد صوتي", callback_data=f"r_v_{user_id}_{name}")]]
            await context.bot.send_voice(chat_id=GROUP_ID, voice=update.message.voice.file_id,
                                         caption=f"تسميع: {name}\nID: {user_id}",
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

async def handle_callback(update: Update, context) -> None:
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

def main():
    # 1. تشغيل سيرفر Flask فوراً في الخلفية
    keep_alive()
    
    # 2. إعداد البوت
    app = Application.builder().token(TOKEN).build()
    
    # 3. إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_text))
    app.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE, handle_voice))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(GROUP_ID), handle_text))
    app.add_handler(MessageHandler(filters.VOICE & filters.Chat(GROUP_ID), handle_voice))

    # 4. التشغيل مع مسح التحديثات القديمة
    print("🤖 البوت بدأ العمل...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
