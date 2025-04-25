# app/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import uuid
import bcrypt
from app.utils.database import get_db
from app.utils.validators import is_valid_username, is_valid_password
from app.utils.decorators import login_required

auth_bp = Blueprint('auth', __name__)

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
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            if user['is_blocked']:
                flash('당신은 차단된 사용자입니다. 관리자에게 문의하세요.')
                return redirect(url_for('auth.login'))

            session['user_id'] = user['id']
            flash('로그인 성공!')

            if user['is_admin']:
                return redirect(url_for('admin.admin_dashboard'))
            else:
                return redirect(url_for('main.dashboard'))
        else:
            flash('아이디 또는 비밀번호가 올바르지 않습니다.')
            return redirect(url_for('auth.login'))

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    flash('로그아웃되었습니다.')
    return redirect(url_for('main.index'))
