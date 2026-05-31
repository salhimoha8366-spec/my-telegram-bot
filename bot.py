import os
import yt_dlp
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters
)

# سنقوم بجلب التوكن من إعدادات البيئة في موقع الاستضافة
BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    msg = await update.message.reply_text("⏳ جاري تحميل الفيديو...")

    try:
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": "downloads/%(title)s.%(ext)s",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
        }

        os.makedirs("downloads", exist_ok=True)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            
            # التأكد من المسار الصحيح للملف بعد التحميل
            if not file_path.endswith(".mp4"):
                base = os.path.splitext(file_path)[0]
                mp4_file = base + ".mp4"
                if os.path.exists(mp4_file):
                    file_path = mp4_file

        await msg.edit_text("📤 جاري رفع الفيديو...")

        with open(file_path, "rb") as video:
            await update.message.reply_video(
                video=video,
                supports_streaming=True
            )

        os.remove(file_path)
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ خطأ في تحميل الفيديو:\n{str(e)}")

async def main():
    if not BOT_TOKEN:
        print("خطأ: يرجى ضبط متغير البيئة BOT_TOKEN")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # حذف الـ Webhook القديم قبل بدء الـ Polling لحل مشكلة الـ Conflict
    await app.bot.delete_webhook(drop_pending_updates=True)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    print("Bot Started...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())