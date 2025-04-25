import sqlite3      #SQLite라는 내장형 데이터베이스를 쓰겠다.
import uuid         #사용자간 중복없는 진짜 고유 식별자를 만들어서 데이터베이스의 기본키로 쓰겠다.
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from flask_socketio import SocketIO, send
from functools import wraps   #일반 사용자와 admin 계정 보안을 위한 데코레이터
import re   #정규식 모듈 
import html  #XSS 공격 방지를 위한 모듈 HTML 이스케이프
from flask_wtf import CSRFProtect #CSRF 공격 방지를 위한 모듈
import bcrypt #비밀 번호 암호화를 위한 모듈
from flask import abort #오류 발생 처리를를 위한 모듈
from datetime import timedelta, datetime  #세션 종료 처리와 시간 처리를 위한 모듈

# 보안을 고려한 요소 모음
def is_valid_username(username):
    # 영문, 숫자, 언더스코어만 허용한다. 
    return re.match(r'^[a-zA-Z0-9_]{3,20}$', username)

def is_valid_password(password):
    # 최소 8자 이상, 영문자 + 숫자 + 특수문자 포함
    return (
        len(password) >= 8 and
        re.search(r'[A-Za-z]', password) and
        re.search(r'\d', password) and
        re.search(r'[!@#$%^&*(),.?":{}|<>]', password)
    )

def admin_required(f):     #관리자 권한 확인 데코레이터터
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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("로그인이 필요합니다.")
            return redirect(url_for('login'))
    
        return f(*args, **kwargs)
    return decorated_function

# 오류 메시지 출력 함수
# 404 Not Found 오류 처리리
@app.errorhandler(404)
def not_found_error(e):
    return render_template('error.html', message="페이지를 찾을 수 없습니다."), 404

# 500 Internal Server Error 오류 처리
@app.errorhandler(500)
def internal_error(e):
    return render_template('error.html', message="서버에 오류가 발생했습니다. 관리자에게 문의하세요."), 500

# 예상치 못한 모든 예외 처리 실시
@app.errorhandler(Exception)
def handle_unexpected_error(e):
    print(f"[예외 발생] {e}") # 로그 출력력
    return render_template('error.html', code=500, message="알 수 없는 오류가 발생했습니다."), 500
app = Flask(__name__)
csrf = CSRFProtect(app)
app.config['SECRET_KEY'] = 'secret!'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15) #세션 유지시간 설정 (15분)
DATABASE = 'market.db'
socketio = SocketIO(app)

@app.before_request
def session_timeout_check():
    session.permanent = True # session.lifetime 설정을 위해 필요
    now = datetime.utcnow()

    if 'user_id' in session:
        last_activity = session.get('last_activity')

        if last_activity:
            elapsed = now - datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S')
            if elapsed > timedelta(minutes=15):
                session.clear()
                flash('세션이 만료되었습니다. 다시 로그인해주세요.')
                return redirect(url_for('login'))

        # 활동 시간 갱신
        session['last_activity'] = now.strftime('%Y-%m-%d %H:%M:%S')

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
        cursor = db.cursor()     #cursor는 데이터베이스에 명령을 날리는 도구.
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
        """)  #id : UUID 형식의 고유 식별자, username : 사용자 이름 (중복 x)
              # is_blocked : 0은 정상, 1은 차단된다. 
        
        # 신고 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS report (
                id TEXT PRIMARY KEY,
                reporter_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                reason TEXT NOT NULL
            )
        """)

        # 상품 테이블 생성
        cursor.execute("""
           CREATE TABLE IF NOT EXISTS product (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                price TEXT NOT NULL,
                seller_id TEXT NOT NULL
            )
        """)

        try:
            cursor.execute("ALTER TABLE user ADD COLUMN is_blocked INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE user ADD COLUMN balance INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE user ADD COLUMN is_admin INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass 
        
        # 관리자 계정 생성
        cursor.execute("SELECT * FROM user WHERE username = 'admin'")
        if not cursor.fetchone():
            admin_id = str(uuid.uuid4())
            hashed_admin_pw = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
            cursor.execute("""
                INSERT INTO user (id, username, password, is_admin)
                VALUES (?, ?, ?, 1)   
            """, (admin_id, 'admin', hashed_admin_pw))
            print("기본 관리자 계정이 생성되었습니다.")
      
    
        db.commit()

# 기본 라우트
# app.route('/') : 라우트는 웹 애플리케이션에서 요청을 처리하는 경로를 정의하는 기능.
# 사용자가 웹사이트의 어떤 주소(URL)로 들어왔을 때 어떤 코드를 실행할지 정하는 규칙칙
# 아래의 경우는 홈페이지 역할을 한다. 
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# 회원가입  시 비밀번호 암호화화
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # 서버 측 입력 검증
        if not is_valid_username(username):
            flash('아이디는 3~20자의 영문자, 숫자, 밑줄만 가능합니다.')
            return redirect(url_for('register'))

        if not is_valid_password(password):
            flash('비밀번호는 최소 8자 이상이며, 영문자/숫자/특수문자를 모두 포함해야 합니다.')
            return redirect(url_for('register'))

        db = get_db()
        cursor = db.cursor()
        # 중복 사용자 체크
        cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
        if cursor.fetchone() is not None:
            flash('이미 존재하는 사용자명입니다.')
            return redirect(url_for('register'))

        # 비밀번호 암호화
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO user (id, username, password) VALUES (?, ?, ?)",
                       (user_id, username, hashed_password))
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
        cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
        user = cursor.fetchone()

         if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            if user['is_blocked']:
                flash('당신은 차단된 user입니다. 관리자에게 문의하세요.')
                return redirect(url_for('login'))
            
            session['user_id'] = user['id']
            flash('로그인 성공!')

            # 관리자 계정인 경우 admin 대시보드로 바로 이동한다.
            if user['is_admin']:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))

        else:   
            flash('아이디 또는 비밀번호가 올바르지 않습니다.')
            return redirect(url_for('login'))

    return render_template('login.html')

# 로그아웃
@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    flash('로그아웃되었습니다.')
    return redirect(url_for('index'))

# 대시보드: 사용자 정보와 전체 상품 리스트 표시
@app.route('/dashboard')
@login_required
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cursor = db.cursor()
    # 현재 사용자 조회
    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()
    # 모든 상품 조회
    cursor.execute("SELECT * FROM product")
    all_products = cursor.fetchall()
    return render_template('dashboard.html', products=all_products, user=current_user)

# 프로필 페이지: bio 업데이트 가능
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cursor = db.cursor()
    if request.method == 'POST':
        raw_bio = request.form.get('bio', '')
        # XSS 공격 방지를 위한 HTML 이스케이프
        safe_bio = html.escape(raw_bio)
        cursor.execute("UPDATE user SET bio = ? WHERE id = ?", (safe_bio, session['user_id']))
        db.commit()
        flash('프로필이 업데이트되었습니다.')
        return redirect(url_for('profile'))
    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()
    return render_template('profile.html', user=current_user)

# 상품 등록
@app.route('/product/new', methods=['GET', 'POST'])
@login_required
def new_product():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = request.form['price']
        db = get_db()
        cursor = db.cursor()
        product_id = str(uuid.uuid4())    #애초에 상품을 새롭게 가입할 때부터 UUID를 부여한다.
        cursor.execute(
            "INSERT INTO product (id, title, description, price, seller_id) VALUES (?, ?, ?, ?, ?)",
            (product_id, title, description, price, session['user_id'])
        )
        db.commit()
        flash('상품이 등록되었습니다.')
        return redirect(url_for('dashboard'))
    return render_template('new_product.html')

# 상품 상세보기
@app.route('/product/<product_id>')   #Flask에서 URL 경로에 <...> 이런 식으로 쓰면, 해당 부분을 변수로 받아서 함수의 파라미터로 넘겨준다.
@login_required
def view_product(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

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
    # 현재 로그인한 사용자 정보 조회
    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()
    return render_template('view_product.html', product=product, seller=seller, user=current_user)

# 신고하기
@app.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    if request.method == 'POST':
        username = request.form['target_id']  # 유저 이름으로 입력받음
        reason = request.form['reason']

        db = get_db()
        cursor = db.cursor()

        # 🔍 유저 이름으로 UUID 조회
        cursor.execute("SELECT id FROM user WHERE username = ?", (username,))
        target_user = cursor.fetchone()

        if not target_user:
            flash("해당 유저를 찾을 수 없습니다.")
            return redirect(url_for('report'))

        target_id = target_user['id']  # 실제 UUID로 바꿔서 저장

        report_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO report (id, reporter_id, target_id, reason)
            VALUES (?, ?, ?, ?)
        """, (report_id, session['user_id'], target_id, reason))

        db.commit()
        flash('신고가 접수되었습니다. 관리자가 검토 후 조치할 예정입니다.')
        return redirect(url_for('dashboard'))
    return render_template('report.html')


# 일단 유저들이 본인의 돈을 충전해야 한다.
@app.route('/charge', methods=['GET', 'POST'])
@login_required
def charge():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            amount = int(request.form['amount'])
            if amount <= 0:
                flash("0원 이하로는 충전할 수 없습니다.")
                return redirect(url_for('charge'))
        except ValueError:
            flash("유효한 숫자를 입력해주세요.")
            return redirect(url_for('charge'))
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE user SET balance = balance + ? WHERE id = ?", (amount, session['user_id']))
        db.commit()
        flash(f"{amount}원이 충전되었습니다.")
        return redirect(url_for('dashboard'))
    return render_template('charge.html')

# 유저들 간의 송금이 가능해야 한다. (유저 간 포인트 송금 시스템으로 구현)
@app.route('/transfer/<seller_id>/<product_id>', methods=['POST'])
@login_required
def direct_transfer(seller_id, product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    amount = int(request.form['amount'])

    db = get_db()
    cursor = db.cursor()
    # 상품 정보 먼저 조회
    cursor.execute("SELECT * FROM product WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        flash("해당 상품은 존재하지 않습니다.")
        return redirect(url_for('dashboard'))
    
    # 금액 일치 여부 확인
    if amount != int(product['price']):
        flash("송금 금액이 상품 가격과 일치하지 않습니다.")
        return redirect(url_for('view_product', product_id = product_id))

    # 송신자
    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    sender = cursor.fetchone()
    # 수신자
    cursor.execute("SELECT * FROM user WHERE id = ?", (seller_id,))
    recipient = cursor.fetchone()

    if not recipient or sender['id'] == recipient['id']:
        flash("유효하지 않은 송금 대상입니다.")
    if sender['balance'] < amount:
        flash("잔액 포인트가 부족합니다")
        return redirect(url_for('view_product', product_id=product_id))

    # 송금 처리
    cursor.execute("UPDATE user SET balance = balance - ? WHERE id = ?", (amount, sender['id']))
    cursor.execute("UPDATE user SET balance = balance + ? WHERE id = ?", (amount, recipient['id']))

    # 상품 삭제
    cursor.execute("DELETE FROM product WHERE id = ?", (product_id,))
    db.commit()

    flash(f"{recipient['username']}님에게 {amount}원을 송금하고 상품을 구매했습니다다.")
    return redirect(url_for('dashboard'))

# 상품 검색 기능도 추가해야 한다.
@app.route('/search')
@login_required
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
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
    
# 실시간 채팅: 클라이언트가 메시지를 보내면 전체 브로드캐스트
@socketio.on('send_message')
@login_required
def handle_send_message_event(data):
    data['message_id'] = str(uuid.uuid4())
    send(data, broadcast=True)

#=======================여기서부턴 관리자 전용 라우터 :/admin=======================


@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    cursor = db.cursor()

    # 전체 user 조회
    cursor.execute("SELECT * FROM user")
    users = cursor.fetchall()

    # 전체 상품 조회
    cursor.execute("SELECT * FROM product")
    products = cursor.fetchall()

    # 전체 신고 조회
    cursor.execute("SELECT * FROM report")
    reports = cursor.fetchall()

    return render_template('admin_dashboard.html', users=users, products=products, reports=reports)

@app.route('/admin/block_user/<user_id>', methods=['POST'])
@admin_required
def admin_block_user(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE user SET is_blocked = 1 WHERE id = ?", (user_id,))
    db.commit()
    flash(f'{user_id}사용자가 차단됐습니다.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user_products/<user_id>', methods=['POST']) 
@admin_required
def admin_delete_user_products(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM product WHERE seller_id = ?", (user_id,))
    db.commit()
    flash(f'{user_id}사용자의 상품이 삭제됐습니다.')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    init_db()  # 앱 컨텍스트 내에서 테이블 생성
    socketio.run(app, debug=True)  #debug = False로 설정하면 오류 정보가 사용자에게 노출되지 않는다. 지금은 개발 단계니까 True로 설정하겠다. 
