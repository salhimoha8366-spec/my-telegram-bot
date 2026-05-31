import os
import yt_dlp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN غير موجود في Variables")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ أرسل رابط فيديو صحيح.")
        return

    status = await update.message.reply_text("⏳ جاري التحميل...")

    try:
        os.makedirs("downloads", exist_ok=True)

        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": "downloads/%(title)s.%(ext)s",
            "noplaylist": True,
            "quiet": True,
            # هذا السطر للتمويه لكي لا يكتشف يوتيوب أنه بوت
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # تحميل المعلومات والملف
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            base_name = os.path.splitext(file_path)[0]
            if os.path.exists(base_name + ".mp4"):
                file_path = base_name + ".mp4"

        await status.edit_text("📤 جاري رفع الفيديو...")

        with open(file_path, "rb") as video:
            await update.message.reply_video(
                video=video,
                supports_streaming=True
            )

        # مسح الملف بعد الإرسال لتوفير المساحة في السيرفر
        if os.path.exists(file_path):
            os.remove(file_path)

        await status.delete()

    except Exception as e:
        await status.edit_text(f"❌ حدث خطأ أثناء التحميل:\n`{e}`", parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))
    print("✅ Bot Started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()