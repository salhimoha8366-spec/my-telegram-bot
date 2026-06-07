"""
🎬 خدمة تحميل الفيديوهات المتقدمة
تدعم جميع المنصات الشهيرة
"""

import os
import asyncio
import logging
from typing import Optional, Dict
import yt_dlp

logger = logging.getLogger(__name__)


class VideoDownloader:
    """خدمة تحميل الفيديوهات"""
    
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
    
    @staticmethod
    def get_ydl_opts(quality: str = "best", download_dir: str = "downloads") -> dict:
        """إعدادات yt-dlp حسب الجودة"""
        base_opts = {
            "quiet": False,
            "no_warnings": False,
            "socket_timeout": 30,
            "socket_timeout_retry": 5,
            "retries": 5,
            "fragment_retries": 5,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
        }
        
        # تحديد الصيغة حسب الجودة
        quality_map = {
            "best": "bestvideo+bestaudio/best",
            "720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "audio": "bestaudio/best",
            "worst": "worst",
        }
        
        base_opts["format"] = quality_map.get(quality, "best")
        return base_opts
    
    async def download_video(
        self, 
        url: str, 
        quality: str = "best"
    ) -> Optional[Dict]:
        """تحميل الفيديو بشكل async"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._download_sync, 
                url, 
                quality
            )
            return result
        except Exception as e:
            logger.error(f"❌ خطأ في التحميل: {e}")
            return None
    
    def _download_sync(self, url: str, quality: str) -> Optional[Dict]:
        """تحميل الفيديو (دالة متزامنة)"""
        try:
            opts = self.get_ydl_opts(quality, self.download_dir)
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                
                return {
                    "title": info.get("title", "Unknown"),
                    "filename": os.path.basename(file_path),
                    "filepath": file_path,
                    "duration": info.get("duration", 0),
                    "uploader": info.get("uploader", "Unknown"),
                    "platform": self._detect_platform(url),
                    "filesize": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                }
        except Exception as e:
            logger.error(f"❌ خطأ في التحميل المتزامن: {e}")
            return None
    
    @staticmethod
    def _detect_platform(url: str) -> str:
        """كشف منصة الفيديو"""
        platforms = {
            "youtube.com": "YouTube",
            "youtu.be": "YouTube",
            "tiktok.com": "TikTok",
            "instagram.com": "Instagram",
            "facebook.com": "Facebook",
            "twitter.com": "Twitter",
            "x.com": "X (Twitter)",
        }
        
        for platform_url, platform_name in platforms.items():
            if platform_url in url:
                return platform_name
        
        return "Unknown Platform"
    
    def cleanup_file(self, filepath: str) -> bool:
        """حذف الملف بعد الإرسال"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
        except Exception as e:
            logger.error(f"خطأ في حذف الملف: {e}")
        return False
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """تنسيق مدة الفيديو"""
        if not seconds:
            return "N/A"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
    
    @staticmethod
    def format_filesize(bytes_size: int) -> str:
        """تنسيق حجم الملف"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.2f} TB"


# إنشاء نسخة عامة
downloader = VideoDownloader()
