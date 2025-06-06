import os
import re
import sqlite3
import time
import logging  

from routes import routes
from mimes import get_mime
from views import NotFoundView, InternalServerErrorView  
from utils import get_db_cursor


# Создание таблиц в базе данных
def initialize_database():
    # Папка для хранения файлов
    os.makedirs('static/uploads', exist_ok=True)

    """
    Инициализирует базу данных, создавая необходимые таблицы, если они не существуют.
    """
    with get_db_cursor() as cursor:
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL, 
                UNIQUE (username)
            )
        ''')

        # Таблица сообщений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                sender TEXT NOT NULL,
                message_text TEXT NOT NULL,
                timestamp INTEGER
            )
        ''')

        # Таблица групп
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                timestamp INTEGER,
                creator_id INTEGER,
                created_at INTEGER,
                FOREIGN KEY(creator_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица Вложений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_type TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                filename TEXT NOT NULL
            )               
        ''')

        # Создание общего чата, если он не существует
        cursor.execute('SELECT * FROM groups WHERE name = "Общий чат"')
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO groups (name, creator_id, created_at)
                VALUES ('Общий чат', 0, ?)
            ''', (int(time.time()),))

        # Таблица участников групп
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_members (
                group_id INTEGER,
                user_id INTEGER,
                timestamp INTEGER,
                role TEXT CHECK(role IN ('owner', 'admin', 'member')),
                joined_at INTEGER,
                UNIQUE (group_id, user_id),
                FOREIGN KEY(group_id) REFERENCES groups(group_id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        # Таблица сообщений групп
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                message_text TEXT,
                timestamp INTEGER
            )
        ''')

        #Таблица личных сообщений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS private_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                message_text TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                FOREIGN KEY(sender_id) REFERENCES users(id),
                FOREIGN KEY(receiver_id) REFERENCES users(id)
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_text_nocase 
            ON messages(message_text COLLATE NOCASE)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_private_messages_text_nocase 
            ON private_messages(message_text COLLATE NOCASE)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_group_messages_text_nocase 
            ON group_messages(message_text COLLATE NOCASE)
        ''')

        # Фиксируем изменения в базе данных
        cursor.connection.commit()

# Инициализация базы данных при запуске приложения
initialize_database()

def load(file_name):
    """
    Загружает содержимое файла.

    :param file_name: Имя файла.
    :return: Содержимое файла в виде строки.
    """
    with open(file_name, encoding='utf-8') as f:
        data = f.read()
    return data

def serve_static(environ, start_response):
    """Обработка статических файлов."""
    file_path = environ['REQUEST_URI'][1:]
    if not os.path.exists(file_path):
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'File not found']
    
    with open(file_path, 'rb') as f:
        data = f.read()
    
    mime_type = get_mime(file_path)
    start_response('200 OK', [('Content-Type', mime_type)])
    return [data]

def app(environ, start_response):
    """
    Основная функция приложения.

    :param environ: Словарь с переменными окружения и данными запроса.
    :param start_response: Функция для отправки HTTP-заголовков.
    :return: Тело HTTP-ответа.
    """

    url = environ['PATH_INFO']
    view = None
    matched_key = None  
        
    try:
        for key in routes.keys():
            if re.match(key, url):
                view = routes[key](url)
                matched_key = key 
                break

        if not view:
            view = NotFoundView(url)

        if matched_key:
            match = re.match(matched_key, url)
            if match:
                environ['url_params'] = match.groups()

        return view.response(environ, start_response)
        
    except Exception as e:
        logging.error(f"Server error: {str(e)}", exc_info=True)
        error_view = InternalServerErrorView('/500')
        return error_view.response(environ, start_response)