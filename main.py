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

# تخزين بيانات الطالبات
user_data = {}

# ========================
# دوال مساعدة
# ========================
def is_valid_name(name: str) -> bool:
    name = name.strip()
    if len(name) < 5:
        return False
    words = name.split()
    if len(words) < 2:
        return False
    return True

# ========================
# أوامر البوت
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if update.effective_chat.type != "private":
        return
    
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_data:
        await update.message.reply_text("⚠️ أرسلي /start أولاً")
        return
    
    step = user_data[user_id].get("step")
    
    if step == "waiting_for_name":
        if text.lower() == "/start":
            return
        
        if not is_valid_name(text):
            await update.message.reply_text(
                "❌ الاسم غير صحيح. أرسلي اسمك الكامل (ثلاثي) على الأقل.\n"
                "مثال: فاطمة محمد الزهراء"
            )
            return
        
        user_data[user_id]["name"] = text
        user_data[user_id]["step"] = "ready"
        await update.message.reply_text(
            f"✅ تم حفظ اسمك: {text}\n"
            f"📤 الآن أرسلي صوتية التسميع 🎙️"
        )
        logger.info(f"📝 تم حفظ اسم الطالبة {user_id}: {text}")
    
    elif step == "ready":
        await update.message.reply_text(
            "📤 أنت الآن في مرحلة إرسال التسميع.\n"
            "الرجاء إرسال **صوتية** 🎙️ وليس نصاً."
        )

async def handle_voice_from_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    
    user_id = update.effective_user.id
    
    if user_id not in user_data or "name" not in user_data[user_id]:
        await update.message.reply_text(
            "⚠️ لم أجد اسمك.\n"
            "أرسلي /start ثم اسمك الكامل أولاً."
        )
        return
    
    name = user_data[user_id]["name"]
    voice = update.message.voice
    
    # إرسال الصوتية إلى مجموعة المعلمات مع معرف الطالبة
    await context.bot.send_voice(
        chat_id=GROUP_ID,
        voice=voice.file_id,
        caption=f"🎙️ تسميع: {name}\n🆔 معرف الطالبة: {user_id}"
    )
    
    await update.message.reply_text(
        "✅ تم إرسال تسميعك إلى المعلمات.\n"
        "ستصلك الملاحظات قريباً."
    )
    logger.info(f"🎤 تم إرسال تسميع الطالبة {name} (ID: {user_id}) إلى المجموعة")

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الردود من المعلمات في المجموعة"""
    
    # التأكد من أن الرسالة من المجموعة الصحيحة
    if update.effective_chat.id != GROUP_ID:
        return
    
    # التأكد من أنها رد على رسالة سابقة
    if not update.message.reply_to_message:
        logger.info("⏭️ رسالة جديدة (ليست رداً) - تم تجاهلها")
        return
    
    logger.info("↩️ تم استلام رد في المجموعة")
    
    original = update.message.reply_to_message
    
    # البحث عن معرف الطالبة من caption
    student_id = None
    student_name = None
    
    if original.caption:
        caption = original.caption
        logger.info(f"📝 نص الـ caption: {caption}")
        
        # محاولة استخراج المعرف
        if "🆔 معرف الطالبة:" in caption:
            try:
                student_id_str = caption.split("🆔 معرف الطالبة:")[1].strip()
                student_id = int(student_id_str)
                logger.info(f"✅ تم استخراج معرف الطالبة: {student_id}")
            except:
                logger.error("فشل استخراج المعرف")
        
        # محاولة استخراج الاسم
        if "🎙️ تسميع:" in caption:
            try:
                student_name = caption.split("🎙️ تسميع:")[1].split("\n")[0].strip()
                logger.info(f"✅ تم استخراج اسم الطالبة: {student_name}")
            except:
                logger.error("فشل استخراج الاسم")
    
    # إذا لم نجد المعرف، نبحث في user_data
    if not student_id and student_name:
        for uid, data in user_data.items():
            if data.get("name") == student_name:
                student_id = uid
                logger.info(f"✅ تم العثور على المعرف من خلال الاسم: {student_id}")
                break
    
    if not student_id:
        await update.message.reply_text(
            "⚠️ لم أتمكن من تحديد الطالبة.\n"
            "تأكدي من الرد على رسالة البوت مباشرة."
        )
        logger.warning("⚠️ لم يتم العثور على الطالبة")
        return
    
    # إرسال الرد إلى الطالبة
    try:
        if update.message.text:
            await context.bot.send_message(
                student_id,
                f"📝 *ملاحظة من المعلمة:*\n\n{update.message.text}",
                parse_mode="Markdown"
            )
            await update.message.reply_text(f"✅ تم إرسال ملاحظتك إلى الطالبة")
            logger.info(f"✅ تم إرسال رد نصي إلى {student_id}")
            
        elif update.message.voice:
            await context.bot.send_voice(
                student_id,
                update.message.voice.file_id,
                caption="🎙️ *ملاحظة صوتية من المعلمة*",
                parse_mode="Markdown"
            )
            await update.message.reply_text(f"✅ تم إرسال الملاحظة الصوتية")
            logger.info(f"✅ تم إرسال رد صوتي إلى {student_id}")
        else:
            logger.info("الرد ليس نصاً ولا صوتية - تم تجاهله")
            
    except Exception as e:
        logger.error(f"💥 فشل إرسال الرد: {e}")
        await update.message.reply_text(f"⚠️ فشل إرسال الملاحظة: {str(e)[:100]}")

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
