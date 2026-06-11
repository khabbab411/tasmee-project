import json
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"
GROUP_ID = -1003846785454

USERS_FILE = "users.json"
MAP_FILE = "message_map.json"

def load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except:
        return default

def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل اسمك الكامل ليتم تسجيلك.")

async def save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    users = load_json(USERS_FILE, {})
    uid = str(update.effective_user.id)

    if uid not in users:
        users[uid] = {
            "name": update.message.text.strip(),
            "username": update.effective_user.username or ""
        }
        save_json(USERS_FILE, users)
        await update.message.reply_text("تم حفظ اسمك. يمكنك الآن إرسال التسميع الصوتي.")
        return

async def voice_from_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == GROUP_ID:
        return

    users = load_json(USERS_FILE, {})
    uid = str(update.effective_user.id)

    if uid not in users:
        await update.message.reply_text("أرسل /start ثم اسمك الكامل أولاً.")
        return

    student = users[uid]

    sent = await context.bot.send_message(
        GROUP_ID,
        f"📖 تسميع جديد\n\nالطالبة: {student['name']}\nالمعرف: @{student['username']}" if student['username'] else f"📖 تسميع جديد\n\nالطالبة: {student['name']}"
    )

    forwarded = await context.bot.forward_message(
        GROUP_ID,
        update.effective_chat.id,
        update.message.message_id
    )

    mapping = load_json(MAP_FILE, {})
    mapping[str(forwarded.message_id)] = int(uid)
    save_json(MAP_FILE, mapping)

async def teacher_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return

    if not update.message.reply_to_message:
        return

    mapping = load_json(MAP_FILE, {})
    target = mapping.get(str(update.message.reply_to_message.message_id))

    if not target:
        return

    if update.message.text:
        await context.bot.send_message(target, f"📝 رد المعلمة:\n\n{update.message.text}")

    elif update.message.voice:
        await context.bot.send_voice(target, update.message.voice.file_id)

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_name))
    app.add_handler(MessageHandler(filters.VOICE & ~filters.Chat(GROUP_ID), voice_from_student))
    app.add_handler(MessageHandler(filters.ALL & filters.Chat(GROUP_ID), teacher_reply))

    app.run_polling()

if __name__ == "__main__":
    main()
