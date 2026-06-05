# دليل النشر والاستضافة

## 🌐 خيارات الاستضافة المتاحة

### 1. Railway (الأسهل والمجاني)

#### المميزات:
- مجاني تماماً
- سهل الإعداد
- دعم عربي
- لا حاجة لبطاقة ائتمان

#### الخطوات:

```bash
# 1. تثبيت Railway CLI
npm install -g @railway/cli

# 2. تسجيل الدخول
railway login

# 3. إنشاء مشروع جديد
railway create

# 4. تعيين المتغيرات
railway config:set BOT_TOKEN="your_token_here"

# 5. نشر المشروع
git push

# 6. مراقبة السجلات
railway logs --follow
```

### 2. Heroku

#### المميزات:
- موثوق جداً
- لوحة تحكم قوية
- سهل الإدارة

#### الخطوات:

```bash
# 1. تثبيت Heroku CLI
# ثم

# 2. تسجيل الدخول
heroku login

# 3. إنشاء تطبيق
heroku create your-telegram-bot

# 4. عيّن المتغيرات
heroku config:set BOT_TOKEN="your_token_here"

# 5. نشر
git push heroku main

# 6. مراقبة
heroku logs --tail
```

### 3. Render

#### الخطوات:

```bash
# 1. اربط حسابك على GitHub
# 2. انسخ المستودع
# 3. أنشئ Web Service
# 4. عيّن BOT_TOKEN
# 5. Deploy
```

### 4. خادم خاص (VPS)

#### على DigitalOcean:

```bash
# 1. أنشئ Droplet بـ Ubuntu 20.04

# 2. SSH إلى السيرفر
ssh root@your_ip

# 3. التحديثات
apt-get update
apt-get upgrade -y

# 4. تثبيت Python
apt-get install python3 python3-pip python3-venv git

# 5. استنساخ المستودع
git clone https://github.com/salhimoha8366-spec/my-telegram-bot.git
cd my-telegram-bot

# 6. بيئة افتراضية
python3 -m venv venv
source venv/bin/activate

# 7. تثبيت المكتبات
pip install -r requirements.txt

# 8. إعداد البوت
nano .env
# أضف BOT_TOKEN

# 9. تشغيل دائم باستخدام supervisor
apt-get install supervisor

# أنشئ ملف التكوين
nano /etc/supervisor/conf.d/bot.conf

# أضف:
[program:telegram-bot]
directory=/root/my-telegram-bot
command=/root/my-telegram-bot/venv/bin/python bot.py
autostart=true
autorestart=true
user=root

# شغّل supervisor
supervisorctl reread
supervisorctl update
supervisorctl start telegram-bot
```

#### على Linode:

```bash
# خطوات مشابهة لـ DigitalOcean
# مع تكييف اسم المستخدم والمسارات
```

### 5. Docker

#### ملف Dockerfile:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

#### البناء والتشغيل:

```bash
# بناء الصورة
docker build -t telegram-bot .

# تشغيل الحاوية
docker run -e BOT_TOKEN="your_token" telegram-bot
```

### 6. Docker Compose

#### docker-compose.yml:

```yaml
version: '3.8'

services:
  bot:
    build: .
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
    volumes:
      - ./downloads:/app/downloads
      - ./download_history.json:/app/download_history.json
    restart: always
```

#### التشغيل:

```bash
docker-compose up -d
```

## ✅ قائمة التحقق قبل النشر

- [ ] تثبيت جميع المكتبات
- [ ] اختبار البوت محلياً
- [ ] التحقق من BOT_TOKEN
- [ ] اختبار جميع الأوامر
- [ ] اختبار جميع المنصات
- [ ] التحقق من رسائل الأخطاء
- [ ] إنشاء ملف .env
- [ ] إنشاء مجلد downloads
- [ ] إضافة FFmpeg (إن لزم الحال)

## 🔧 إدارة التطبيق بعد النشر

### مراقبة السجلات

#### Railway:
```bash
railway logs --follow
```

#### Heroku:
```bash
heroku logs --tail
```

#### خادم خاص:
```bash
tail -f /var/log/supervisor/bot.log
```

### إيقاف/إعادة التشغيل

#### Railway:
```bash
railway down
railway up
```

#### Heroku:
```bash
heroku ps:scale worker=0
heroku ps:scale worker=1
```

#### خادم خاص:
```bash
supervisorctl stop telegram-bot
supervisorctl start telegram-bot
```

## 🚨 مشاكل شائعة وحلولها

### المشكلة: البوت لا يستجيب

```bash
# تحقق من السجلات
# أعد التشغيل
# تأكد من BOT_TOKEN
```

### المشكلة: استهلاك CPU عالي

```bash
# قلل عدد العمليات المتزامنة
# أضف حد أقصى للملفات
# استخدم صور Docker محسّنة
```

### المشكلة: مشاكل الذاكرة

```bash
# تنظيف الملفات المؤقتة
# تقليل حجم ذاكرة التخزين المؤقت
# استخدم خادم أقوى
```

## 💰 التكاليف المتوقعة

| الخدمة | التكلفة | الملاحظات |
|--------|--------|---------|
| Railway | مجاني | توليد محدود مجاني |
| Heroku | مجاني (بدون Dyno) | الخطة المدفوعة من $7 |
| Render | مجاني | مع قيود |
| DigitalOcean | $5+/شهر | حسب الخطة |
| Linode | $5+/شهر | حسب الخطة |

---

اختر الخيار الذي يناسبك أفضل! 🚀
