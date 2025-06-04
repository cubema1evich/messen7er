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