import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

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

# تخزين مؤقت لانتظار رد المعلمة
waiting_for_reply = {}  # {teacher_id: {"student_id": xxx, "type": "text" or "voice"}}

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
# أوامر البوت للطالبات
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
    
    # إنشاء الأزرار للمعلمة
    keyboard = [
        [
            InlineKeyboardButton("✏️ رد نصي", callback_data=f"reply_text_{user_id}_{name}"),
            InlineKeyboardButton("🎙️ رد صوتي", callback_data=f"reply_voice_{user_id}_{name}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # إرسال الصوتية إلى مجموعة المعلمات مع الأزرار
    await context.bot.send_voice(
        chat_id=GROUP_ID,
        voice=voice.file_id,
        caption=f"🎙️ تسميع الطالبة: {name}\n🆔 معرفها: {user_id}\n\nاختر طريقة الرد:",
        reply_markup=reply_markup
    )
    
    await update.message.reply_text(
        "✅ تم إرسال تسميعك إلى المعلمات.\n"
        "ستصلك الملاحظات قريباً."
    )
    logger.info(f"🎤 تم إرسال تسميع الطالبة {name} (ID: {user_id}) إلى المجموعة مع أزرار")

# ========================
# معالجة أزرار المعلمات
# ========================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    teacher_id = update.effective_user.id
    teacher_name = update.effective_user.first_name
    
    # استخراج المعلومات من البيانات
    parts = data.split("_")
    if len(parts) >= 3:
        reply_type = parts[1]  # text or voice
        student_id = int(parts[2])
        
        # محاولة استخراج الاسم (قد يحتوي على مسافات)
        student_name = "_".join(parts[3:]) if len(parts) > 3 else "الطالبة"
        
        # تخزين أن هذه المعلمة بصدد الرد على طالبة معينة
        waiting_for_reply[teacher_id] = {
            "student_id": student_id,
            "student_name": student_name,
            "type": reply_type
        }
        
        if reply_type == "text":
            await query.edit_message_caption(
                caption=f"🎙️ تسميع الطالبة: {student_name}\n\n✏️ **الآن اكتبي ردك النصي** (أرسلي الرسالة هنا مباشرة)",
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                teacher_id,
                f"✏️ أرسلي الرد النصي للطالبة {student_name}:"
            )
        else:
            await query.edit_message_caption(
                caption=f"🎙️ تسميع الطالبة: {student_name}\n\n🎙️ **الآن أرسلي رداً صوتياً**",
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                teacher_id,
                f"🎙️ أرسلي الرد الصوتي للطالبة {student_name}:"
            )
        
        logger.info(f"📝 المعلمة {teacher_name} بدأت الرد على {student_name}")

# ========================
# استلام الرد من المعلمة (بعد الضغط على الزر)
# ========================
async def handle_teacher_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teacher_id = update.effective_user.id
    
    if teacher_id not in waiting_for_reply:
        return
    
    reply_info = waiting_for_reply[teacher_id]
    student_id = reply_info["student_id"]
    student_name = reply_info["student_name"]
    reply_type = reply_info["type"]
    
    # إرسال الرد إلى الطالبة
    try:
        if reply_type == "text":
            # رد نصي
            text = update.message.text
            await context.bot.send_message(
                student_id,
                f"📝 *ملاحظة من المعلمة:*\n\n{text}",
                parse_mode="Markdown"
            )
            await update.message.reply_text(f"✅ تم إرسال ملاحظتك إلى {student_name}")
            logger.info(f"✅ تم إرسال رد نصي إلى {student_name} (ID: {student_id})")
            
        elif reply_type == "voice" and update.message.voice:
            # رد صوتي
            voice = update.message.voice
            await context.bot.send_voice(
                student_id,
                voice.file_id,
                caption="🎙️ *ملاحظة صوتية من المعلمة*",
                parse_mode="Markdown"
            )
            await update.message.reply_text(f"✅ تم إرسال الملاحظة الصوتية إلى {student_name}")
            logger.info(f"✅ تم إرسال رد صوتي إلى {student_name} (ID: {student_id})")
        else:
            await update.message.reply_text("⚠️ يرجى إرسال رد بالطريقة المطلوبة (نص أو صوت)")
            return
        
        # حذف المعلمة من قائمة الانتظار
        del waiting_for_reply[teacher_id]
        
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
    
    # أوامر الطالبات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_from_student))
    
    # معالجة الأزرار وردود المعلمات
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.ALL, handle_teacher_reply))
    
    logger.info("🚀 البوت بدأ العمل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
