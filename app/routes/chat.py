# app/routes/chat.py
from flask import session
from flask_socketio import emit
import uuid
from app.utils.decorators import login_required

def chat_socket_events(socketio):
    @socketio.on('send_message')
    def handle_send_message_event(data):
        data['message_id'] = str(uuid.uuid4())
        emit('message',data, broadcast=True)
