import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN غير موجود في متغيرات البيئة")

MAX_FILE_SIZE_MB = 50
DOWNLOAD_DIR = "downloads"
COOKIES_FILE = "cookies.txt"  # ← ملف الكوكيز من يوتيوب
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# خيارات الجودة
QUALITY_OPTIONS = {
    "1080": ("FHD – 1080p", "bestvideo[height<=1080]+bestaudio/best[height<=1080]"),
    "720":  ("HD  –  720p", "bestvideo[height<=720]+bestaudio/best[height<=720]"),
    "480":  ("SD  –  480p", "bestvideo[height<=480]+bestaudio/best[height<=480]"),
    "360":  ("LOW –  360p", "bestvideo[height<=360]+bestaudio/best[height<=360]"),
    "audio":("🎵 صوت فقط – MP3", "bestaudio/best"),
}

# ─────────────────────────────────────────────
# إعدادات yt_dlp الأساسية المشتركة
def base_ydl_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 5,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    # إضافة الكوكيز إذا كان الملف موجوداً
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    return opts


def build_ydl_opts(quality_key: str, output_template: str) -> dict:
    _, fmt = QUALITY_OPTIONS[quality_key]
    opts = base_ydl_opts()
    opts.update({
        "format": fmt,
        "outtmpl": output_template,
        "noplaylist": True,
    })
    if quality_key == "audio":
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        opts["merge_output_format"] = "mp4"
    return opts


# ─────────────────────────────────────────────
# المرحلة 1 – استقبال الرابط وعرض قائمة الجودة
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ أرسل رابط فيديو صحيح (يبدأ بـ http أو https).")
        return

    context.user_data["url"] = url
    status = await update.message.reply_text("🔍 جاري قراءة معلومات الفيديو...")

    try:
        ydl_info_opts = base_ydl_opts()
        with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        await status.edit_text(f"❌ تعذّر قراءة الرابط:\n`{e}`", parse_mode="Markdown")
        return

    title    = info.get("title", "فيديو")
    duration = info.get("duration") or 0
    uploader = info.get("uploader", "—")
    mins, secs = divmod(int(duration), 60)
    context.user_data["title"] = title

    # بناء لوحة الجودة
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"quality:{key}")]
        for key, (label, _) in QUALITY_OPTIONS.items()
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    text = (
        f"🎬 *{title[:60]}*\n"
        f"👤 {uploader}   ⏱ {mins}:{secs:02d}\n\n"
        f"اختر جودة التحميل:"
    )
    await status.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")


# ─────────────────────────────────────────────
# المرحلة 2 – تحميل الفيديو بعد اختيار الجودة
async def handle_quality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    quality_key = query.data.split(":")[1]
    url = context.user_data.get("url")

    if not url:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط من جديد.")
        return

    label, _ = QUALITY_OPTIONS[quality_key]
    await query.edit_message_text(f"⏳ جاري التحميل بجودة *{label}* ...", parse_mode="Markdown")

    template = os.path.join(DOWNLOAD_DIR, "%(id)s_%(height)s.%(ext)s")
    ydl_opts = build_ydl_opts(quality_key, template)
    file_path = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            if quality_key == "audio":
                # البحث عن ملف mp3 في مجلد التحميل
                vid_id = info.get("id", "")
                mp3_candidates = [
                    f for f in os.listdir(DOWNLOAD_DIR)
                    if f.startswith(vid_id) and f.endswith(".mp3")
                ]
                if mp3_candidates:
                    file_path = os.path.join(DOWNLOAD_DIR, mp3_candidates[0])
                else:
                    file_path = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"
            else:
                downloads = info.get("requested_downloads", [{}])
                file_path = downloads[0].get("filepath") if downloads else None
                if not file_path:
                    file_path = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp4"

        # التحقق من وجود الملف
        if not file_path or not os.path.exists(file_path):
            await query.edit_message_text("❌ لم يُعثر على الملف بعد التحميل.")
            return

        # التحقق من الحجم
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            os.remove(file_path)
            await query.edit_message_text(
                f"❌ حجم الملف *{size_mb:.1f} MB* يتجاوز حد تيليغرام ({MAX_FILE_SIZE_MB} MB).\n"
                f"جرّب جودة أقل 👇",
                parse_mode="Markdown"
            )
            return

        # الرفع
        await query.edit_message_text(f"📤 جاري الرفع... ({size_mb:.1f} MB)")

        with open(file_path, "rb") as f:
            if quality_key == "audio":
                await query.message.reply_audio(
                    audio=f,
                    title=info.get("title", "audio")[:64],
                    read_timeout=180,
                    write_timeout=180,
                )
            else:
                await query.message.reply_video(
                    video=f,
                    supports_streaming=True,
                    read_timeout=180,
                    write_timeout=180,
                )

        os.remove(file_path)
        await query.delete_message()

    except Exception as e:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        await query.edit_message_text(
            f"❌ حدث خطأ:\n`{e}`", parse_mode="Markdown"
        )


# ─────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_quality_choice, pattern=r"^quality:"))
    print("✅ Bot Started — Waiting for links...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
