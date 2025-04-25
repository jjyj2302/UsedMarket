# app/utils/decorators.py
from functools import wraps
from flask import session, flash, redirect, url_for, g
from app.utils.database import get_db

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("로그인이 필요합니다.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("로그인이 필요합니다.")
            return redirect(url_for('login'))

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()

        if not user or user['is_admin'] != 1:
            flash("관리자 권한이 필요합니다.")
            return redirect(url_for('dashboard'))

        return f(*args, **kwargs)
    return decorated_function

def register_error_handlers(app):
    from flask import render_template

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template('error.html', message="페이지를 찾을 수 없습니다."), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template('error.html', message="서버에 오류가 발생했습니다. 관리자에게 문의하세요."), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        print(f"[예외 발생] {e}")
        return render_template('error.html', code=500, message="알 수 없는 오류가 발생했습니다."), 500
