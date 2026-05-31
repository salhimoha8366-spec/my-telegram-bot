import os
import yt_dlp
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters
)

BOT_TOKEN = "8327603349:AAF48wieDTXW0AgdUs3qNtq8AallHS9VjU4"


async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    msg = await update.message.reply_text("⏳ جاري تحميل الفيديو...")

    try:
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "outtmpl": "downloads/%(title)s.%(ext)s",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
        }

        os.makedirs("downloads", exist_ok=True)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

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
        await msg.edit_text(f"❌ خطأ:\n{e}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, download_video)
    )

    print("Bot Started...")
    app.run_polling()


if __name__ == "__main__":
    main()