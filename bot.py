import os
import base64
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

MAX_FILE_SIZE_MB = 50
DOWNLOAD_DIR = "downloads"
COOKIES_FILE = "cookies.txt"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ─── دالة مساعدة لتنسيق النصوص بأمان ───
def safe_md(text: str) -> str:
    return escape_markdown(str(text), version=2)

# ─────────────────────────────────────────────
# [بقية الدوال المساعدة مثل is_youtube, is_tiktok, base_ydl_opts, get_format هنا]
# ...

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ أرسل رابط فيديو صحيح.")
        return

    context.user_data["url"] = url
    status = await update.message.reply_text("🔍 جاري قراءة معلومات الفيديو...")

    try:
        with yt_dlp.YoutubeDL(base_ydl_opts(url)) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        await status.edit_text(f"❌ تعذّر قراءة الرابط:\n`{safe_md(str(e))}`", parse_mode="MarkdownV2")
        return

    title = info.get("title", "فيديو")
    duration = info.get("duration") or 0
    uploader = info.get("uploader", "—")
    mins, secs = divmod(int(duration), 60)
    
    safe_title = safe_md(title[:60])
    
    if is_youtube(url):
        buttons = [[InlineKeyboardButton(label, callback_data=f"quality:{key}")] for key, label in QUALITY_OPTIONS.items()]
    else:
        platform = "TikTok 🚫💧" if is_tiktok(url) else "الفيديو"
        buttons = [[InlineKeyboardButton(f"⬇️ تحميل {platform}", callback_data="quality:best")], [InlineKeyboardButton("🎵 صوت فقط", callback_data="quality:audio")]]

    keyboard = InlineKeyboardMarkup(buttons)
    text = f"🎬 *{safe_title}*\n👤 {safe_md(uploader)}   ⏱ {mins}:{secs:02d}\n\nاختر طريقة التحميل:"
    
    await status.edit_text(text, reply_markup=keyboard, parse_mode="MarkdownV2")

async def handle_quality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    quality_key = query.data.split(":")[1]
    url = context.user_data.get("url")

    if not url:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط من جديد.")
        return

    label = QUALITY_OPTIONS.get(quality_key, "الجودة المتاحة")
    await query.edit_message_text(f"⏳ جاري التحميل *{safe_md(label)}* ...", parse_mode="MarkdownV2")

    file_path = None
    try:
        before_files = set(glob.glob(os.path.join(DOWNLOAD_DIR, "*")))
        fmt = get_format(quality_key, url)
        template = os.path.join(DOWNLOAD_DIR, "%(id)s_%(height)s.%(ext)s")

        opts = base_ydl_opts(url)
        opts.update({"format": fmt, "outtmpl": template, "noplaylist": True, "prefer_ffmpeg": False, "postprocessors": []})

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloads = info.get("requested_downloads", [])
            file_path = downloads[0]["filepath"] if downloads and downloads[0].get("filepath") else ydl.prepare_filename(info)

        if not file_path or not os.path.exists(file_path):
            await query.edit_message_text("❌ لم يُعثر على الملف.")
            return

        # ... (أضف هنا منطق الرفع وإرسال الملف الذي كان لديك سابقاً) ...
        # تذكر استخدام safe_md() عند إرسال أي نصوص
        
    except Exception as e:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        
        await query.edit_message_text(
            f"❌ حدث خطأ تقني:\n`{safe_md(str(e)[:100])}`", 
            parse_mode="MarkdownV2"
        )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_quality_choice, pattern=r"^quality:"))
    print("✅ البوت يعمل الآن...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
