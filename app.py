import os
import re
import sqlite3

from routes import routes
from mimes import get_mime
from views import NotFoundView

conn = sqlite3.connect('data.db')
cursor = conn.cursor()

# Таблица учетных данных пользователей
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        user_id INTEGER,  
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
#Таблица пользователи группы 
cursor.execute('''
    CREATE TABLE IF NOT EXISTS group_members (
        group_id INTEGER,
        user_id INTEGER,
        role TEXT CHECK(role IN ('owner', 'admin', 'member')) 
        )
''')
# Таблица Сообщения группы
cursor.execute('''
    CREATE TABLE IF NOT EXISTS group_messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        user_id INTEGER,
        message TEXT,
        timestamp INTEGER
        )
''')

conn.close()

def load(file_name):
    f = open(file_name, encoding='utf-8')
    data = f.read()
    f.close()
    return data

def app(environ, start_response):
    """
    (dict, callable( status: str,
                     headers: list[(header_name: str, header_value: str)]))
                  -> body: iterable of strings_
    """
    url = environ['REQUEST_URI']
    view = None
    
    for key in routes.keys():
        if re.match(key, url) is not None:
            view = routes[key](url)
            break
    
    if view is None:
        view = NotFoundView(url)
    
    resp = view.response(environ, start_response)  
    # Возвращаем HTTP-ответ с сгенерированной страницей
    return resp

