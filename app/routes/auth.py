from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
import uuid
import bcrypt
from app.utils.database import get_db
from app.utils.validators import is_valid_username, is_valid_password
from app.utils.decorators import login_required
from datetime import datetime, timedelta

login_attempts = {}  # { ip: (count, last_attempt_time) }

auth_bp = Blueprint('auth', __name__)

def log_user_activity(user_id, action):
    db = get_db()
    cursor = db.cursor()
    log_id = str(uuid.uuid4())  # 고유 ID 생성
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 타임스탬프 생성
    cursor.execute("""
        INSERT INTO activity_log (id, user_id, action, timestamp)
        VALUES (?, ?, ?, ?)
    """, (log_id, user_id, action, timestamp))
    db.commit()


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not is_valid_username(username):
            flash('아이디는 3~20자의 영문자, 숫자, 밑줄만 가능합니다.')
            return redirect(url_for('auth.register'))

        if not is_valid_password(password):
            flash('비밀번호는 최소 8자 이상이며, 영문자/숫자/특수문자를 모두 포함해야 합니다.')
            return redirect(url_for('auth.register'))

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
        if cursor.fetchone():
            flash('이미 존재하는 사용자명입니다.')
            return redirect(url_for('auth.register'))

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO user (id, username, password) VALUES (?, ?, ?)",
                       (user_id, username, hashed_password))
        db.commit()
        flash('회원가입이 완료되었습니다. 로그인 해주세요.')
        return redirect(url_for('auth.login'))
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    ip = request.remote_addr
    now = datetime.now()

    attempt_info = login_attempts.get(ip)
    if attempt_info:
        count, last_attempt_time = attempt_info
        if now - last_attempt_time > timedelta(minutes=10):
            login_attempts[ip] = (0, now)
        elif count >= 5:
            flash("로그인 시도 제한. 10분 후 다시 시도하세요.")
            return redirect(url_for('auth.login'))
    else:
        login_attempts[ip] = (0, now)

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            log_user_activity(user['id'], '로그인 시도')
            login_attempts[ip] = (0, now)  # ✅ 로그인 성공 시 실패 초기화
            session['user_id'] = user['id']

            if user['is_blocked']:
                flash('당신은 차단된 사용자입니다. 관리자에게 문의하세요.')
                return redirect(url_for('auth.login'))
            
            flash('로그인 성공!')

            if user['is_admin']:
                timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
                print(f"[ADMIN LOGIN] 관리자 '{username}'이 {timestamp}에 {ip} IP에서 로그인했습니다.")
                return redirect(url_for('superadmin9283.admin_dashboard'))
            else:
                return redirect(url_for('main.dashboard'))
        else:
            count, _ = login_attempts.get(ip, (0, now))
            login_attempts[ip] = (count + 1, now)  # ✅ 실패 기록 증가
            flash('아이디 또는 비밀번호가 올바르지 않습니다.')
            return redirect(url_for('auth.login'))

    return render_template('login.html')

@auth_bp.route('/profile/password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']

        # 현재 비밀번호 확인
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()

        if not bcrypt.checkpw(current_password.encode('utf-8'), user['password']):
            flash('현재 비밀번호가 올바르지 않습니다.')
            return redirect(url_for('auth.change_password'))

        # 새 비밀번호 유효성 검사
        if not is_valid_password(new_password):
            flash('비밀번호는 최소 8자 이상이며, 영문자/숫자/특수문자를 모두 포함해야 합니다.')
            return redirect(url_for('auth.change_password'))

        # 새 비밀번호 해싱
        hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("UPDATE user SET password = ? WHERE id = ?", (hashed_new_password, session['user_id']))
        db.commit()
        
        # 활동 로그 기록
        log_user_activity(session['user_id'], '비밀번호 변경')  # 비밀번호 변경 후 기록

        flash('비밀번호가 성공적으로 변경되었습니다.')
        return redirect(url_for('main.dashboard'))

    return render_template('change_password.html')


@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()  # ✅ 전체 세션 초기화로 보안 강화
    flash('로그아웃되었습니다.')
    return redirect(url_for('main.index'))
