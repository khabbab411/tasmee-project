import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from keep_alive import keep_alive

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global dictionaries for temporary data storage
user_data = {}  # {user_id: {"name": "الاسم", "step": "مرحلة"}}
waiting_for_reply = {}  # {teacher_id: {"student_id": xxx, "student_name": xxx, "type": "text/voice"}}

# --- Configuration --- #
# Replace with your bot token from BotFather
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8850523963:AAEjjD2hElr0iXWbl2N84jSJkXzyCv1ejck")
# Replace with your teachers' group ID (e.g., -1001234567890)
GROUP_ID = int(os.environ.get("TEACHERS_GROUP_ID", "-1003914929532"))

# --- Helper Functions --- #
def is_valid_name(name: str) -> bool:
    name = name.strip()
    if len(name) < 5:
        return False
    words = name.split()
    if len(words) < 2:
        return False
    return True

# --- Bot Commands and Handlers --- #
async def start(update: Update, context) -> None:
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    if update.effective_chat.type == "private":
        if user_id not in user_data or "name" not in user_data[user_id]:
            user_data[user_id] = {"step": "awaiting_name"}
            await update.message.reply_text(
                f"أهلاً بك يا {user_name}! 👋\nالرجاء إدخال اسمك الكامل (ثلاثي على الأقل) لتسجيلك في الحلقة."
            )
        else:
            await update.message.reply_text(
                f"أهلاً بك مجدداً يا {user_data[user_id]['name']}!\nالرجاء إرسال صوتية التسميع."
            )
            user_data[user_id]["step"] = "awaiting_voice"
    else:
        # Ignore start command in groups
        pass

async def handle_text(update: Update, context) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    text = update.message.text

    if chat_type == "private":
        if user_id in user_data and user_data[user_id].get("step") == "awaiting_name":
            if is_valid_name(text):
                user_data[user_id]["name"] = text
                user_data[user_id]["step"] = "awaiting_voice"
                await update.message.reply_text(
                    f"شكراً لك يا {text}! تم حفظ اسمك بنجاح.\nالآن، الرجاء إرسال صوتية التسميع."
                )
            else:
                await update.message.reply_text(
                    "الاسم غير صحيح. الرجاء إدخال اسم كامل (ثلاثي على الأقل، مثال: فاطمة محمد الزهراء)."
                )
        else:
            await update.message.reply_text("الرجاء إرسال صوتية التسميع.")

    elif chat_type == "group" and update.effective_chat.id == GROUP_ID:
        teacher_id = update.effective_user.id
        if teacher_id in waiting_for_reply and waiting_for_reply[teacher_id].get("type") == "text":
            student_id = waiting_for_reply[teacher_id]["student_id"]
            student_name = waiting_for_reply[teacher_id]["student_name"]
            
            # Send text reply to student
            await context.bot.send_message(chat_id=student_id, text=f"ملاحظة من المعلمة:\n{text}")
            
            await update.message.reply_text(f"✅ تم إرسال الملاحظة إلى {student_name}")
            del waiting_for_reply[teacher_id]

async def handle_voice_from_student(update: Update, context) -> None:
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type

    if chat_type == "private":
        if user_id in user_data and "name" in user_data[user_id]:
            student_name = user_data[user_id]["name"]
            voice_file_id = update.message.voice.file_id

            keyboard = [
                [InlineKeyboardButton("رد نصي", callback_data=f"reply_text_{user_id}_{student_name}")],
                [InlineKeyboardButton("رد صوتي", callback_data=f"reply_voice_{user_id}_{student_name}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send voice to teachers' group
            await context.bot.send_voice(
                chat_id=GROUP_ID,
                voice=voice_file_id,
                caption=f"تسميع من الطالبة: {student_name}\nمعرف الطالبة: {user_id}",
                reply_markup=reply_markup
            )
            await update.message.reply_text("✅ تم إرسال تسميعك إلى المعلمات")
            user_data[user_id]["step"] = "awaiting_teacher_reply"
        else:
            await update.message.reply_text("الرجاء إرسال /start أولاً لتسجيل اسمك.")

async def handle_callback(update: Update, context) -> None:
    query = update.callback_query
    teacher_id = query.from_user.id
    chat_id = query.message.chat_id

    if chat_id == GROUP_ID: # Ensure callback is from the teachers' group
        callback_data = query.data
        parts = callback_data.split('_')
        action_type = parts[1] # 'text' or 'voice'
        student_id = int(parts[2])
        student_name = '_'.join(parts[3:]) # Reconstruct student name

        waiting_for_reply[teacher_id] = {
            "student_id": student_id,
            "student_name": student_name,
            "type": action_type
        }

        if action_type == "text":
            await query.edit_message_caption(
                caption=query.message.caption + f"\n\nالمعلمة {query.from_user.first_name} تود الرد نصياً.\nالرجاء كتابة الرد الآن في هذه المجموعة.",
                reply_markup=None
            )
        elif action_type == "voice":
            await query.edit_message_caption(
                caption=query.message.caption + f"\n\nالمعلمة {query.from_user.first_name} تود الرد صوتياً.\nالرجاء إرسال الرد الصوتي الآن في هذه المجموعة.",
                reply_markup=None
            )
    await query.answer()

async def handle_group_messages(update: Update, context) -> None:
    teacher_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if chat_id == GROUP_ID and teacher_id in waiting_for_reply:
        reply_info = waiting_for_reply[teacher_id]
        student_id = reply_info["student_id"]
        student_name = reply_info["student_name"]
        reply_type = reply_info["type"]

        if reply_type == "voice" and update.message.voice:
            voice_file_id = update.message.voice.file_id
            await context.bot.send_voice(chat_id=student_id, voice=voice_file_id)
            await update.message.reply_text(f"✅ تم إرسال الملاحظة الصوتية إلى {student_name}")
            del waiting_for_reply[teacher_id]
        elif reply_type == "text" and update.message.text:
            # This case is handled by handle_text, but we keep this for clarity if other message types were allowed
            pass
        else:
            await update.message.reply_text("الرجاء إرسال الرد بالصيغة المطلوبة (نص أو صوتية).")

def main() -> None:
    # Start the Flask server for Render's health check
    keep_alive()

    application = Application.builder().token(TOKEN).build()

    # Handlers for private chat with students
    application.add_handler(CommandHandler("start", start, filters.ChatType.PRIVATE))
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_text))
    application.add_handler(MessageHandler(filters.VOICE & filters.ChatType.PRIVATE, handle_voice_from_student))

    # Handlers for teachers' group
    application.add_handler(CallbackQueryHandler(handle_callback, chat_id=GROUP_ID))
    application.add_handler(MessageHandler(filters.VOICE & filters.Chat(GROUP_ID), handle_group_messages))
    application.add_handler(MessageHandler(filters.TEXT & filters.Chat(GROUP_ID), handle_text)) # Handle text replies from teachers

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
