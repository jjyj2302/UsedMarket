from datetime import timedelta
import os
from dotenv import load_dotenv  # 추가

load_dotenv()  # .env 파일 로딩

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=15)
    DATABASE = os.getenv('DATABASE', 'market.db')
    DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
    DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
    
    # 세션/쿠키 보안 강화 설정 추가
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

