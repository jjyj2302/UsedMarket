# app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for, session, request, flash
from datetime import datetime, timedelta
import html
from app.utils.database import get_db
from app.utils.decorators import login_required

main_bp = Blueprint('main', __name__)

@main_bp.before_app_request
def session_timeout_check():
    session.permanent = True
    now = datetime.utcnow()

    if 'user_id' in session:
        last_activity = session.get('last_activity')

        if last_activity:
            elapsed = now - datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S')
            if elapsed > timedelta(minutes=15):
                session.clear()
                flash('세션이 만료되었습니다. 다시 로그인해주세요.')
                return redirect(url_for('auth.login'))

        session['last_activity'] = now.strftime('%Y-%m-%d %H:%M:%S')

@main_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()
    cursor.execute("SELECT * FROM product")
    all_products = cursor.fetchall()
    return render_template('dashboard.html', products=all_products, user=current_user)

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = get_db()
    cursor = db.cursor()
    if request.method == 'POST':
        raw_bio = request.form.get('bio', '')
        safe_bio = html.escape(raw_bio)
        cursor.execute("UPDATE user SET bio = ? WHERE id = ?", (safe_bio, session['user_id']))
        db.commit()
        flash('프로필이 업데이트되었습니다.')
        return redirect(url_for('main.profile'))

    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()
    return render_template('profile.html', user=current_user)
