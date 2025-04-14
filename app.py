import sqlite3
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from flask_socketio import SocketIO, send
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
DATABASE = 'market.db'
socketio = SocketIO(app)

# 데이터베이스 연결 관리: 요청마다 연결 생성 후 사용, 종료 시 close
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # 결과를 dict처럼 사용하기 위함
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 테이블 생성 (최초 실행 시에만)
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # 사용자 테이블 생성
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
        # 상품 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                price TEXT NOT NULL,
                seller_id TEXT NOT NULL,
                is_blocked INTEGER DEFAULT 0,
                is_sold INTEGER DEFAULT 0
            )
        """)
        # 신고 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS report (
                id TEXT PRIMARY KEY,
                reporter_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                report_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)
        # 거래 내역 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                sender_id TEXT NOT NULL,
                receiver_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES user (id),
                FOREIGN KEY (receiver_id) REFERENCES user (id)
            )
        """)
        db.commit()

# 관리자 권한 확인 데코레이터
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT is_admin FROM user WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()
        
        if not user or not user['is_admin']:
            flash('관리자 권한이 필요합니다.')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# 기본 라우트
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# 회원가입
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor()
        # 중복 사용자 체크
        cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
        if cursor.fetchone() is not None:
            flash('이미 존재하는 사용자명입니다.')
            return redirect(url_for('register'))
        user_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO user (id, username, password) VALUES (?, ?, ?)",
                       (user_id, username, password))
        db.commit()
        flash('회원가입이 완료되었습니다. 로그인 해주세요.')
        return redirect(url_for('login'))
    return render_template('register.html')

# 로그인
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        if user:
            if user['is_blocked']:
                flash('차단된 사용자입니다. 관리자에게 문의하세요.')
                return redirect(url_for('login'))
            session['user_id'] = user['id']
            flash('로그인 성공!')
            return redirect(url_for('dashboard'))
        else:
            flash('아이디 또는 비밀번호가 올바르지 않습니다.')
            return redirect(url_for('login'))
    return render_template('login.html')

# 로그아웃
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('로그아웃되었습니다.')
    return redirect(url_for('index'))

# 대시보드: 사용자 정보와 전체 상품 리스트 표시
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cursor = db.cursor()
    # 현재 사용자 조회
    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()
    
    # 차단되지 않은 상품만 조회
    cursor.execute("""
        SELECT p.*, u.username as seller_name 
        FROM product p 
        JOIN user u ON p.seller_id = u.id 
        WHERE p.is_blocked = 0 AND u.is_blocked = 0
    """)
    all_products = cursor.fetchall()
    return render_template('dashboard.html', products=all_products, user=current_user)

# 프로필 페이지: bio 업데이트 가능
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cursor = db.cursor()
    if request.method == 'POST':
        bio = request.form.get('bio', '')
        cursor.execute("UPDATE user SET bio = ? WHERE id = ?", (bio, session['user_id']))
        db.commit()
        flash('프로필이 업데이트되었습니다.')
        return redirect(url_for('profile'))
    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()
    return render_template('profile.html', user=current_user)

# 상품 등록
@app.route('/product/new', methods=['GET', 'POST'])
def new_product():
    if 'user_id' not in session:
        return redirect(url_for('login'))
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
        return redirect(url_for('dashboard'))
    return render_template('new_product.html')

# 상품 상세보기
@app.route('/product/<product_id>')
def view_product(product_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM product WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        flash('상품을 찾을 수 없습니다.')
        return redirect(url_for('dashboard'))
    # 판매자 정보 조회
    cursor.execute("SELECT * FROM user WHERE id = ?", (product['seller_id'],))
    seller = cursor.fetchone()
    return render_template('view_product.html', product=product, seller=seller)

# 신고하기
@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        target_id = request.form['target_id']
        reason = request.form['reason']
        report_type = request.form['report_type']  # 'user' 또는 'product'
        
        db = get_db()
        cursor = db.cursor()
        report_id = str(uuid.uuid4())
        
        # 신고 기록 저장
        cursor.execute(
            "INSERT INTO report (id, reporter_id, target_id, reason, report_type) VALUES (?, ?, ?, ?, ?)",
            (report_id, session['user_id'], target_id, reason, report_type)
        )
        
        # 신고 횟수 확인 (최근 7일 이내)
        cursor.execute("""
            SELECT COUNT(*) as report_count 
            FROM report 
            WHERE target_id = ? 
            AND report_type = ? 
            AND created_at >= datetime('now', '-7 days')
        """, (target_id, report_type))
        
        report_count = cursor.fetchone()[0]
        
        # 신고 횟수가 3회 이상이면 차단
        if report_count >= 3:
            if report_type == 'user':
                cursor.execute("UPDATE user SET is_blocked = 1 WHERE id = ?", (target_id,))
                flash('해당 사용자가 차단되었습니다.')
            else:  # product
                cursor.execute("UPDATE product SET is_blocked = 1 WHERE id = ?", (target_id,))
                flash('해당 상품이 차단되었습니다.')
        
        db.commit()
        flash('신고가 접수되었습니다.')
        return redirect(url_for('dashboard'))
    return render_template('report.html')

# 잔액 충전
@app.route('/balance/charge', methods=['GET', 'POST'])
def charge_balance():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        amount = int(request.form['amount'])
        if amount <= 0:
            flash('올바른 금액을 입력해주세요.')
            return redirect(url_for('charge_balance'))
            
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE user SET balance = balance + ? WHERE id = ?", 
                      (amount, session['user_id']))
        db.commit()
        flash(f'{amount}원이 충전되었습니다.')
        return redirect(url_for('dashboard'))
        
    return render_template('charge_balance.html')

# 송금
@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        receiver_username = request.form['receiver']
        amount = int(request.form['amount'])
        description = request.form.get('description', '')
        
        if amount <= 0:
            flash('올바른 금액을 입력해주세요.')
            return redirect(url_for('transfer'))
            
        db = get_db()
        cursor = db.cursor()
        
        # 수신자 확인
        cursor.execute("SELECT * FROM user WHERE username = ?", (receiver_username,))
        receiver = cursor.fetchone()
        if not receiver:
            flash('존재하지 않는 사용자입니다.')
            return redirect(url_for('transfer'))
            
        # 송신자 잔액 확인
        cursor.execute("SELECT balance FROM user WHERE id = ?", (session['user_id'],))
        sender_balance = cursor.fetchone()['balance']
        
        if sender_balance < amount:
            flash('잔액이 부족합니다.')
            return redirect(url_for('transfer'))
            
        # 트랜잭션 시작
        try:
            # 송신자 잔액 감소
            cursor.execute("UPDATE user SET balance = balance - ? WHERE id = ?",
                         (amount, session['user_id']))
            # 수신자 잔액 증가
            cursor.execute("UPDATE user SET balance = balance + ? WHERE id = ?",
                         (amount, receiver['id']))
            # 거래 내역 기록
            transaction_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO transaction (id, sender_id, receiver_id, amount, description)
                VALUES (?, ?, ?, ?, ?)
            """, (transaction_id, session['user_id'], receiver['id'], amount, description))
            
            db.commit()
            flash(f'{receiver_username}님께 {amount}원을 송금했습니다.')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            db.rollback()
            flash('송금 중 오류가 발생했습니다.')
            return redirect(url_for('transfer'))
            
    return render_template('transfer.html')

# 거래 내역 조회
@app.route('/transactions')
def view_transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT t.*, 
               s.username as sender_username,
               r.username as receiver_username
        FROM transaction t
        JOIN user s ON t.sender_id = s.id
        JOIN user r ON t.receiver_id = r.id
        WHERE t.sender_id = ? OR t.receiver_id = ?
        ORDER BY t.created_at DESC
    """, (session['user_id'], session['user_id']))
    
    transactions = cursor.fetchall()
    return render_template('transactions.html', transactions=transactions)

# 상품 검색
@app.route('/search')
def search():
    query = request.args.get('q', '')
    category = request.args.get('category', 'all')
    sort_by = request.args.get('sort', 'recent')
    
    db = get_db()
    cursor = db.cursor()
    
    base_query = """
        SELECT p.*, u.username as seller_name
        FROM product p
        JOIN user u ON p.seller_id = u.id
        WHERE p.is_blocked = 0 AND u.is_blocked = 0
    """
    
    params = []
    if query:
        base_query += " AND (p.title LIKE ? OR p.description LIKE ?)"
        params.extend([f'%{query}%', f'%{query}%'])
    
    if category != 'all':
        base_query += " AND p.category = ?"
        params.append(category)
    
    if sort_by == 'price_asc':
        base_query += " ORDER BY CAST(p.price AS INTEGER) ASC"
    elif sort_by == 'price_desc':
        base_query += " ORDER BY CAST(p.price AS INTEGER) DESC"
    else:  # recent
        base_query += " ORDER BY p.created_at DESC"
    
    cursor.execute(base_query, params)
    products = cursor.fetchall()
    
    return render_template('search.html', products=products, query=query,
                         category=category, sort_by=sort_by)

# 관리자 대시보드
@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

# 사용자 관리
@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT u.*, 
               COUNT(DISTINCT p.id) as product_count,
               COUNT(DISTINCT r.id) as report_count
        FROM user u
        LEFT JOIN product p ON u.id = p.seller_id
        LEFT JOIN report r ON u.id = r.target_id AND r.report_type = 'user'
        GROUP BY u.id
        ORDER BY u.username
    """)
    users = cursor.fetchall()
    return render_template('admin/users.html', users=users)

# 사용자 차단/차단해제
@app.route('/admin/users/<user_id>/toggle_block', methods=['POST'])
@admin_required
def toggle_user_block(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE user SET is_blocked = 1 - is_blocked WHERE id = ?", (user_id,))
    db.commit()
    return redirect(url_for('admin_users'))

# 상품 관리
@app.route('/admin/products')
@admin_required
def admin_products():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT p.*, u.username as seller_name,
               COUNT(DISTINCT r.id) as report_count
        FROM product p
        JOIN user u ON p.seller_id = u.id
        LEFT JOIN report r ON p.id = r.target_id AND r.report_type = 'product'
        GROUP BY p.id
        ORDER BY p.created_at DESC
    """)
    products = cursor.fetchall()
    return render_template('admin/products.html', products=products)

# 상품 차단/차단해제
@app.route('/admin/products/<product_id>/toggle_block', methods=['POST'])
@admin_required
def toggle_product_block(product_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE product SET is_blocked = 1 - is_blocked WHERE id = ?", (product_id,))
    db.commit()
    return redirect(url_for('admin_products'))

# 신고 관리
@app.route('/admin/reports')
@admin_required
def admin_reports():
    status = request.args.get('status', 'pending')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT r.*, 
               reporter.username as reporter_name,
               CASE 
                   WHEN r.report_type = 'user' THEN target_user.username
                   ELSE target_product.title
               END as target_name,
               r.report_type
        FROM report r
        JOIN user reporter ON r.reporter_id = reporter.id
        LEFT JOIN user target_user ON r.target_id = target_user.id AND r.report_type = 'user'
        LEFT JOIN product target_product ON r.target_id = target_product.id AND r.report_type = 'product'
        WHERE r.status = ?
        ORDER BY r.created_at DESC
    """, (status,))
    reports = cursor.fetchall()
    return render_template('admin/reports.html', reports=reports, current_status=status)

# 신고 처리
@app.route('/admin/reports/<report_id>/process', methods=['POST'])
@admin_required
def process_report(report_id):
    action = request.form['action']  # 'approve' or 'reject'
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM report WHERE id = ?", (report_id,))
    report = cursor.fetchone()
    
    if action == 'approve':
        if report['report_type'] == 'user':
            cursor.execute("UPDATE user SET is_blocked = 1 WHERE id = ?", (report['target_id'],))
        else:  # product
            cursor.execute("UPDATE product SET is_blocked = 1 WHERE id = ?", (report['target_id'],))
    
    cursor.execute("UPDATE report SET status = ? WHERE id = ?", 
                  ('approved' if action == 'approve' else 'rejected', report_id))
    db.commit()
    
    flash(f'신고가 {action}되었습니다.')
    return redirect(url_for('admin_reports'))

# 통계 대시보드
@app.route('/admin/stats')
@admin_required
def admin_stats():
    db = get_db()
    cursor = db.cursor()
    
    # 전체 통계
    cursor.execute("""
        SELECT 
            (SELECT COUNT(*) FROM user) as total_users,
            (SELECT COUNT(*) FROM user WHERE is_blocked = 1) as blocked_users,
            (SELECT COUNT(*) FROM product) as total_products,
            (SELECT COUNT(*) FROM product WHERE is_blocked = 1) as blocked_products,
            (SELECT COUNT(*) FROM report WHERE status = 'pending') as pending_reports
    """)
    stats = cursor.fetchone()
    
    # 일별 거래량
    cursor.execute("""
        SELECT DATE(created_at) as date,
               COUNT(*) as transaction_count,
               SUM(amount) as total_amount
        FROM transaction
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 7
    """)
    daily_transactions = cursor.fetchall()
    
    return render_template('admin/stats.html', stats=stats, 
                         daily_transactions=daily_transactions)

# 실시간 채팅: 클라이언트가 메시지를 보내면 전체 브로드캐스트
@socketio.on('send_message')
def handle_send_message_event(data):
    data['message_id'] = str(uuid.uuid4())
    send(data, broadcast=True)

if __name__ == '__main__':
    init_db()  # 앱 컨텍스트 내에서 테이블 생성
    socketio.run(app, debug=True)
