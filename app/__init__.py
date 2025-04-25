# app/__init__.py
from flask import Flask
from flask_wtf import CSRFProtect
from flask_socketio import SocketIO
from .utils.database import init_db
from .utils.database import close_connection
from .utils.decorators import register_error_handlers
from config import Config
from .routes.auth import auth_bp
from .routes.main import main_bp
from .routes.product import product_bp
from .routes.admin import admin_bp
from .routes.chat import chat_socket_events
from flask_wtf.csrf import generate_csrf
import os

socketio = SocketIO()
csrf = CSRFProtect()

def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
    app.config.from_object(Config)

    # 보안 설정
    csrf.init_app(app)

    # DB 종료 핸들러 등록
    app.teardown_appcontext(close_connection)

    # 블루프린트 등록
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(admin_bp)

    # 소켓이벤트 등록
    socketio.init_app(app)
    chat_socket_events(socketio)

    # 에러 핸들러 등록
    register_error_handlers(app)

    # DB 초기화
    with app.app_context():
        init_db()


    @app.after_request
    def add_security_headers(response):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self' https://cdn.socket.io; "
            "script-src 'self' 'unsafe-inline' https://cdn.socket.io; "
            "style-src 'self' 'unsafe-inline'; "
        )
        return response

    # 템플릿에서 {{ csrf_token() }} 사용 가능하도록 설정
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf)
    return app
