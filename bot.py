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
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# خيارات الجودة
QUALITY_OPTIONS = {
    "2160": ("4K  – 2160p", "bestvideo[height<=2160]+bestaudio/best[height<=2160]"),
    "1080": ("FHD – 1080p", "bestvideo[height<=1080]+bestaudio/best[height<=1080]"),
    "720":  ("HD  –  720p", "bestvideo[height<=720]+bestaudio/best[height<=720]"),
    "480":  ("SD  –  480p", "bestvideo[height<=480]+bestaudio/best[height<=480]"),
    "360":  ("LOW –  360p", "bestvideo[height<=360]+bestaudio/best[height<=360]"),
    "audio":("🎵 صوت فقط (MP3)", "bestaudio/best"),
}

# ─────────────────────────────────────────────
# مساعد: إعدادات yt_dlp
def build_ydl_opts(quality_key: str, output_template: str) -> dict:
    _, fmt = QUALITY_OPTIONS[quality_key]
    opts = {
        "format": fmt,
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4" if quality_key != "audio" else None,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "socket_timeout": 30,
        "retries": 3,
    }
    if quality_key == "audio":
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
        opts.pop("merge_output_format")
    return opts


# ─────────────────────────────────────────────
# المرحلة 1 – استقبال الرابط وعرض قائمة الجودة
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.startswith(("http://", "https://")):
        await update.message.reply_text(
            "❌ أرسل رابط فيديو صحيح (يبدأ بـ http أو https)."
        )
        return

    # حفظ الرابط مؤقتاً
    context.user_data["url"] = url

    # استخراج معلومات الفيديو أولاً
    status = await update.message.reply_text("🔍 جاري قراءة معلومات الفيديو...")
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        await status.edit_text(f"❌ تعذّر قراءة الرابط:\n`{e}`", parse_mode="Markdown")
        return

    title = info.get("title", "فيديو")
    duration = info.get("duration", 0)
    uploader = info.get("uploader", "—")

    mins, secs = divmod(duration, 60)
    context.user_data["title"] = title

    # بناء لوحة الجودة
    buttons = []
    for key, (label, _) in QUALITY_OPTIONS.items():
        buttons.append([InlineKeyboardButton(label, callback_data=f"quality:{key}")])

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
    await query.edit_message_text(f"⏳ جاري تحميل الفيديو بجودة **{label}** ...", parse_mode="Markdown")

    # تحديد مسار الملف
    ext = "%(ext)s" if quality_key != "audio" else "mp3"
    template = os.path.join(DOWNLOAD_DIR, f"%(id)s_%(height)s.{ext}")
    ydl_opts = build_ydl_opts(quality_key, template)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # تحديد مسار الملف الفعلي
            if quality_key == "audio":
                file_path = os.path.join(
                    DOWNLOAD_DIR,
                    f"{info['id']}_None.mp3"
                )
                # fallback إذا اختلف الاسم
                if not os.path.exists(file_path):
                    file_path = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"
            else:
                downloads = info.get("requested_downloads", [{}])
                file_path = downloads[0].get("filepath") if downloads else None
                if not file_path:
                    base = ydl.prepare_filename(info).rsplit(".", 1)[0]
                    file_path = base + ".mp4"

        # التحقق من وجود الملف
        if not file_path or not os.path.exists(file_path):
            await query.edit_message_text("❌ لم يُعثر على الملف بعد التحميل.")
            return

        # التحقق من الحجم
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            os.remove(file_path)
            await query.edit_message_text(
                f"❌ حجم الملف ({size_mb:.1f} MB) يتجاوز حد تيليغرام ({MAX_FILE_SIZE_MB} MB).\n"
                f"جرّب جودة أقل."
            )
            return

        # الرفع
        await query.edit_message_text(f"📤 جاري رفع الملف ({size_mb:.1f} MB) ...")

        with open(file_path, "rb") as f:
            if quality_key == "audio":
                await query.message.reply_audio(
                    audio=f,
                    title=info.get("title", "audio"),
                    read_timeout=120,
                    write_timeout=120,
                )
            else:
                await query.message.reply_video(
                    video=f,
                    supports_streaming=True,
                    read_timeout=120,
                    write_timeout=120,
                )

        os.remove(file_path)
        await query.delete_message()

    except Exception as e:
        # تنظيف في حالة الخطأ
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        await query.edit_message_text(
            f"❌ حدث خطأ أثناء التحميل:\n`{e}`", parse_mode="Markdown"
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
