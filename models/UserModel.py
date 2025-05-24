import sqlite3
import logging
import bcrypt
import re
from werkzeug.utils import secure_filename
from typing import List, Dict, Optional
from collections import defaultdict
from contextlib import contextmanager
from utils import get_db_cursor
from datetime import datetime

class UserModel:
    @staticmethod
    def get_user_id(username: str) -> Optional[int]:
        """Получает ID пользователя по имени"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            result = cursor.fetchone()
            return result[0] if result else None

    @staticmethod
    def create_user(username: str, password: str) -> tuple:
        """
        Создает нового пользователя
        Возвращает (success, error_message)
        """
        if not re.match(r'^[a-zA-Zа-яА-Я0-9_-]{3,20}$', username):
            return False, 'Недопустимое имя пользователя'
        
        if len(password) < 6:
            return False, 'Пароль должен быть не менее 6 символов'

        try:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            with get_db_cursor() as cursor:
                cursor.execute(
                    'INSERT INTO users (username, password) VALUES (?, ?)',
                    (username, hashed_password)
                )
                cursor.connection.commit()
            return True, None
        except sqlite3.IntegrityError:
            return False, 'Пользователь с таким именем уже существует'
        except Exception as e:
            logging.error(f"Registration error: {str(e)}")
            return False, 'Ошибка сервера при регистрации'

    @staticmethod
    def authenticate(username: str, password: str) -> tuple:
        """
        Аутентификация пользователя
        Возвращает (user_id, error_message)
        """
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    'SELECT id, password FROM users WHERE username=?',
                    (username,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return None, 'Пользователь не найден'
                
                user_id, hashed_password = result
                if not bcrypt.checkpw(password.encode('utf-8'), hashed_password):
                    return None, 'Неверный пароль'
                
                return user_id, None
        except Exception as e:
            logging.error(f"Auth error: {str(e)}")
            return None, 'Ошибка аутентификации'

    @staticmethod
    def get_user_by_id(user_id: int) -> dict:
        """Получает данные пользователя по ID"""
        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT id, username FROM users WHERE id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            return {'id': result[0], 'username': result[1]} if result else None

    @staticmethod
    def search_users(query: str, exclude_user_id: int = None) -> list:
        """Поиск пользователей по имени"""
        with get_db_cursor() as cursor:
            params = [f'%{query}%']
            if exclude_user_id:
                cursor.execute(
                    'SELECT username FROM users WHERE username LIKE ? AND id != ? LIMIT 10',
                    (f'%{query}%', exclude_user_id)
                )
            else:
                cursor.execute(
                    'SELECT username FROM users WHERE username LIKE ? LIMIT 10',
                    (f'%{query}%',)
                )
            return [row[0] for row in cursor.fetchall()]