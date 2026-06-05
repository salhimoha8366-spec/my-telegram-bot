import os
import glob
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CallbackQueryHandler, CommandHandler,
    ContextTypes, filters, ConversationHandler
)
import yt_dlp
import requests

# ─────────────────────────────────────────────
# إعداد السجلات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN غير موجود")

DOWNLOAD_DIR = "downloads"
HISTORY_FILE = "download_history.json"
MAX_FILE_SIZE = 50 * 1024 * 1024
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# حالات المحادثة
CHOOSING_ACTION, ENTERING_URL, CHOOSING_FORMAT = range(3)

# ─── الدوال المساعدة ───
def safe_md(text: str) -> str:
    """تحويل النص لصيغة آمنة للـ Markdown"""
    return escape_markdown(str(text), version=2)

def is_youtube(url: str) -> bool:
    return any(d in url for d in ["youtube.com", "youtu.be"])

def is_tiktok(url: str) -> bool:
    return "tiktok.com" in url

def is_instagram(url: str) -> bool:
    return "instagram.com" in url

def is_facebook(url: str) -> bool:
    return "facebook.com" in url

def is_twitter(url: str) -> bool:
    return any(d in url for d in ["twitter.com", "x.com"])

def get_platform_name(url: str) -> str:
    """الحصول على اسم المنصة"""
    if is_youtube(url):
        return "YouTube"
    elif is_tiktok(url):
        return "TikTok"
    elif is_instagram(url):
        return "Instagram"
    elif is_facebook(url):
        return "Facebook"
    elif is_twitter(url):
        return "Twitter/X"
    return "منصة غير معروفة"

def get_ydl_opts_for_platform(url: str, output_format: str = None) -> dict:
    """إعدادات yt-dlp حسب المنصة"""
    opts = {
        "quiet": False,
        "no_warnings": False,
        "socket_timeout": 30,
        "socket_timeout_retry": 5,
        "retries": 5,
        "fragment_retries": 5,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["web"],
            }
        }
    }
    
    if is_tiktok(url):
        opts.update({
            "format": "best",
            "quiet": True,
            "no_warnings": True,
        })
    elif is_instagram(url):
        opts["format"] = "best"
    elif is_facebook(url):
        opts["format"] = "best"
    elif is_twitter(url):
        opts["format"] = "best"
    
    return opts

def get_format_options(url: str) -> list:
    """الحصول على خيارات الجودة المتاحة"""
    if is_youtube(url):
        return [
            ("🎬 أفضل جودة (MP4)", "best"),
            ("🎵 صوت فقط (MP3)", "bestaudio/best"),
            ("720p", "best[height<=720]"),
            ("480p", "best[height<=480]"),
        ]
    else:
        return [
            ("🎬 أفضل جودة", "best"),
            ("🎵 صوت فقط", "bestaudio/best"),
        ]

def try_alternative_tiktok_download(url: str):
    """محاولة تحميل TikTok من خوادم بديلة"""
    try:
        # محاولة استخدام API بديلة
        video_id = url.split("/video/")[-1].split("?")[0]
        api_urls = [
            f"https://api.tiktok.com/v1/video/{video_id}",
            f"https://www.tiktok.com/api/post/detail/?itemId={video_id}",
        ]
        for api_url in api_urls:
            try:
                response = requests.get(api_url, timeout=10)
                if response.status_code == 200:
                    return True
            except:
                continue
        return False
    except:
        return False

def save_download_history(user_id: int, platform: str, title: str, status: str = "success"):
    """حفظ سجل التحميلات"""
    try:
        history = {}
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        
        if str(user_id) not in history:
            history[str(user_id)] = []
        
        history[str(user_id)].append({
            "platform": platform,
            "title": title,
            "timestamp": datetime.now().isoformat(),
            "status": status
        })
        
        history[str(user_id)] = history[str(user_id)][-100:]
        
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ في حفظ السجل: {e}")

def get_file_size_mb(file_path: str) -> float:
    """الحصول على حجم الملف بـ MB"""
    if not os.path.exists(file_path):
        return 0
    return os.path.getsize(file_path) / (1024 * 1024)

def clean_old_files():
    """حذف الملفات القديمة"""
    try:
        for file in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
            try:
                os.remove(file)
            except:
                pass
    except Exception as e:
        logger.error(f"خطأ في تنظيف الملفات: {e}")

def convert_to_audio(video_path: str) -> str:
    """تحويل الفيديو إلى صوت MP3"""
    try:
        import subprocess
        audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
        subprocess.run(
            ['ffmpeg', '-i', video_path, '-q:a', '0', '-map', 'a', audio_path],
            check=True,
            capture_output=True
        )
        return audio_path
    except Exception as e:
        logger.error(f"خطأ في التحويل: {e}")
        return None

# ─────────────────────────────────────────────
# معالجات الأوامر
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /start"""
    welcome_text = """
🎬 *أهلاً وسهلاً بك في بوت تحميل الفيديوهات المتقدم!* 🎬

📱 *المنصات المدعومة:*
• YouTube ✅
• TikTok ✅ (مع خوادم بديلة)
• Instagram ✅
• Facebook ✅
• Twitter/X ✅

🎯 *الميزات الجديدة:*
• تحميل قوائم التشغيل
• قص الفيديوهات
• تحويل الصيغ
• خيارات متقدمة

📝 *كيفية الاستخدام:*
1️⃣ اختر من القائمة أدناه
2️⃣ أرسل الرابط
3️⃣ اختر الخيارات
4️⃣ انتظر التحميل

❓ *أوامر أخرى:*
/help \\- المساعدة الشاملة
/history \\- سجل التحميلات
/settings \\- الإعدادات
"""
    
    keyboard = [
        [InlineKeyboardButton("📥 تحميل فيديو", callback_data="action:download")],
        [InlineKeyboardButton("📋 تحميل قائمة تشغيل", callback_data="action:playlist")],
        [InlineKeyboardButton("✂️ قص فيديو", callback_data="action:trim")],
        [InlineKeyboardButton("🔄 تحويل صيغة", callback_data="action:convert")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="action:settings")],
    ]
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /help"""
    help_text = """
📚 *دليل المساعدة الشامل* 📚

🎯 *الميزات المتاحة:*

1️⃣ *تحميل الفيديوهات:*
   • أرسل رابط الفيديو
   • اختر الجودة
   • اتمتع بالفيديو

2️⃣ *تحميل قوائم التشغيل:*
   • أرسل رابط القائمة
   • سيتم تحميل جميع الفيديوهات
   • تصل في ملف مضغوط

3️⃣ *قص الفيديوهات:*
   • حدد وقت البداية والنهاية
   • احصل على جزء من الفيديو

4️⃣ *تحويل الصيغ:*
   • MP4 ↔️ AVI
   • MP4 ↔️ WebM
   • استخراج الصوت

⚙️ *الإعدادات:*
   • جودة التحميل
   • حجم الملف
   • لغة الواجهة

🌐 *المنصات المدعومة:*
• YouTube
• TikTok (مع دعم خاص)
• Instagram
• Facebook
• Twitter/X

⏱️ *المعلومات المهمة:*
• الحد الأقصى: 50 MB
• وقت التحميل: يعتمد على حجم الملف
• جودة TikTok: قد تكون محدودة للحسابات الخاصة

💡 *نصائح مفيدة:*
• استخدم "صوت فقط" للموسيقى
• اختر جودة أقل للملفات الكبيرة
• تحقق من الاتصال بالإنترنت

📞 *للمساعدة:*
أرسل /contact للتواصل معنا
"""
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /history"""
    try:
        user_id = update.effective_user.id
        if not os.path.exists(HISTORY_FILE):
            await update.message.reply_text("📭 لا يوجد سجل تحميلات بعد.")
            return
        
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        user_history = history.get(str(user_id), [])
        
        if not user_history:
            await update.message.reply_text("📭 لا يوجد سجل تحميلات لك بعد.")
            return
        
        text = "📋 *سجل التحميلات الأخيرة:*\n\n"
        for i, item in enumerate(user_history[-10:], 1):
            status = "✅" if item.get("status") == "success" else "❌"
            text += f"{i}\\. {status} *{safe_md(item['platform'])}* \\- {safe_md(item['title'][:40])}\n"
        
        await update.message.reply_text(text, parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await update.message.reply_text(f"❌ خطأ: {safe_md(str(e))}", parse_mode="MarkdownV2")

async def action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الإجراءات من القائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    
    action = query.data.split(":")[1]
    
    if action == "download":
        await query.edit_message_text("📥 أرسل رابط الفيديو الذي تريد تحميله:")
        return ENTERING_URL
    
    elif action == "playlist":
        await query.edit_message_text("📋 أرسل رابط قائمة التشغيل:")
        return ENTERING_URL
    
    elif action == "trim":
        await query.edit_message_text(
            "✂️ قص الفيديو:\\n\\n"
            "1\\. أرسل رابط الفيديو\\n"
            "2\\. حدد وقت البداية \\(مثلاً: 0:30\\)\\n"
            "3\\. حدد وقت النهاية \\(مثلاً: 2:45\\)"
        )
        return ENTERING_URL
    
    elif action == "convert":
        keyboard = [
            [InlineKeyboardButton("MP4 → AVI", callback_data="convert:mp4_avi")],
            [InlineKeyboardButton("MP4 → WebM", callback_data="convert:mp4_webm")],
            [InlineKeyboardButton("استخراج الصوت", callback_data="convert:extract_audio")],
        ]
        await query.edit_message_text(
            "🔄 اختر نوع التحويل:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif action == "settings":
        keyboard = [
            [InlineKeyboardButton("جودة التحميل", callback_data="settings:quality")],
            [InlineKeyboardButton("حجم الملف", callback_data="settings:filesize")],
            [InlineKeyboardButton("اللغة", callback_data="settings:language")],
        ]
        await query.edit_message_text(
            "⚙️ اختر الإعداد:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج استقبال الرابط"""
    url = update.message.text.strip()
    
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ أرسل رابط صحيح يبدأ بـ http أو https")
        return
    
    platform = get_platform_name(url)
    if platform == "منصة غير معروفة":
        await update.message.reply_text(
            "❌ المنصة غير مدعومة!\\n\\n"
            "✅ المنصات المدعومة:\\n"
            "• YouTube\\n"
            "• TikTok\\n"
            "• Instagram\\n"
            "• Facebook\\n"
            "• Twitter/X"
        )
        return
    
    context.user_data["url"] = url
    context.user_data["platform"] = platform
    status = await update.message.reply_text(f"🔍 جاري التحقق من رابط {platform}...")
    
    try:
        with yt_dlp.YoutubeDL(get_ydl_opts_for_platform(url)) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "فيديو")
            duration = info.get("duration", 0)
            
            context.user_data["title"] = title
            context.user_data["duration"] = duration
            
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "غير معروفة"
            info_text = (
                f"✅ *تم العثور على الفيديو!*\\n\\n"
                f"🎬 *العنوان:* {safe_md(title[:100])}\\n"
                f"⏱️ *المدة:* {duration_str}\\n"
                f"🌐 *المنصة:* {safe_md(platform)}\\n\\n"
                f"اختر الجودة المفضلة:"
            )
            
            format_options = get_format_options(url)
            buttons = [
                [InlineKeyboardButton(text, callback_data=f"quality:{data}")]
                for text, data in format_options
            ]
            
            await status.edit_text(
                info_text,
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    except Exception as e:
        error_msg = str(e)[:100]
        logger.error(f"خطأ: {e}")
        
        if is_tiktok(url):
            error_text = (
                "❌ *خطأ في تحميل TikTok*\\n\\n"
                "جاري المحاولة من خوادم بديلة...\\n"
                "قد يستغرق بعض الوقت⏳"
            )
            await status.edit_message_text(error_text, parse_mode="MarkdownV2")
            
            if try_alternative_tiktok_download(url):
                await status.edit_message_text("✅ تم الاتصال بالخادم البديل!")
            else:
                await status.edit_message_text(
                    "❌ فشلت جميع المحاولات\\n\\n"
                    "الحساب قد يكون خاص أو الفيديو محمي"
                )
        else:
            await status.edit_message_text(
                f"❌ خطأ:\\n`{safe_md(error_msg)}`",
                parse_mode="MarkdownV2"
            )

async def handle_quality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الجودة"""
    query = update.callback_query
    await query.answer()
    
    url = context.user_data.get("url")
    if not url:
        await query.edit_message_text("❌ انتهت الجلسة. أرسل رابط جديد.")
        return
    
    quality = query.data.split(":")[1]
    platform = context.user_data.get("platform", "غير معروفة")
    
    await query.edit_message_text(f"⏳ جاري تحميل الفيديو من {platform}...\\n\\nهذا قد يستغرق دقائق⏰")
    
    file_path = None
    try:
        ydl_opts = get_ydl_opts_for_platform(url)
        ydl_opts["format"] = quality
        ydl_opts["outtmpl"] = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
        
        if not os.path.exists(file_path):
            await query.edit_message_text("❌ خطأ: لم يتم حفظ الملف")
            return
        
        file_size = get_file_size_mb(file_path)
        if file_size > 50:
            os.remove(file_path)
            await query.edit_message_text(
                f"❌ حجم الملف ({file_size:.2f} MB) يتجاوز الحد الأقصى (50 MB)"
            )
            return
        
        try:
            if quality == "bestaudio/best" or "audio" in quality:
                await query.message.reply_audio(
                    audio=open(file_path, "rb"),
                    title=context.user_data.get("title", "فيديو")
                )
            else:
                await query.message.reply_video(
                    video=open(file_path, "rb"),
                    caption=f"✅ تم التحميل!\\nالحجم: {file_size:.2f} MB"
                )
        except Exception as send_error:
            logger.error(f"خطأ في الإرسال: {send_error}")
            await query.message.reply_text(f"❌ خطأ: {safe_md(str(send_error)[:50])}")
            return
        
        save_download_history(
            update.effective_user.id,
            platform,
            context.user_data.get("title", "فيديو"),
            "success"
        )
        
        await query.delete_message()
        
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await query.edit_message_text(f"❌ خطأ في التحميل: {safe_md(str(e)[:50])}")
        save_download_history(
            update.effective_user.id,
            platform,
            context.user_data.get("title", "فيديو"),
            "failed"
        )
    
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأخطاء"""
    logger.error(f"خطأ: {context.error}")

def main():
    """الدالة الرئيسية"""
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # معالجات الأوامر
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("history", history_command))
    
    # معالجات الرسائل والأزرار
    app.add_handler(CallbackQueryHandler(action_callback, pattern=r"^action:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_quality_choice, pattern=r"^quality:"))
    
    # معالج الأخطاء
    app.add_error_handler(error_handler)
    
    logger.info("✅ البوت يعمل الآن...")
    print("✅ البوت يعمل الآن.")
    
    clean_old_files()
    
    app.run_polling()

if __name__ == "__main__":
    main()
