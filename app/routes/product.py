# app/routes/product.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import uuid
from app.utils.database import get_db
from app.utils.decorators import login_required

product_bp = Blueprint('product', __name__)

@product_bp.route('/product/new', methods=['GET', 'POST'])
@login_required
def new_product():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = request.form['price']

        db = get_db()
        cursor = db.cursor()
        product_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO product (id, title, description, price, seller_id) VALUES (?, ?, ?, ?, ?)",
            (product_id, title, description, price, session['user_id'])
        )
        db.commit()
        flash('상품이 등록되었습니다.')
        return redirect(url_for('main.dashboard'))
    return render_template('new_product.html')


@product_bp.route('/product/<product_id>')
@login_required
def view_product(product_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM product WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        flash('상품을 찾을 수 없습니다.')
        return redirect(url_for('main.dashboard'))

    cursor.execute("SELECT * FROM user WHERE id = ?", (product['seller_id'],))
    seller = cursor.fetchone()

    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()

    return render_template('view_product.html', product=product, seller=seller, user=current_user)


@product_bp.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    if request.method == 'POST':
        username = request.form['target_id']
        reason = request.form['reason']

        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT id FROM user WHERE username = ?", (username,))
        target_user = cursor.fetchone()

        if not target_user:
            flash("해당 유저를 찾을 수 없습니다.")
            return redirect(url_for('product.report'))

        target_id = target_user['id']
        report_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO report (id, reporter_id, target_id, reason)
            VALUES (?, ?, ?, ?)
        """, (report_id, session['user_id'], target_id, reason))

        db.commit()
        flash('신고가 접수되었습니다. 관리자가 검토 후 조치할 예정입니다.')
        return redirect(url_for('main.dashboard'))
    return render_template('report.html')


@product_bp.route('/charge', methods=['GET', 'POST'])
@login_required
def charge():
    if request.method == 'POST':
        try:
            amount = int(request.form['amount'])
            if amount <= 0:
                flash("0원 이하로는 충전할 수 없습니다.")
                return redirect(url_for('product.charge'))
        except ValueError:
            flash("유효한 숫자를 입력해주세요.")
            return redirect(url_for('product.charge'))

        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE user SET balance = balance + ? WHERE id = ?", (amount, session['user_id']))
        db.commit()
        flash(f"{amount}원이 충전되었습니다.")
        return redirect(url_for('main.dashboard'))
    return render_template('charge.html')


@product_bp.route('/transfer/<seller_id>/<product_id>', methods=['POST'])
@login_required
def direct_transfer(seller_id, product_id):
    amount = int(request.form['amount'])

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM product WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        flash("해당 상품은 존재하지 않습니다.")
        return redirect(url_for('main.dashboard'))

    if amount != int(product['price']):
        flash("송금 금액이 상품 가격과 일치하지 않습니다.")
        return redirect(url_for('product.view_product', product_id=product_id))

    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    sender = cursor.fetchone()
    cursor.execute("SELECT * FROM user WHERE id = ?", (seller_id,))
    recipient = cursor.fetchone()

    if not recipient or sender['id'] == recipient['id']:
        flash("유효하지 않은 송금 대상입니다.")
        return redirect(url_for('product.view_product', product_id=product_id))

    if sender['balance'] < amount:
        flash("잔액 포인트가 부족합니다")
        return redirect(url_for('product.view_product', product_id=product_id))

    cursor.execute("UPDATE user SET balance = balance - ? WHERE id = ?", (amount, sender['id']))
    cursor.execute("UPDATE user SET balance = balance + ? WHERE id = ?", (amount, recipient['id']))
    cursor.execute("DELETE FROM product WHERE id = ?", (product_id,))
    db.commit()

    flash(f"{recipient['username']}님에게 {amount}원을 송금하고 상품을 구매했습니다.")
    return redirect(url_for('main.dashboard'))


@product_bp.route('/search')
@login_required
def search():
    keyword = request.args.get('q', '').strip()

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()

    if keyword:
        cursor.execute("SELECT * FROM product WHERE title LIKE ?", (f"%{keyword}%",))
        results = cursor.fetchall()
        flash(f"'{keyword}'에 대한 검색 결과입니다.")
    else:
        results = []
        flash("검색어를 입력해주세요.")

    return render_template('dashboard.html', products=results, user=current_user)
