from utils import get_db_cursor
import uuid
from Crypto.Random import get_random_bytes

def create_session():
    """
    Создать идентификатор сессии.
    Создать сессионный ключ.
    """
    session_id = str(uuid.uuid4())
    with get_db_cursor() as cursor:
            key = get_random_bytes(16)
            cursor.execute(f"INSERT INTO session VALUES (?, ?)", (session_id, key))
            cursor.connection.commit()
    return (session_id, key)

def get_key(session_id):
    """
    Получить ключ по session_id
    """
    with get_db_cursor() as cursor:
        cursor.execute(f"SELECT key FROM session WHERE id = ?", (session_id, ))
        return cursor.fetchone()[0]


def delete_session(session_id):
        """
        Удаление сессии.
        """
        with get_db_cursor() as cursor: 
               cursor.execute(f"DELETE FROM session WHERE id = ?", (session_id,))
               cursor.connection.commit()
        return True