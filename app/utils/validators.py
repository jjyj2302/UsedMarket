# app/utils/validators.py
import re

def is_valid_username(username):
    """영문, 숫자, 밑줄 포함 3~20자"""
    return re.match(r'^[a-zA-Z0-9_]{3,20}$', username)

def is_valid_password(password):
    """8자 이상, 영문자 + 숫자 + 특수문자 포함"""
    return (
        len(password) >= 8 and
        re.search(r'[A-Za-z]', password) and
        re.search(r'\d', password) and
        re.search(r'[!@#$%^&*(),.?":{}|<>]', password)
    )
