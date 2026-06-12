import logging
import os
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from keep_alive import keep_alive

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

user_data = {}
waiting_for_reply = {}

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8871655491:AAEWD5WQxJUeBBngKxe8u2OJonKcVsQo4sg")
GROUP_ID = int(os.environ.get("TEACHERS_GROUP_ID", "-1004344713055"))

def is_valid_name(name: str) -> bool:
    name = name.strip()
    return len(name) >= 5 and len(name.split()) >= 2

async def start(update: Update, context) -> None:
    if update.effective_chat.type == "private":
        user_data[update.effective_user.id] = {"step": "awaiting_name"}
        await update.message.reply_text("أهلاً بك! الرجاء إدخال اسمك الكامل (ثلاثي) للبدء.")

async def handle_text(update: Update, context) -> None:
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        if user_id in user_data and user_data[user_id].get("step") == "awaiting_name":
            if is_valid_name(update.message.text):
                user_data[user_id] = {"name": update.message.text, "step": "awaiting_voice"}
                await update.message.reply_text(f"تم حفظ اسمك. الآن أرسل صوتية التسميع.")
            else:
                await update.message.reply_text("الاسم قصير جداً، يرجى إرسال اسمك الثلاثي.")
    elif update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply and waiting_for_reply[teacher_id]["type"] == "text":
            await context.bot.send_message(chat_id=waiting_for_reply[teacher_id]["student_id"], text=f"ملاحظة: {update.message.text}")
            await update.message.reply_text(f"✅ تم الإرسال إلى {waiting_for_reply[teacher_id]['student_name']}")
            del waiting_for_reply[teacher_id]

async def handle_voice(update: Update, context) -> None:
    user_id = update.effective_user.id
    if update.effective_chat.type == "private":
        if user_id in user_data and "name" in user_data[user_id]:
            keyboard = [[InlineKeyboardButton("رد نصي", callback_data=f"r_t_{user_id}_{user_data[user_id]['name']}"),
                         InlineKeyboardButton("رد صوتي", callback_data=f"r_v_{user_id}_{user_data[user_id]['name']}")]]
            await context.bot.send_voice(chat_id=GROUP_ID, voice=update.message.voice.file_id,
                                         caption=f"تسميع: {user_data[user_id]['name']}",
                                         reply_markup=InlineKeyboardMarkup(keyboard))
            await update.message.reply_text("✅ تم الإرسال.")
    elif update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply and waiting_for_reply[teacher_id]["type"] == "voice":
            await context.bot.send_voice(chat_id=waiting_for_reply[teacher_id]["student_id"], voice=update.message.voice.file_id)
            await update.message.reply_text(f"✅ تم الإرسال إلى {waiting_for_reply[teacher_id]['student_name']}")
            del waiting_for_reply[teacher_id]

async def handle_callback(update: Update, context) -> None:
    query = update.callback_query
    data = query.data.split('_')
    waiting_for_reply[query.from_user.id] = {"type": "text" if data[1] == "t" else "voice", "student_id": int(data[2]), "student_name": data[3]}
    await query.edit_message_caption(caption=query.message.caption + f"\n\n⏳ أرسل الرد الآن:")
    await query.answer()

def main():
    keep_alive()
    # تأخير لمدة 10 ثوانٍ للسماح للنسخ القديمة في Render بالإغلاق تماماً
    print("⏳ جاري الانتظار قليلاً لضمان عدم وجود تعارض...")
    time.sleep(10) 
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_text))
    app.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE, handle_voice))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(GROUP_ID), handle_text))
    app.add_handler(MessageHandler(filters.VOICE & filters.Chat(GROUP_ID), handle_voice))

    print("🚀 البوت بدأ العمل الآن...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
