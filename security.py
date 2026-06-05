# 🔐 نظام الأمان والحماية
"""
ميزات الأمان والحماية
"""

import hashlib
import hmac
from typing import Dict
from datetime import datetime, timedelta

class SecurityManager:
    """مدير الأمان"""
    
    def __init__(self):
        self.failed_attempts = {}
        self.max_attempts = 5
        self.lockout_duration = 300  # 5 دقائق
    
    def hash_token(self, token: str) -> str:
        """تجزئة التوكن"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def verify_token(self, token: str, hash_token: str) -> bool:
        """التحقق من التوكن"""
        return hmac.compare_digest(self.hash_token(token), hash_token)
    
    def check_rate_limit(self, user_id: int) -> bool:
        """التحقق من حد معدل الطلبات"""
        now = datetime.now()
        
        if user_id in self.failed_attempts:
            attempts, last_attempt = self.failed_attempts[user_id]
            
            # إذا انتهت فترة الحظر
            if now - last_attempt > timedelta(seconds=self.lockout_duration):
                del self.failed_attempts[user_id]
                return True
            
            # إذا تجاوزت محاولات
            if attempts >= self.max_attempts:
                return False
        
        return True
    
    def record_failed_attempt(self, user_id: int):
        """تسجيل محاولة فاشلة"""
        now = datetime.now()
        
        if user_id in self.failed_attempts:
            attempts, _ = self.failed_attempts[user_id]
            self.failed_attempts[user_id] = (attempts + 1, now)
        else:
            self.failed_attempts[user_id] = (1, now)
    
    def reset_attempts(self, user_id: int):
        """إعادة تعيين المحاولات"""
        if user_id in self.failed_attempts:
            del self.failed_attempts[user_id]
    
    def sanitize_filename(self, filename: str) -> str:
        """تنظيف اسم الملف من الأحرف الخطرة"""
        dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        return filename[:255]  # حد أقصى لاسم الملف
    
    def validate_url(self, url: str) -> bool:
        """التحقق من صيغة الرابط"""
        valid_schemes = ['http', 'https']
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.scheme in valid_schemes
        except:
            return False

# إنشاء نسخة عامة
security_manager = SecurityManager()
