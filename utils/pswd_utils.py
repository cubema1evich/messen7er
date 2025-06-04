import bcrypt
from contextlib import contextmanager

def hash_password(password):
    """
    Хеширует пароль с использованием bcrypt.
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(hashed_password, user_password):
    """
    Проверяет, соответствует ли пароль хешу.
    """
    return bcrypt.checkpw(user_password.encode('utf-8'), hashed_password)