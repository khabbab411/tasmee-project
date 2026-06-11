import os
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# المتغيرات
TOKEN = "ضع_توكن_البوت_هنا"
GROUP_ID = -1001234567890  # ضع ID مجموعة المعلمات

# تخزين مؤقت لأسماء الطالبات (في مشروع حقيقي استخدم قاعدة بيانات)
user_names = {}

# دالة /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("🌸 مرحباً بك في بوت التسميع\nأرسلي اسمك الكامل (ثلاثي) لنبدأ:")

# استلام الاسم
async def save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text
    user_names[user_id] = name
    await update.message.reply_text(f"✅ تم حفظ اسمك: {name}\n📤 الآن أرسلي صوتية التسميع 🎙️")

# استلام الصوتية من الطالبة
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = user_names.get(user_id, "طالبة بدون اسم")
    voice = update.message.voice

    # إرسال الصوتية إلى مجموعة المعلمات مع اسم الطالبة
    await context.bot.send_voice(
        chat_id=GROUP_ID,
        voice=voice.file_id,
        caption=f"📖 تسميع الطالبة: {name}\n👩‍🏫 الرجاء الرد على هذه الرسالة"
    )

    await update.message.reply_text("✅ تم إرسال تسميعك إلى المعلمات، ستصل إليك الملاحظات قريباً.")

# استلام الرد من المعلمة (في المجموعة)
async def handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التأكد أن الرسالة رد على رسالة أخرى
    if update.message.reply_to_message:
        original_message = update.message.reply_to_message
        original_caption = original_message.caption or ""

        # استخراج اسم الطالبة من الرسالة الأصلية
        if "📖 تسميع الطالبة:" in original_caption:
            student_name = original_caption.split("📖 تسميع الطالبة:")[1].split("\n")[0].strip()

            # البحث عن معرف الطالبة (في مشروع حقيقي تحتاج قاعدة بيانات)
            student_id = None
            for uid, uname in user_names.items():
                if uname == student_name:
                    student_id = uid
                    break

            if student_id:
                # إرسال الرد للطالبة
                if update.message.text:
                    await context.bot.send_message(student_id, f"📝 ملاحظة من المعلمة:\n{update.message.text}")
                elif update.message.voice:
                    await context.bot.send_voice(student_id, update.message.voice.file_id, caption="🎙️ ملاحظة صوتية من المعلمة")
            else:
                await update.message.reply_text("⚠️ لم أجد الطالبة في السجل.")

# تشغيل البوت
def main():
    # تشغيل خادم Flask (لإرضاء Render)
    from keep_alive import keep_alive
    keep_alive()

    # إعداد البوت
    application = Application.builder().token(TOKEN).build()

    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_name))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.ALL, handle_group_reply))

    # تشغيل البوت
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
