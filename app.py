import os
import re
import sqlite3
import time

from routes import routes
from mimes import get_mime
from views import NotFoundView
from utils import get_db_cursor


# Создание таблиц в базе данных
def initialize_database():
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
                name TEXT NOT NULL,
                creator_id INTEGER,
                created_at INTEGER,
                FOREIGN KEY(creator_id) REFERENCES users(user_id)
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
                role TEXT CHECK(role IN ('owner', 'admin', 'member')) 
            )
        ''')

        # Таблица сообщений групп
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                message TEXT,
                timestamp INTEGER
            )
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

def app(environ, start_response):
    """
    Основная функция приложения.

    :param environ: Словарь с переменными окружения и данными запроса.
    :param start_response: Функция для отправки HTTP-заголовков.
    :return: Тело HTTP-ответа.
    """
    # Логируем запрос
    url = environ['REQUEST_URI']

    try:
        # Поиск подходящего представления (view) для обработки запроса
        view = None
        for key in routes.keys():
            if re.match(key, url) is not None:
                view = routes[key](url)
                break

        # Если представление не найдено, используем NotFoundView
        if view is None:
            view = NotFoundView(url)

        # Генерация HTTP-ответа
        resp = view.response(environ, start_response)
        return resp

    except Exception as e:
        raise