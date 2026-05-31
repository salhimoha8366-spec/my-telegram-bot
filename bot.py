import os
import base64
import glob
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
COOKIES_FILE = "cookies.txt"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ── استعادة cookies من متغير البيئة إن وُجد ──
_cookies_b64 = os.getenv("COOKIES_B64")
if _cookies_b64 and not os.path.exists(COOKIES_FILE):
    try:
        with open(COOKIES_FILE, "wb") as _f:
            _f.write(base64.b64decode(_cookies_b64))
        print("✅ cookies.txt تم استعادته من COOKIES_B64")
    except Exception as _e:
        print(f"⚠️ فشل استعادة cookies: {_e}")

# ─────────────────────────────────────────────
QUALITY_OPTIONS = {
    "1080": ("FHD – 1080p", "best[height<=1080][ext=mp4]/best[height<=1080]/best"),
    "720":  ("HD  –  720p", "best[height<=720][ext=mp4]/best[height<=720]/best"),
    "480":  ("SD  –  480p", "best[height<=480][ext=mp4]/best[height<=480]/best"),
    "360":  ("LOW –  360p", "best[height<=360][ext=mp4]/best[height<=360]/best"),
    "audio":("🎵 صوت فقط – MP3", "bestaudio[ext=m4a]/bestaudio"),
}

# ─────────────────────────────────────────────
def base_ydl_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 5,
        "extractor_args": {
            "youtube": {"player_client": ["ios", "web"]},
        },
        "http_headers": {
            "User-Agent": (
                "com.google.ios.youtube/19.09.3 "
                "(iPhone14,3; U; CPU iPhone OS 16_0 like Mac OS X)"
            ),
        },
    }
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
        "prefer_ffmpeg": False,
        "postprocessors": [],
    })
    return opts


# ─────────────────────────────────────────────
def find_downloaded_file(download_dir: str, before_files: set) -> str | None:
    """يجد الملف الجديد الذي تم تحميله بمقارنة الملفات قبل وبعد التحميل"""
    after_files = set(glob.glob(os.path.join(download_dir, "*")))
    new_files = after_files - before_files
    if new_files:
        # أرجع الملف الأحدث
        return max(new_files, key=os.path.getmtime)
    return None


# ─────────────────────────────────────────────
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ أرسل رابط فيديو صحيح.")
        return

    context.user_data["url"] = url
    status = await update.message.reply_text("🔍 جاري قراءة معلومات الفيديو...")

    try:
        with yt_dlp.YoutubeDL(base_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        await status.edit_text(f"❌ تعذّر قراءة الرابط:\n`{e}`", parse_mode="Markdown")
        return

    title    = info.get("title", "فيديو")
    duration = info.get("duration") or 0
    uploader = info.get("uploader", "—")
    mins, secs = divmod(int(duration), 60)
    context.user_data["title"] = title

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
async def handle_quality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    quality_key = query.data.split(":")[1]
    url = context.user_data.get("url")

    if not url:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط من جديد.")
        return

    label, _ = QUALITY_OPTIONS[quality_key]
    await query.edit_message_text(
        f"⏳ جاري التحميل بجودة *{label}* ...", parse_mode="Markdown"
    )

    # تسجيل الملفات الموجودة قبل التحميل
    before_files = set(glob.glob(os.path.join(DOWNLOAD_DIR, "*")))

    template = os.path.join(DOWNLOAD_DIR, "%(id)s_%(height)s.%(ext)s")
    ydl_opts = build_ydl_opts(quality_key, template)
    file_path = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # محاولة 1: من requested_downloads
            downloads = info.get("requested_downloads", [])
            if downloads and downloads[0].get("filepath"):
                file_path = downloads[0]["filepath"]

            # محاولة 2: prepare_filename
            if not file_path or not os.path.exists(file_path):
                file_path = ydl.prepare_filename(info)

        # محاولة 3: مقارنة الملفات قبل وبعد
        if not file_path or not os.path.exists(file_path):
            file_path = find_downloaded_file(DOWNLOAD_DIR, before_files)

        # محاولة 4: أحدث ملف في المجلد
        if not file_path or not os.path.exists(file_path):
            all_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*"))
            if all_files:
                file_path = max(all_files, key=os.path.getmtime)

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

        await query.edit_message_text(f"📤 جاري الرفع... ({size_mb:.1f} MB)")

        ext = os.path.splitext(file_path)[1].lower()
        with open(file_path, "rb") as f:
            if quality_key == "audio" or ext in (".m4a", ".mp3", ".ogg", ".opus", ".webm"):
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
