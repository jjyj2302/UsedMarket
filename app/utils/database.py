# app/utils/database.py
import sqlite3
import uuid
import bcrypt
from flask import g, current_app

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

def close_connection(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            bio TEXT,
            is_blocked INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS report (
            id TEXT PRIMARY KEY,
            reporter_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            reason TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            price TEXT NOT NULL,
            seller_id TEXT NOT NULL
        )
    """)

    # 기본 관리자 계정 생성
    cursor.execute("SELECT * FROM user WHERE username = 'admin'")
    if not cursor.fetchone():
        admin_id = str(uuid.uuid4())
        hashed_pw = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("""
            INSERT INTO user (id, username, password, is_admin)
            VALUES (?, ?, ?, 1)
        """, (admin_id, 'admin', hashed_pw))
        print("기본 관리자 계정이 생성되었습니다.")

    db.commit()
# app/utils/database.py
import sqlite3
import uuid
import bcrypt
from flask import g, current_app

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

def close_connection(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    cursor = db.cursor()
    # 테이블 생성 (없을 경우에만)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            bio TEXT,
            is_blocked INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS report (
            id TEXT PRIMARY KEY,
            reporter_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            reason TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            price TEXT NOT NULL,
            seller_id TEXT NOT NULL
        )
    """)
     # 컬럼 없을 경우 수동으로 추가 (실행해도 이미 있으면 무시됨)
    try:
        cursor.execute("ALTER TABLE user ADD COLUMN is_admin INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE user ADD COLUMN balance INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE user ADD COLUMN is_blocked INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass


    # 관리자 계정이 없으면 생성
    cursor.execute("SELECT * FROM user WHERE username = 'admin'")
    if not cursor.fetchone():
        admin_id = str(uuid.uuid4())
        hashed_pw = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("""
            INSERT INTO user (id, username, password, is_admin)
            VALUES (?, ?, ?, 1)
        """, (admin_id, 'admin', hashed_pw))
        print("기본 관리자 계정이 생성되었습니다.")

    db.commit()
