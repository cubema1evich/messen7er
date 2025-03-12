import bcrypt
import sqlite3
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    """
    Контекстный менеджер для работы с базой данных.
    Автоматически открывает и закрывает соединение.
    """
    conn = sqlite3.connect('data.db')
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def get_db_cursor():
    """
    Контекстный менеджер для работы с курсором базы данных.
    Автоматически открывает и закрывает курсор.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

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