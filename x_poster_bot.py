#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت النشر التلقائي على X (Twitter)
يدعم النصوص والصور والفيديوهات
"""

import os
import json
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

import tweepy
import feedparser
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.helpers import escape_markdown

# ─────────────────────────────────────────────
# إعداد السجلات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# متغيرات البيئة
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

if not all([BOT_TOKEN, X_BEARER_TOKEN]):
    raise ValueError("❌ التوكنات المطلوبة غير موجودة")

# ─────────────────────────────────────────────
# الثوابت
CONTENT_DB = "content_database.json"
SCHEDULE_DB = "schedule.json"
POSTED_LOG = "posted_content.json"
MAX_TEXT_LENGTH = 280

# ─────────────────────────────────────────────
# نماذج البيانات
@dataclass
class Content:
    """نموذج المحتوى"""
    text: str
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    hashtags: List[str] = None
    source: str = "manual"
    id: Optional[str] = None

    def __post_init__(self):
        if self.hashtags is None:
            self.hashtags = []
        if self.id is None:
            self.id = str(int(datetime.now().timestamp() * 1000))

    def to_dict(self) -> dict:
        """تحويل إلى قاموس"""
        return {
            'text': self.text,
            'image_url': self.image_url,
            'video_url': self.video_url,
            'hashtags': self.hashtags,
            'source': self.source,
            'id': self.id
        }

# ─────────────────────────────────────────────
# فئة إدارة قاعدة البيانات
class ContentDatabase:
    """إدارة قاعدة بيانات المحتوى"""
    
    def __init__(self, db_file: str = CONTENT_DB):
        self.db_file = db_file
        self.load_database()
    
    def load_database(self):
        """تحميل قاعدة البيانات"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except:
                self.data = {'contents': []}
        else:
            self.data = {'contents': []}
    
    def save_database(self):
        """حفظ قاعدة البيانات"""
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ قاعدة البيانات: {e}")
    
    def add_content(self, content: Content):
        """إضافة محتوى جديد"""
        self.data['contents'].append(content.to_dict())
        self.save_database()
        logger.info(f"تم إضافة محتوى جديد: {content.id}")
    
    def get_all_content(self) -> List[Content]:
        """الحصول على جميع المحتويات"""
        contents = []
        for item in self.data.get('contents', []):
            content = Content(
                text=item['text'],
                image_url=item.get('image_url'),
                video_url=item.get('video_url'),
                hashtags=item.get('hashtags', []),
                source=item.get('source', 'manual'),
                id=item.get('id')
            )
            contents.append(content)
        return contents
    
    def get_random_content(self) -> Optional[Content]:
        """الحصول على محتوى عشوائي"""
        contents = self.get_all_content()
        if contents:
            return random.choice(contents)
        return None
    
    def delete_content(self, content_id: str):
        """حذف محتوى"""
        self.data['contents'] = [
            c for c in self.data['contents'] if c.get('id') != content_id
        ]
        self.save_database()
        logger.info(f"تم حذف المحتوى: {content_id}")
    
    def count_content(self) -> int:
        """عد المحتويات"""
        return len(self.data.get('contents', []))

# ─────────────────────────────────────────────
# فئة إدارة X (Twitter)
class XPoster:
    """إدارة النشر على X"""
    
    def __init__(self):
        """تهيئة عميل X"""
        try:
            self.auth = tweepy.OAuthHandler(X_API_KEY, X_API_SECRET)
            self.auth.set_access_token(X_ACCESS_TOKEN, X_ACCESS_SECRET)
            self.api = tweepy.API(self.auth)
            self.client = tweepy.Client(
                bearer_token=X_BEARER_TOKEN,
                consumer_key=X_API_KEY,
                consumer_secret=X_API_SECRET,
                access_token=X_ACCESS_TOKEN,
                access_token_secret=X_ACCESS_SECRET
            )
            logger.info("✅ تم الاتصال بـ X بنجاح")
        except Exception as e:
            logger.error(f"❌ خطأ في الاتصال بـ X: {e}")
    
    async def post_text(self, text: str) -> bool:
        """نشر نص"""
        try:
            response = self.client.create_tweet(text=text)
            logger.info(f"✅ تم نشر النص: {response.data['id']}")
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نشر النص: {e}")
            return False
    
    async def post_with_image(self, text: str, image_url: str) -> bool:
        """نشر نص مع صورة"""
        try:
            # تحميل الصورة
            response = requests.get(image_url)
            if response.status_code == 200:
                # حفظ الصورة مؤقتاً
                temp_image = "temp_image.jpg"
                with open(temp_image, 'wb') as f:
                    f.write(response.content)
                
                # تحميل الصورة إلى X
                media = self.api.media_upload(temp_image)
                
                # نشر مع الصورة
                response = self.client.create_tweet(
                    text=text,
                    media_ids=[media.media_id]
                )
                
                # حذف الملف المؤقت
                os.remove(temp_image)
                logger.info(f"✅ تم نشر النص مع الصورة: {response.data['id']}")
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في نشر النص مع الصورة: {e}")
        return False
    
    async def post_with_video(self, text: str, video_url: str) -> bool:
        """نشر نص مع فيديو"""
        try:
            # تحميل الفيديو
            response = requests.get(video_url)
            if response.status_code == 200:
                # حفظ الفيديو مؤقتاً
                temp_video = "temp_video.mp4"
                with open(temp_video, 'wb') as f:
                    f.write(response.content)
                
                # تحميل الفيديو إلى X
                media = self.api.media_upload(temp_video, media_category="tweet_video")
                
                # نشر مع الفيديو
                response = self.client.create_tweet(
                    text=text,
                    media_ids=[media.media_id]
                )
                
                # حذف الملف المؤقت
                os.remove(temp_video)
                logger.info(f"✅ تم نشر النص مع الفيديو: {response.data['id']}")
                return True
        except Exception as e:
            logger.error(f"❌ خطأ في نشر النص مع الفيديو: {e}")
        return False
    
    async def post_content(self, content: Content) -> bool:
        """نشر محتوى كامل"""
        # إضافة الهاشتاجات
        text = content.text
        if content.hashtags:
            text += "\n\n" + " ".join([f"#{tag}" for tag in content.hashtags])
        
        # التحقق من طول النص
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH - 3] + "..."
        
        # النشر حسب نوع المحتوى
        if content.video_url:
            return await self.post_with_video(text, content.video_url)
        elif content.image_url:
            return await self.post_with_image(text, content.image_url)
        else:
            return await self.post_text(text)

# ─────────────────────────────────────────────
# فئة إدارة جدولة النشر
class PostScheduler:
    """إدارة جدولة النشر"""
    
    def __init__(self):
        self.db = ContentDatabase()
        self.poster = XPoster()
        self.schedule_file = SCHEDULE_DB
        self.load_schedule()
    
    def load_schedule(self):
        """تحميل جدولة النشر"""
        if os.path.exists(self.schedule_file):
            try:
                with open(self.schedule_file, 'r', encoding='utf-8') as f:
                    self.schedule = json.load(f)
            except:
                self.schedule = self.get_default_schedule()
        else:
            self.schedule = self.get_default_schedule()
    
    def get_default_schedule(self) -> dict:
        """الجدولة الافتراضية"""
        return {
            'enabled': True,
            'interval_hours': 1,  # كل ساعة
            'random_offset': 10,  # عشوائي بـ 10 دقائق
            'last_post': None,
            'posts_today': 0,
            'max_posts_per_day': 24
        }
    
    def save_schedule(self):
        """حفظ جدولة النشر"""
        try:
            with open(self.schedule_file, 'w', encoding='utf-8') as f:
                json.dump(self.schedule, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ الجدولة: {e}")
    
    async def auto_post(self):
        """النشر التلقائي"""
        if not self.schedule['enabled']:
            return
        
        # الحصول على محتوى عشوائي
        content = self.db.get_random_content()
        if not content:
            logger.warning("⚠️ لا يوجد محتوى للنشر")
            return
        
        # النشر
        success = await self.poster.post_content(content)
        
        if success:
            self.schedule['last_post'] = datetime.now().isoformat()
            self.schedule['posts_today'] += 1
            self.save_schedule()
            logger.info(f"✅ تم النشر التلقائي: {content.id}")
    
    def should_post(self) -> bool:
        """التحقق من استحقاق النشر"""
        if not self.schedule['enabled']:
            return False
        
        # التحقق من الحد الأقصى اليومي
        if self.schedule['posts_today'] >= self.schedule['max_posts_per_day']:
            return False
        
        # التحقق من الفاصل الزمني
        last_post = self.schedule.get('last_post')
        if last_post:
            last_post_time = datetime.fromisoformat(last_post)
            interval = timedelta(hours=self.schedule['interval_hours'])
            if datetime.now() - last_post_time < interval:
                return False
        
        return True

# ─────────────────────────────────────────────
# معالجات الأوامر
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج /start"""
    text = """
🚀 *بوت النشر التلقائي على X*

📱 *الميزات:*
• نشر نصوص + صور + فيديوهات
• جدولة تلقائية
• إضافة هاشتاجات
• إدارة المحتوى

📋 *الأوامر:*
/add_content - إضافة محتوى جديد
/schedule - عرض الجدولة
/stats - عرض الإحصائيات
/post_now - نشر الآن
/help - المساعدة
"""
    await update.message.reply_text(text, parse_mode="MarkdownV2")

async def add_content_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج /add_content"""
    text = """
📝 *إضافة محتوى جديد*

أرسل المحتوى بالصيغة التالية:
```
النص: [نصك هنا]
رابط الصورة: [الرابط أو اترك فارغ]
رابط الفيديو: [الرابط أو اترك فارغ]
هاشتاجات: [#tag1 #tag2 ...]
```
"""
    await update.message.reply_text(text, parse_mode="MarkdownV2")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج /stats"""
    db = ContentDatabase()
    count = db.count_content()
    
    text = f"""
📊 *الإحصائيات*

• عدد المحتويات: {count}
• المصدر: قاعدة بيانات محلية
• الحالة: جاهز للنشر
"""
    await update.message.reply_text(text, parse_mode="MarkdownV2")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج /help"""
    text = """
📚 *دليل المساعدة*

🎯 *طرق النشر:*
1. **يدويَّاً**: /post_now
2. **تلقائياً**: الجدولة المحددة
3. **عشوائياً**: كل ساعة تقريباً

💡 *نصائح:*
• أضف محتوى متنوع
• استخدم هاشتاجات ذات صلة
• جرّب مختلف الأوقات
"""
    await update.message.reply_text(text, parse_mode="MarkdownV2")

# ─────────────────────────────────────────────
def main():
    """الدالة الرئيسية"""
    if not BOT_TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN غير موجود")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # معالجات الأوامر
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("add_content", add_content_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("help", help_command))
    
    logger.info("✅ بوت النشر يعمل الآن...")
    print("✅ بوت النشر يعمل الآن...")
    
    app.run_polling()

if __name__ == "__main__":
    main()
