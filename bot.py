import os
import glob
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CallbackQueryHandler, 
    ContextTypes, filters,
)
import yt_dlp

# ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN غير موجود")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ─── الدوال المساعدة ───
def safe_md(text: str) -> str:
    return escape_markdown(str(text), version=2)

def is_youtube(url: str) -> bool:
    return any(d in url for d in ["youtube.com", "youtu.be"])

def is_tiktok(url: str) -> bool:
    return "tiktok.com" in url

def base_ydl_opts(url: str = "") -> dict:
    opts = {"quiet": True, "no_warnings": True}
    if is_tiktok(url):
        opts["format"] = "best"
    return opts

def get_format(quality_key: str, url: str) -> str:
    if quality_key == "audio": return "bestaudio/best"
    return "best"

# ─────────────────────────────────────────────
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ أرسل رابط فيديو صحيح.")
        return

    context.user_data["url"] = url
    status = await update.message.reply_text("🔍 جاري المعالجة...")

    try:
        with yt_dlp.YoutubeDL(base_ydl_opts(url)) as ydl:
            info = ydl.extract_info(url, download=False)
            context.user_data["title"] = info.get("title", "فيديو")
            await status.edit_text(f"✅ تم العثور على: *{safe_md(context.user_data['title'][:50])}*\nاختر الجودة:", parse_mode="MarkdownV2", 
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("تحميل", callback_data="quality:best")]]))
    except Exception as e:
        await status.edit_text(f"❌ خطأ:\n`{safe_md(str(e)[:50])}`", parse_mode="MarkdownV2")

async def handle_quality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    url = context.user_data.get("url")
    if not url:
        await query.edit_message_text("❌ انتهت الجلسة.")
        return

    await query.edit_message_text("⏳ جاري التحميل...")
    
    file_path = None
    try:
        with yt_dlp.YoutubeDL(base_ydl_opts(url)) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
        
        await query.message.reply_video(video=open(file_path, "rb"))
        os.remove(file_path)
        await query.delete_message()
    except Exception as e:
        if file_path and os.path.exists(file_path): os.remove(file_path)
        await query.edit_message_text(f"❌ خطأ في التحميل:\n`{safe_md(str(e)[:50])}`", parse_mode="MarkdownV2")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_quality_choice, pattern=r"^quality:"))
    print("✅ البوت يعمل الآن.")
    app.run_polling()

if __name__ == "__main__":
    main()
