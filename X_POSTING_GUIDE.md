# 🚀 دليل بوت النشر التلقائي على X

## المميزات

✅ نشر نصوص + صور + فيديوهات
✅ جدولة النشر التلقائي
✅ إضافة هاشتاجات تلقائية
✅ قاعدة بيانات محلية للمحتوى
✅ RSS Feed Support
✅ API Integration

## التثبيت

### 1. المتطلبات
```bash
Python 3.8+
pip
Access Token من X API v2
```

### 2. التثبيت
```bash
git clone https://github.com/salhimoha8366-spec/my-telegram-bot.git
cd my-telegram-bot

# بيئة افتراضية
python -m venv venv
source venv/bin/activate

# المكتبات
pip install -r x_requirements.txt
```

### 3. الإعداد
```bash
# نسخ ملف المتغيرات
cp .env.x.example .env

# تعديل .env وأضف التوكنات
nano .env
```

## الحصول على التوكنات

### X (Twitter) API v2

1. انتقل إلى [Twitter Developer Portal](https://developer.twitter.com/)
2. اختر "Create an app"
3. اختر "Elevated" أو أعلى
4. انسخ:
   - API Key
   - API Secret
   - Bearer Token
   - Access Token
   - Access Token Secret

### Telegram Bot Token

1. تحدث مع [@BotFather](https://t.me/botfather)
2. أرسل: /newbot
3. اتبع التعليمات
4. انسخ التوكن

## طريقة الاستخدام

### تشغيل البوت
```bash
python x_poster_bot.py
```

### أوامر Telegram

| الأمر | الوصف |
|------|-------|
| `/start` | بدء البوت |
| `/add_content` | إضافة محتوى جديد |
| `/schedule` | عرض الجدولة |
| `/stats` | عرض الإحصائيات |
| `/post_now` | نشر فوري |
| `/help` | المساعدة |

## أمثلة المحتوى

### نص بسيط
```
النص: مرحباً بك في بوتي الجديد! 🚀
هاشتاجات: #bot #python #automation
```

### نص مع صورة
```
النص: صورة جميلة اليوم! 📸
رابط الصورة: https://example.com/image.jpg
هاشتاجات: #photography #beautiful
```

### نص مع فيديو
```
النص: فيديو مثير! 🎥
رابط الفيديو: https://example.com/video.mp4
هاشتاجات: #viral #video
```

## جدولة النشر

### الإعدادات الافتراضية
- **الفاصل الزمني**: 1 ساعة
- **الحد الأقصى اليومي**: 24 نشر
- **العشوائية**: 10 دقائق

### التعديل
عدّل `schedule.json`:
```json
{
  "enabled": true,
  "interval_hours": 2,
  "max_posts_per_day": 12,
  "random_offset": 15
}
```

## قاعدة البيانات

### صيغة المحتوى
```json
{
  "text": "نص المحتوى",
  "image_url": "رابط الصورة أو null",
  "video_url": "رابط الفيديو أو null",
  "hashtags": ["tag1", "tag2"],
  "source": "manual",
  "id": "timestamp"
}
```

### ملفات قاعدة البيانات
- `content_database.json` - المحتويات
- `schedule.json` - جدولة النشر
- `posted_content.json` - سجل المشاركات

## الميزات المتقدمة

### 1. RSS Feed
```python
import feedparser

feed = feedparser.parse('https://example.com/feed.xml')
for entry in feed.entries:
    content = Content(
        text=entry.title,
        source="rss"
    )
    db.add_content(content)
```

### 2. API خارجي
```python
import requests

response = requests.get('https://api.example.com/posts')
for item in response.json():
    content = Content(
        text=item['title'],
        image_url=item.get('image')
    )
    db.add_content(content)
```

### 3. الهاشتاجات التلقائية
```python
from textblob import TextBlob

def generate_hashtags(text):
    # تحليل النص واستخراج الكلمات المفتاحية
    blob = TextBlob(text)
    return [word for word in blob.words if len(word) > 5]
```

## استكشاف الأخطاء

### خطأ: توكن غير صحيح
```bash
# تحقق من .env
echo $X_BEARER_TOKEN

# جرّب توكن جديد
# أنشئ تطبيق جديد على Twitter Developer
```

### خطأ: الاتصال
```bash
# تحقق من الإنترنت
ping 8.8.8.8

# تحقق من الحيطة الناري
sudo ufw status
```

### خطأ: الصور/الفيديوهات
```bash
# تحقق من صيغ الملفات المدعومة
# الصور: JPG, PNG, GIF
# الفيديو: MP4, MOV
```

## الأمان

⚠️ **تحذيرات مهمة:**
- لا تشارك `.env` مع أحد
- استخدم متغيرات البيئة
- حم البيانات الحساسة
- راقب معدل الطلبات

## النشر

### على Railway
```bash
railway create
railway config:set TELEGRAM_BOT_TOKEN="token"
railway up
```

### على Heroku
```bash
heroku create
heroku config:set TELEGRAM_BOT_TOKEN="token"
git push heroku main
```

### Docker
```bash
docker build -t x-poster .
docker run -e TELEGRAM_BOT_TOKEN="token" x-poster
```

## الدعم

 للمساعدة:
- اقرأ [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- افتح Issue على GitHub
- تحقق من السجلات

---

**الإصدار**: 1.0.0
**آخر تحديث**: يونيو 2024
