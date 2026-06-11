import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# تفعيل السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========================
# الإعدادات الأساسية
# ========================
TOKEN = "8850523963:AAEDeo6_T5LeNqpTMq0kEIHozwymORvhylQ"
GROUP_ID = -1003914929532  # ضع ID مجموعة المعلمات هنا

# تخزين أسماء الطالبات
user_names = {}

# ========================
# أوامر البوت
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user_id = update.effective_user.id
    await update.message.reply_text("🌸 مرحباً بك في بوت التسميع\nأرسلي اسمك الكامل (ثلاثي) لنبدأ:")
    logger.info(f"📌 الطالبة {user_id} بدأت البوت")

async def save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user_id = update.effective_user.id
    name = update.message.text.strip()
    user_names[user_id] = name
    await update.message.reply_text(f"✅ تم حفظ اسمك: {name}\n📤 الآن أرسلي صوتية التسميع 🎙️")
    logger.info(f"📝 تم حفظ اسم الطالبة {user_id}: {name}")

async def handle_voice_from_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user_id = update.effective_user.id
    name = user_names.get(user_id)
    if not name:
        await update.message.reply_text("⚠️ لم أجد اسمك. أرسلي /start ثم اسمك الكامل أولاً.")
        return
    voice = update.message.voice
    await context.bot.send_voice(
        chat_id=GROUP_ID,
        voice=voice.file_id,
        caption=f"📖 تسميع الطالبة: {name}\n👩‍🏫 الرجاء الرد على هذه الرسالة"
    )
    await update.message.reply_text("✅ تم إرسال تسميعك إلى المعلمات.\nستصلك الملاحظات قريباً.")
    logger.info(f"🎤 تم إرسال تسميع الطالبة {name} إلى المجموعة")

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # نتأكد أن الرسالة من المجموعة الصحيحة
    if update.effective_chat.id != GROUP_ID:
        return
    
    logger.info(f"📩 رسالة جديدة في المجموعة من {update.effective_user.first_name}")
    
    # نتأكد أنها رد على رسالة سابقة
    if not update.message.reply_to_message:
        logger.info("⏭️ الرسالة ليست رداً، تم تجاهلها")
        return
    
    logger.info("↩️ هذه رسالة رد")
    original = update.message.reply_to_message
    
    # نتأكد أن الرسالة الأصلية هي تسميع طالبة
    if not original.caption or "📖 تسميع الطالبة:" not in original.caption:
        logger.info("❌ الرد ليس على تسميع طالبة، تم تجاهله")
        return
    
    # استخراج اسم الطالبة
    try:
        student_name = original.caption.split("📖 تسميع الطالبة:")[1].split("\n")[0].strip()
        logger.info(f"🎯 استخراج اسم الطالبة: '{student_name}'")
    except Exception as e:
        logger.error(f"🔥 فشل استخراج الاسم: {e}")
        return
    
    # البحث عن معرف الطالبة
    student_id = None
    for uid, uname in user_names.items():
        if uname == student_name:
            student_id = uid
            break
    
    logger.info(f"🔍 user_names الحالي: {user_names}")
    logger.info(f"👩‍🎓 الطالبة المطلوبة: '{student_name}' -> ID: {student_id}")
    
    if not student_id:
        await update.message.reply_text(f"⚠️ لم أجد الطالبة '{student_name}' في السجل.")
        logger.warning(f"⚠️ لم يتم العثور على الطالبة '{student_name}'")
        return
    
    # إرسال الرد
    try:
        if update.message.text:
            await context.bot.send_message(student_id, f"📝 *ملاحظة من المعلمة:*\n{update.message.text}", parse_mode="Markdown")
            await update.message.reply_text(f"✅ تم إرسال ملاحظتك إلى {student_name}")
            logger.info(f"✅ تم إرسال رد نصي إلى {student_name}")
        elif update.message.voice:
            await context.bot.send_voice(student_id, update.message.voice.file_id, caption="🎙️ *ملاحظة صوتية من المعلمة*", parse_mode="Markdown")
            await update.message.reply_text(f"✅ تم إرسال الملاحظة الصوتية إلى {student_name}")
            logger.info(f"✅ تم إرسال رد صوتي إلى {student_name}")
    except Exception as e:
        logger.error(f"💥 فشل إرسال الرد: {e}")

# ========================
# تشغيل البوت
# ========================
def main():
    from keep_alive import keep_alive
    keep_alive()
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_name))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_from_student))
    application.add_handler(MessageHandler(filters.ALL, handle_group_messages))
    
    logger.info("🚀 البوت بدأ العمل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
