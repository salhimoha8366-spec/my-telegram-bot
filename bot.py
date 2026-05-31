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

_cookies_b64 = os.getenv("COOKIES_B64")
if _cookies_b64 and not os.path.exists(COOKIES_FILE):
    try:
        with open(COOKIES_FILE, "wb") as _f:
            _f.write(base64.b64decode(_cookies_b64))
        print("✅ cookies.txt تم استعادته")
    except Exception as _e:
        print(f"⚠️ فشل استعادة cookies: {_e}")

# ─────────────────────────────────────────────
QUALITY_OPTIONS = {
    "1080": "FHD – 1080p",
    "720":  "HD  –  720p",
    "480":  "SD  –  480p",
    "360":  "LOW –  360p",
    "audio":"🎵 صوت فقط",
}

def get_format(quality_key: str, is_youtube: bool) -> str:
    """
    يوتيوب: يدعم فلتر الجودة
    باقي المنصات: best فقط بدون فلتر
    """
    if quality_key == "audio":
        return "bestaudio[ext=m4a]/bestaudio"

    if is_youtube:
        h = quality_key  # 1080, 720, 480, 360
        return (
            f"best[height<={h}][ext=mp4]"
            f"/best[height<={h}]"
            f"/best[ext=mp4]"
            f"/best"
        )
    else:
        # منصات أخرى: خذ الأفضل المتاح مباشرة
        return "best[ext=mp4]/best"

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
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        },
    }
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    return opts


def is_youtube_url(url: str) -> bool:
    return any(d in url for d in ["youtube.com", "youtu.be"])


def find_new_file(before: set) -> str | None:
    after = set(glob.glob(os.path.join(DOWNLOAD_DIR, "*")))
    new = after - before
    if new:
        return max(new, key=os.path.getmtime)
    if after:
        return max(after, key=os.path.getmtime)
    return None


# ─────────────────────────────────────────────
async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ أرسل رابط فيديو صحيح.")
        return

    context.user_data["url"] = url
    context.user_data["is_youtube"] = is_youtube_url(url)
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

    # إذا مش يوتيوب — أزرار مبسطة
    if not context.user_data["is_youtube"]:
        buttons = [
            [InlineKeyboardButton("⬇️ تحميل الفيديو", callback_data="quality:best")],
            [InlineKeyboardButton("🎵 صوت فقط", callback_data="quality:audio")],
        ]
    else:
        buttons = [
            [InlineKeyboardButton(label, callback_data=f"quality:{key}")]
            for key, label in QUALITY_OPTIONS.items()
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
    url         = context.user_data.get("url")
    is_yt       = context.user_data.get("is_youtube", False)

    if not url:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط من جديد.")
        return

    label = QUALITY_OPTIONS.get(quality_key, "الجودة المتاحة")
    await query.edit_message_text(
        f"⏳ جاري التحميل بجودة *{label}* ...", parse_mode="Markdown"
    )

    before_files = set(glob.glob(os.path.join(DOWNLOAD_DIR, "*")))
    fmt          = get_format(quality_key, is_yt)
    template     = os.path.join(DOWNLOAD_DIR, "%(id)s_%(height)s.%(ext)s")

    opts = base_ydl_opts()
    opts.update({
        "format": fmt,
        "outtmpl": template,
        "noplaylist": True,
        "prefer_ffmpeg": False,
        "postprocessors": [],
    })

    file_path = None

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # محاولة 1: requested_downloads
            downloads = info.get("requested_downloads", [])
            if downloads and downloads[0].get("filepath"):
                fp = downloads[0]["filepath"]
                if os.path.exists(fp):
                    file_path = fp

            # محاولة 2: prepare_filename
            if not file_path:
                fp = ydl.prepare_filename(info)
                if os.path.exists(fp):
                    file_path = fp

        # محاولة 3: مقارنة الملفات
        if not file_path:
            file_path = find_new_file(before_files)

        if not file_path or not os.path.exists(file_path):
            await query.edit_message_text("❌ لم يُعثر على الملف.")
            return

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            os.remove(file_path)
            await query.edit_message_text(
                f"❌ الملف كبير جداً ({size_mb:.1f} MB)\nجرّب جودة أقل 👇",
                parse_mode="Markdown"
            )
            return

        await query.edit_message_text(f"📤 جاري الرفع... ({size_mb:.1f} MB)")

        ext = os.path.splitext(file_path)[1].lower()
        with open(file_path, "rb") as f:
            if quality_key == "audio" or ext in (".m4a", ".mp3", ".ogg", ".opus"):
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
