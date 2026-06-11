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

# تخزين أسماء الطالبات (مفتاح = معرف المستخدم، القيمة = {"name": الاسم, "step": المرحلة})
user_data = {}

# ========================
# دوال مساعدة
# ========================
def is_valid_name(name: str) -> bool:
    """تتأكد أن الاسم يتكون من كلمتين على الأقل وليس نقطة أو حرف واحد"""
    name = name.strip()
    if len(name) < 5:  # الاسم الحقيقي أطول من 4 حروف
        return False
    words = name.split()
    if len(words) < 2:  # على الأقل اسم + لقب
        return False
    return True

# ========================
# أوامر البوت
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عند الضغط على /start"""
    if update.effective_chat.type != "private":
        return
    
    user_id = update.effective_user.id
    user_data[user_id] = {"step": "waiting_for_name"}
    
    await update.message.reply_text(
        "🌸 مرحباً بك في بوت التسميع\n"
        "أرسلي اسمك الكامل (ثلاثي) لنبدأ:\n\n"
        "مثال: فاطمة محمد الزهراء"
    )
    logger.info(f"📌 الطالبة {user_id} بدأت البوت")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية في الخاص"""
    if update.effective_chat.type != "private":
        return
    
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # إذا كان المستخدم ليس لديه بيانات، اطلب منه /start
    if user_id not in user_data:
        await update.message.reply_text("⚠️ أرسلي /start أولاً")
        return
    
    step = user_data[user_id].get("step")
    
    if step == "waiting_for_name":
        # التحقق من صحة الاسم
        if text.lower() == "/start":
            return
        
        if not is_valid_name(text):
            await update.message.reply_text(
                "❌ الاسم غير صحيح. أرسلي اسمك الكامل (ثلاثي) على الأقل.\n"
                "مثال: فاطمة محمد الزهراء"
            )
            return
        
        # حفظ الاسم
        user_data[user_id]["name"] = text
        user_data[user_id]["step"] = "ready"
        await update.message.reply_text(
            f"✅ تم حفظ اسمك: {text}\n"
            f"📤 الآن أرسلي صوتية التسميع 🎙️"
        )
        logger.info(f"📝 تم حفظ اسم الطالبة {user_id}: {text}")
    
    elif step == "ready":
        # إذا كان في مرحلة ready وأرسل نصاً، ذكره بأنه يحتاج صوتية
        await update.message.reply_text(
            "📤 أنت الآن في مرحلة إرسال التسميع.\n"
            "الرجاء إرسال **صوتية** 🎙️ وليس نصاً."
        )
    else:
        await update.message.reply_text("⚠️ أرسلي /start للبدء")

async def handle_voice_from_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام الصوتية من الطالبة"""
    if update.effective_chat.type != "private":
        return
    
    user_id = update.effective_user.id
    
    # التأكد من أن الطالبة سجلت اسمها أولاً
    if user_id not in user_data or "name" not in user_data[user_id]:
        await update.message.reply_text(
            "⚠️ لم أجد اسمك.\n"
            "أرسلي /start ثم اسمك الكامل أولاً."
        )
        return
    
    name = user_data[user_id]["name"]
    voice = update.message.voice
    
    # إرسال الصوتية إلى مجموعة المعلمات
    await context.bot.send_voice(
        chat_id=GROUP_ID,
        voice=voice.file_id,
        caption=f"📖 تسميع الطالبة: {name}\n👩‍🏫 الرجاء الرد على هذه الرسالة"
    )
    
    await update.message.reply_text(
        "✅ تم إرسال تسميعك إلى المعلمات.\n"
        "ستصلك الملاحظات قريباً."
    )
    logger.info(f"🎤 تم إرسال تسميع الطالبة {name} إلى المجموعة")

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الردود من المعلمات في المجموعة"""
    
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
    
    # البحث عن معرف الطالبة باستخدام الاسم
    student_id = None
    for uid, data in user_data.items():
        if data.get("name") == student_name:
            student_id = uid
            break
    
    logger.info(f"🔍 user_data الحالي: {user_data}")
    logger.info(f"👩‍🎓 الطالبة المطلوبة: '{student_name}' -> ID: {student_id}")
    
    if not student_id:
        await update.message.reply_text(
            f"⚠️ لم أجد الطالبة '{student_name}' في السجل.\n"
            f"تأكدي أنها أرسلت اسمها للبوت أولاً."
        )
        logger.warning(f"⚠️ لم يتم العثور على الطالبة '{student_name}'")
        return
    
    # إرسال الرد إلى الطالبة
    try:
        if update.message.text:
            await context.bot.send_message(
                student_id, 
                f"📝 *ملاحظة من المعلمة:*\n{update.message.text}", 
                parse_mode="Markdown"
            )
            await update.message.reply_text(f"✅ تم إرسال ملاحظتك إلى {student_name}")
            logger.info(f"✅ تم إرسال رد نصي إلى {student_name}")
            
        elif update.message.voice:
            await context.bot.send_voice(
                student_id, 
                update.message.voice.file_id, 
                caption="🎙️ *ملاحظة صوتية من المعلمة*",
                parse_mode="Markdown"
            )
            await update.message.reply_text(f"✅ تم إرسال الملاحظة الصوتية إلى {student_name}")
            logger.info(f"✅ تم إرسال رد صوتي إلى {student_name}")
            
    except Exception as e:
        logger.error(f"💥 فشل إرسال الرد: {e}")
        await update.message.reply_text(f"⚠️ فشل إرسال الملاحظة: {str(e)}")

# ========================
# تشغيل البوت
# ========================
def main():
    from keep_alive import keep_alive
    keep_alive()
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_from_student))
    application.add_handler(MessageHandler(filters.ALL, handle_group_messages))
    
    logger.info("🚀 البوت بدأ العمل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
