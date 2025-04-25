# config.py

from datetime import timedelta

class Config:
    SECRET_KEY = 'secret!'  # 보안 키 (배포 시 변경 필수)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=15)  # 세션 유지 시간
    DATABASE = 'market.db'  # SQLite DB 경로
