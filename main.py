import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ========================
# الإعدادات الأساسية
# ========================
TOKEN = "8850523963:AAEDeo6_T5LeNqpTMq0kEIHozwymORvhylQ"
GROUP_ID = -1003914929532  # ضع ID مجموعة المعلمات

# تخزين مؤقت لأسماء الطالبات
user_names = {}

# ========================
# أوامر البوت
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عند الضغط على /start في الخاص"""
    user_id = update.effective_user.id
    
    # نتأكد أن الرسالة من محادثة خاصة وليست من مجموعة
    if update.effective_chat.type != "private":
        return
    
    await update.message.reply_text(
        "🌸 مرحباً بك في بوت التسميع\n"
        "أرسلي اسمك الكامل (ثلاثي) لنبدأ:"
    )

async def save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ اسم الطالبة (فقط في الخاص)"""
    user_id = update.effective_user.id
    
    # نتأكد أن الرسالة من محادثة خاصة
    if update.effective_chat.type != "private":
        return
    
    name = update.message.text.strip()
    user_names[user_id] = name
    
    await update.message.reply_text(
        f"✅ تم حفظ اسمك: {name}\n"
        f"📤 الآن أرسلي صوتية التسميع 🎙️"
    )

async def handle_voice_from_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام الصوتية من الطالبة في الخاص"""
    user_id = update.effective_user.id
    
    # نتأكد أن الرسالة من محادثة خاصة
    if update.effective_chat.type != "private":
        return
    
    name = user_names.get(user_id)
    if not name:
        await update.message.reply_text("⚠️ لم أجد اسمك. أرسلي /start ثم اسمك الكامل أولاً.")
        return
    
    voice = update.message.voice
    
    # إرسال الصوتية إلى مجموعة المعلمات مع اسم الطالبة
    await context.bot.send_voice(
        chat_id=GROUP_ID,
        voice=voice.file_id,
        caption=f"📖 تسميع الطالبة: {name}\n👩‍🏫 الرجاء الرد على هذه الرسالة"
    )
    
    await update.message.reply_text(
        "✅ تم إرسال تسميعك إلى المعلمات.\n"
        "ستصلك الملاحظات قريباً."
    )

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل في مجموعة المعلمات (لن يحدث أي شيء خارج الردود)"""
    
    # نتأكد أن الرسالة من المجموعة
    if update.effective_chat.id != GROUP_ID:
        return
    
    # نتأكد أن الرسالة هي رد على رسالة سابقة
    if not update.message.reply_to_message:
        # إذا كانت رسالة جديدة في المجموعة (ليست رداً)، نتجاهلها تماماً
        return
    
    original = update.message.reply_to_message
    
    # نتأكد أن الرسالة الأصلية هي تسميع طالبة (تحتوي على كلمة "تسميع الطالبة")
    if not original.caption or "📖 تسميع الطالبة:" not in original.caption:
        return
    
    # استخراج اسم الطالبة من الرسالة الأصلية
    try:
        student_name = original.caption.split("📖 تسميع الطالبة:")[1].split("\n")[0].strip()
    except:
        await update.message.reply_text("⚠️ حدث خطأ في قراءة بيانات الطالبة.")
        return
    
    # البحث عن معرف الطالبة
    student_id = None
    for uid, uname in user_names.items():
        if uname == student_name:
            student_id = uid
            break
    
    if not student_id:
        await update.message.reply_text(f"⚠️ لم أجد الطالبة '{student_name}' في السجل.")
        return
    
    # إرسال الرد إلى الطالبة
    if update.message.text:
        # رد نصي
        await context.bot.send_message(
            student_id,
            f"📝 *ملاحظة من المعلمة:*\n{update.message.text}",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ تم إرسال ملاحظتك إلى الطالبة {student_name}")
    
    elif update.message.voice:
        # رد صوتي
        await context.bot.send_voice(
            student_id,
            update.message.voice.file_id,
            caption="🎙️ *ملاحظة صوتية من المعلمة*",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ تم إرسال الملاحظة الصوتية إلى الطالبة {student_name}")

# ========================
# تشغيل البوت
# ========================
def main():
    # تشغيل خادم Flask لإرضاء Render
    from keep_alive import keep_alive
    keep_alive()
    
    # إعداد البوت
    application = Application.builder().token(TOKEN).build()
    
    # أوامر البوت (تعمل فقط في الخاص)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_name))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_from_student))
    
    # معالجة المجموعة (تعمل فقط في مجموعة المعلمات)
    application.add_handler(MessageHandler(filters.ALL, handle_group_messages))
    
    # تشغيل البوت
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
