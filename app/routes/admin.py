# app/routes/admin.py
from flask import Blueprint, render_template, redirect, url_for, flash
from app.utils.database import get_db
from app.utils.decorators import admin_required

admin_bp = Blueprint('superadmin9283', __name__, url_prefix='/superadmin9283')
# 관리자 URL 숨기기

@admin_bp.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM user")
    users = cursor.fetchall()
    cursor.execute("SELECT * FROM product")
    products = cursor.fetchall()
    cursor.execute("SELECT * FROM report")
    reports = cursor.fetchall()
    return render_template('admin_dashboard.html', users=users, products=products, reports=reports)


@admin_bp.route('/admin/block_user/<user_id>', methods=['POST'])
@admin_required
def admin_block_user(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE user SET is_blocked = 1 WHERE id = ?", (user_id,))
    db.commit()
    flash(f'{user_id} 사용자가 차단되었습니다.')
    return redirect(url_for('superadmin9283.admin_dashboard'))



@admin_bp.route('/admin/delete_user_products/<user_id>', methods=['POST'])
@admin_required
def admin_delete_user_products(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM product WHERE seller_id = ?", (user_id,))
    db.commit()
    flash(f'{user_id} 사용자의 상품이 삭제되었습니다.')
    return redirect(url_for('superadmin9283.admin_dashboard'))

