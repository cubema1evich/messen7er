import unittest
import sqlite3
import time
import os
from utils.db_utils import *
from contextlib import contextmanager
from io import BytesIO
from datetime import datetime
from unittest.mock import patch

def init_schema(conn):
    """
    Создаёт схему БД для тестирования, создавая таблицы,
    необходимые для работы модели данных.
    """
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL, 
            UNIQUE (username)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            creator_id INTEGER,
            created_at INTEGER
        )
    ''')
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER,
            user_id INTEGER,
            role TEXT CHECK(role IN ('owner', 'admin', 'member')),
            joined_at INTEGER,
            UNIQUE (group_id, user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            message_text TEXT,
            timestamp INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS private_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_private_messages_text_nocase 
        ON private_messages(message_text COLLATE NOCASE)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_group_messages_text_nocase 
        ON group_messages(message_text COLLATE NOCASE)
    ''')
    conn.commit()

# Импорт тестируемых моделей
from models.UserModel import UserModel
from models.GroupModel import GroupModel
from models.MessageModel import MessageModel

######################################
#            ПОЛЬЗОВАТЕЛЬ            #
######################################
class TestUserModel(unittest.TestCase):
    def setUp(self):
        """
        Создаёт in‑memory БД и инициализирует схему для тестов модели пользователей.
        """
        self.conn = sqlite3.connect(":memory:")
        init_schema(self.conn)
        from utils import db_utils
        self.original_get_db_connection = db_utils.get_db_connection
        db_utils.get_db_connection = lambda: self.conn

    def tearDown(self):
        from utils import db_utils
        self.conn.close()
        db_utils.get_db_connection = self.original_get_db_connection

    def test_create_user_valid(self):
        """Проверка успешного создания пользователя с валидными данными."""
        success, error = UserModel.create_user("testuser", "password123")
        self.assertTrue(success)
        self.assertIsNone(error)

    def test_create_user_invalid_username(self):
        """Проверка, что создание пользователя с недопустимым именем завершается ошибкой."""
        success, error = UserModel.create_user("ab", "password123")
        self.assertFalse(success)
        self.assertIsNotNone(error)

    def test_create_user_duplicate(self):
        """Проверка, что невозможно создать пользователя с уже существующим именем."""
        UserModel.create_user("dupuser", "password123")
        success, error = UserModel.create_user("dupuser", "password456")
        self.assertFalse(success)
        self.assertIn("существует", error.lower())

    def test_authenticate_success(self):
        """Проверка успешной аутентификации пользователя с правильным паролем."""
        UserModel.create_user("authuser", "securepass")
        user_id, error = UserModel.authenticate("authuser", "securepass")
        self.assertIsNotNone(user_id)
        self.assertIsNone(error)

    def test_authenticate_wrong_password(self):
        """Проверка, что при вводе неверного пароля аутентификация не проходит."""
        UserModel.create_user("authuser2", "securepass")
        user_id, error = UserModel.authenticate("authuser2", "wrongpass")
        self.assertIsNone(user_id)
        self.assertIn("неверный", error.lower())

    def test_get_user_by_id(self):
        """Проверка корректного получения данных пользователя по его ID."""
        UserModel.create_user("getuser", "pass123")
        user_id = UserModel.get_user_id("getuser")
        user = UserModel.get_user_by_id(user_id)
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "getuser")

    def test_basic_user_search(self):
        """Тестирование базового поиска пользователей по имени"""
        test_users = ["alice", "bob", "charlie", "alex", "alina"]
        for username in test_users:
            UserModel.create_user(username, "password123")

        search_results = UserModel.search_users("ali")
        expected_users = ["alice", "alina"]
        self.assertEqual(
            set(search_results),
            set(expected_users),
            f"Поиск по 'ali' должен находить {expected_users}, но найдено {search_results}"
        )

    def test_authenticate_invalid_user(self):
        """Проверка аутентификации несуществующего пользователя."""
        user_id, error = UserModel.authenticate("ghost_user", "password")
        self.assertIsNone(user_id)
        self.assertIn("не найден", error.lower())

######################################
#             ГРУППЫ               #
######################################
class TestGroupModel(unittest.TestCase):
    def setUp(self):
        """
        Инициализирует in‑memory БД для тестирования логики групп и создаёт базового пользователя (владельца).
        """
        self.conn = sqlite3.connect(":memory:")
        init_schema(self.conn)
        from utils import db_utils
        self.original_get_db_connection = db_utils.get_db_connection
        db_utils.get_db_connection = lambda: self.conn
        UserModel.create_user("group_owner", "password")
        self.owner_id = UserModel.get_user_id("group_owner")

    def tearDown(self):
        """
        Завершает работу in‑memory БД и восстанавливает оригинальный get_db_connection.
        """
        from utils import db_utils
        self.conn.close()
        db_utils.get_db_connection = self.original_get_db_connection

    def test_create_group_valid(self):
        """Проверка успешного создания группы с уникальным именем."""
        result = GroupModel.create_group("Test Group", self.owner_id)
        self.assertIn("group_id", result)
        self.assertEqual(result["status"], "success")

    def test_create_group_duplicate(self):
        """Проверка создания группы с уже существующим именем."""
        GroupModel.create_group("Unique Group", self.owner_id)
        result = GroupModel.create_group("Unique Group", self.owner_id)
        self.assertIn("error", result)

    def test_add_member(self):
        """Проверка успешного добавления участника в группу."""
        group_result = GroupModel.create_group("Member Group", self.owner_id)
        group_id = group_result.get("group_id")
        UserModel.create_user("member_user", "password")
        member_id = UserModel.get_user_id("member_user")
        add_result = GroupModel.add_member(group_id, member_id)
        self.assertIn("status", add_result)
        self.assertEqual(add_result["status"], "success")

    def test_add_member_already_exists(self):
        """Проверка, что повторное добавление того же участника возвращает ошибку."""
        group_result = GroupModel.create_group("Repeat Member Group", self.owner_id)
        group_id = group_result.get("group_id")
        UserModel.create_user("repeat_user", "password")
        member_id = UserModel.get_user_id("repeat_user")
        GroupModel.add_member(group_id, member_id)
        add_result = GroupModel.add_member(group_id, member_id)
        self.assertIn("error", add_result)

    def test_remove_member_insufficient_rights(self):
        """Проверка, что пользователь без прав не может удалить владельца группы."""
        group_result = GroupModel.create_group("Remove Test Group", self.owner_id)
        group_id = group_result.get("group_id")
        UserModel.create_user("non_admin", "password")
        non_admin_id = UserModel.get_user_id("non_admin")
        GroupModel.add_member(group_id, non_admin_id)
        remove_result = GroupModel.remove_member(group_id, self.owner_id, non_admin_id)
        self.assertIn("error", remove_result)

    def test_rename_group_success(self):
        """Проверка успешного изменения названия группы владельцем"""
        owner_id = self.owner_id
        group = GroupModel.create_group("Old Name", owner_id)
        group_id = group['group_id']
        
        # Пытаемся изменить название
        result = GroupModel.rename_group(
            group_id=group_id,
            new_name="New Name",
            user_id=owner_id
        )
        
        self.assertEqual(result.get("status"), "success")
        
        # Проверяем, что название изменилось в БД
        with get_db_cursor() as cursor:
            cursor.execute("SELECT name FROM groups WHERE group_id = ?", (group_id,))
            self.assertEqual(cursor.fetchone()[0], "New Name")

    def test_rename_group_insufficient_permissions(self):
        """Проверка отказа в изменении названия без прав"""
        owner_id = self.owner_id
        UserModel.create_user("regular_user", "pass")
        member_id = UserModel.get_user_id("regular_user")
        
        group = GroupModel.create_group("Permission Test Group", owner_id)
        group_id = group['group_id']
        GroupModel.add_member(group_id, member_id)
        
        result = GroupModel.rename_group(
            group_id=group_id,
            new_name="Unauthorized Rename",
            user_id=member_id  # Обычный участник без прав
        )
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Недостаточно прав для изменения названия")

    def test_rename_group_duplicate_name(self):
        """Проверка невозможности дублирования названия группы"""
        owner_id = self.owner_id
        
        # Создаем две группы
        GroupModel.create_group("Existing Group", owner_id)
        group2 = GroupModel.create_group("Group To Rename", owner_id)
        group2_id = group2['group_id']
        
        # Пытаемся переименовать во существующее название
        result = GroupModel.rename_group(
            group_id=group2_id,
            new_name="Existing Group",  # Такое название уже есть
            user_id=owner_id
        )
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Группа с таким именем уже существует")

    def test_rename_nonexistent_group(self):
        """Проверка попытки переименования несуществующей группы"""
        owner_id = self.owner_id
        
        result = GroupModel.rename_group(
            group_id=99999,  # Несуществующий ID
            new_name="New Name",
            user_id=owner_id
        )
        
        self.assertIn("error", result)
    
    def test_leave_group_non_owner(self):
        """Проверка, что обычный участник корректно покидает группу (группа не удаляется)."""
        group_result = GroupModel.create_group("Leave Group", self.owner_id)
        group_id = group_result.get("group_id")
        UserModel.create_user("normal_member", "password")
        member_id = UserModel.get_user_id("normal_member")
        GroupModel.add_member(group_id, member_id)
        leave_result = GroupModel.leave_group(group_id, member_id)
        self.assertEqual(leave_result.get("is_group_deleted"), False)

    def test_leave_group_owner(self):
        """Проверка, что покидание группы владельцем приводит к удалению группы."""
        group_result = GroupModel.create_group("Owner Leave Group", self.owner_id)
        group_id = group_result.get("group_id")
        leave_result = GroupModel.leave_group(group_id, self.owner_id)
        self.assertEqual(leave_result.get("is_group_deleted"), True)

    def test_change_role_success(self):
        """Проверка успешного изменения роли участника"""
        # Используем существующего владельца из setUp
        owner_id = self.owner_id
        
        # Создаем нового пользователя
        UserModel.create_user("test_member", "password")
        member_id = UserModel.get_user_id("test_member")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Добавляем участника
        GroupModel.add_member(group_id, member_id)
        
        # Меняем роль участника (owner меняет роль member)
        result = GroupModel.change_role(
            group_id=group_id,
            user_id=member_id,
            new_role="admin",
            changer_id=owner_id
        )
        self.assertEqual(result.get("status"), "success")

    def test_change_role_insufficient_permissions(self):
        """Проверка недостаточных прав для изменения роли"""
        # Используем существующего владельца из setUp
        owner_id = self.owner_id
        
        # Создаем двух новых пользователей
        UserModel.create_user("member1", "password")
        UserModel.create_user("member2", "password")
        member1_id = UserModel.get_user_id("member1")
        member2_id = UserModel.get_user_id("member2")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Добавляем участников
        GroupModel.add_member(group_id, member1_id)
        GroupModel.add_member(group_id, member2_id)
        
        # Пытаемся изменить роль без прав
        result = GroupModel.change_role(
            group_id=group_id,
            user_id=member2_id,
            new_role="admin",
            changer_id=member1_id  # Обычный участник без прав
        )
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Недостаточно прав")

    def test_change_role_user_not_in_group(self):
        """Проверка изменения роли пользователя не из группы"""
        # Используем существующего владельца из setUp
        owner_id = self.owner_id
        
        # Создаем пользователя не из группы
        UserModel.create_user("outsider", "password")
        outsider_id = UserModel.get_user_id("outsider")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Пытаемся изменить роль пользователя, которого нет в группе
        result = GroupModel.change_role(
            group_id=group_id,
            user_id=outsider_id,
            new_role="member",
            changer_id=owner_id
        )
        self.assertIn("error", result)
        self.assertEqual(result["error"], "User not in group")

    def test_change_owner_role(self):
        """Проверка невозможности изменения роли владельца"""
        # Используем существующего владельца из setUp
        owner_id = self.owner_id
        
        # Создаем нового пользователя
        UserModel.create_user("test_admin", "password")
        admin_id = UserModel.get_user_id("test_admin")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Добавляем админа
        GroupModel.add_member(group_id, admin_id, "admin")
        
        # Пытаемся изменить роль владельца
        result = GroupModel.change_role(
            group_id=group_id,
            user_id=owner_id,
            new_role="admin",
            changer_id=admin_id
        )
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Нельзя изменить владельца")

    def test_get_user_groups(self):
        """Проверка получения списка групп пользователя."""
        GroupModel.create_group("Group 1", self.owner_id)
        GroupModel.create_group("Group 2", self.owner_id)
        groups = GroupModel.get_user_groups(self.owner_id)
        self.assertEqual(len(groups), 2)

    def test_check_group_access(self):
        """Проверка доступа к группе (разрешён/запрещён)."""
        group = GroupModel.create_group("Access Test Group", self.owner_id)
        group_id = group.get("group_id")
        UserModel.create_user("random_user", "pass")
        random_id = UserModel.get_user_id("random_user")
        access = GroupModel.check_group_access(group_id, random_id)
        self.assertFalse(access)
        
    def test_add_member_nonexistent_group(self):
        """Проверка добавления участника в несуществующую группу."""
        result = GroupModel.add_member(999, self.owner_id)
        self.assertIn("error", result)

    def test_remove_member_not_found(self):
        """Проверка удаления несуществующего участника."""
        group_id = GroupModel.create_group("Test Group", self.owner_id)["group_id"]
        result = GroupModel.remove_member(group_id, 999, self.owner_id)
        self.assertIn("error", result)

    def test_owner_cannot_remove_other_owner(self):
        """Проверка, что один владелец не может исключить другого владельца."""
        # 1. Создаем первого владельца
        UserModel.create_user("owner1", "pass123")
        owner1_id = UserModel.get_user_id("owner1")
        
        # 2. Создаем второго владельца
        UserModel.create_user("owner2", "pass456")
        owner2_id = UserModel.get_user_id("owner2")
        
        # 3. Создаем группу с первым владельцем
        group = GroupModel.create_group("Test Group", owner1_id)
        group_id = group['group_id']
        
        # 4. Делаем второго пользователя тоже владельцем (напрямую в БД)
        with get_db_cursor() as cursor:
            cursor.execute('''
                INSERT INTO group_members 
                (group_id, user_id, role, joined_at)
                VALUES (?, ?, ?, ?)
            ''', (group_id, owner2_id, 'owner', int(time.time())))
            cursor.connection.commit()
        
        # 5. Пытаемся удалить owner2 из группы от имени owner1
        result = GroupModel.remove_member(
            group_id=group_id,
            user_id=owner2_id,
            remover_id=owner1_id
        )
        
        # Проверяем, что получили ошибку
        self.assertIn('error', result)
        self.assertIn('Нельзя удалить владельца', result['error'])
        
        # Проверяем, что owner2 остался в группе
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT 1 FROM group_members 
                WHERE group_id = ? AND user_id = ?
            ''', (group_id, owner2_id))
            self.assertIsNotNone(cursor.fetchone(), "Owner2 был удален из группы")

######################################
#           СООБЩЕНИЯ              #
######################################
class TestMessageModel(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        init_schema(self.conn)
        from utils import db_utils
        self.original_get_db_connection = db_utils.get_db_connection
        db_utils.get_db_connection = lambda: self.conn
        UserModel.create_user("msg_sender", "pass")
        UserModel.create_user("msg_receiver", "pass")
        self.sender_id = UserModel.get_user_id("msg_sender")
        self.receiver_id = UserModel.get_user_id("msg_receiver")
    
    def tearDown(self):
        from utils import db_utils
        self.conn.close()
        db_utils.get_db_connection = self.original_get_db_connection

    # Вспомогательные методы
    def create_test_user(self, username):
        """Создает тестового пользователя и возвращает его ID"""
        UserModel.create_user(username, "password")
        return UserModel.get_user_id(username)

    def create_two_users(self):
        """Создает двух тестовых пользователей"""
        user1_id = self.create_test_user("user1")
        user2_id = self.create_test_user("user2")
        return user1_id, user2_id

    def create_general_message(self, user_id, text):
        """Создает сообщение в общем чате"""
        return MessageModel.create_message("general", user_id, text)

    def create_group_with_users(self):
        """Создает группу с владельцем и участником"""
        owner_id = self.create_test_user("owner")
        member_id = self.create_test_user("member")
        group = GroupModel.create_group("Test Group", owner_id)
        GroupModel.add_member(group['group_id'], member_id)
        return owner_id, member_id

    def assert_attachments_deleted(self, message_id, message_type):
        """Проверяет что вложения удалены"""
        with get_db_cursor() as cursor:
            cursor.execute('''
                SELECT 1 FROM attachments 
                WHERE message_type = ? AND message_id = ?
            ''', (message_type, message_id))
            self.assertIsNone(cursor.fetchone())

    def test_create_general_message(self):
        """Проверка успешного создания сообщения общего чата."""
        message_id = self.create_general_message(self.sender_id, "Hello general")
        self.assertIsNotNone(message_id)
    
    def test_create_private_message(self):
        # Создаём тестовых пользователей
        sender = UserModel.create_user("test_sender", "password123")
        receiver = UserModel.create_user("test_receiver", "password123")
        
        # Получаем их ID (важно проверить, что они не None)
        sender_id = UserModel.get_user_id("test_sender")
        receiver_id = UserModel.get_user_id("test_receiver")
        
        # Проверяем создание сообщения
        message_id = MessageModel.create_message(
            message_type="private",
            user_id=sender_id,
            message_text="Hello",
            receiver_id=receiver_id
        )
        self.assertIsNotNone(message_id)
    
    def test_edit_message_fail(self):
        """Проверка, что редактирование сообщения другим пользователем не проходит."""
        message_id = MessageModel.create_message("general", self.sender_id, "Original text")
        success = MessageModel.edit_message("general", message_id, self.receiver_id, "Hacked text")
        self.assertFalse(success)
    
    def test_delete_message_fail(self):
        """Проверка, что удаление чужого сообщения завершается неудачей."""
        message_id = MessageModel.create_message("general", self.sender_id, "Message to delete")
        success = MessageModel.delete_message("general", message_id, self.receiver_id)
        self.assertFalse(success)
    
    def test_get_group_messages(self):
        """Проверка получения сообщений группы с учетом timestamp."""
        # Создаем группу
        GroupModel.create_group("Msg Group", self.sender_id)
        group_id = 1  # Если только одна группа—ID будет равен 1
        # Вставляем сообщение в группу
        mid1 = MessageModel.create_message("group", self.sender_id, "Group Msg 1", group_id)
        time.sleep(0.1)
        mid2 = MessageModel.create_message("group", self.sender_id, "Group Msg 2", group_id)
        messages = MessageModel.get_group_messages(group_id, 0)
        self.assertEqual(len(messages), 2)
    
    def test_search_messages_general(self):
        """Проверка поиска сообщений в общем чате по ключевому слову."""
        # Создаем несколько сообщений с искомой подстрокой
        MessageModel.create_message("general", self.sender_id, "This is a searchTest message")
        MessageModel.create_message("general", self.sender_id, "Another searchTest example")
        result = MessageModel.search_messages("searchTest", "general", None, self.sender_id, page=1, per_page=10, sort="date")
        self.assertGreater(result.get("total", 0), 0)
        self.assertTrue(len(result.get("messages", [])) > 0)

    def test_add_attachment(self):
        """Проверка добавления вложения к сообщению."""
        msg_id = MessageModel.create_message("general", self.sender_id, "Test message")
        attachment_id = MessageModel.add_attachment("general", msg_id, "file.pdf", "application/pdf", "file.pdf")
        self.assertIsNotNone(attachment_id)

    def test_delete_message_non_existent(self):
        """Проверка удаления несуществующего сообщения."""
        success = MessageModel.delete_message("general", 999, self.sender_id)
        self.assertFalse(success)

    def test_edit_message_non_existent(self):
        """Проверка редактирования несуществующего сообщения."""
        success = MessageModel.edit_message("general", 999, self.sender_id, "Updated text")
        self.assertFalse(success)

    def test_save_uploaded_file_invalid(self):
        """Проверка обработки невалидного файла."""
        class InvalidFile:
            file = None
            filename = None
            type = None

        result = MessageModel.save_uploaded_file(InvalidFile(), "static/uploads")
        self.assertIsNone(result)

    def test_save_uploaded_file_exists(self):
        """Проверка случая, когда файл уже существует."""
        class MockFile:
            def __init__(self):
                self.file = BytesIO(b"content")
                self.filename = "exist.txt"
                self.type = "text/plain"

        # Первое сохранение
        file_path = MessageModel.save_uploaded_file(MockFile(), "static/uploads")
        # Повторное сохранение (должно вернуть путь без ошибок)
        file_path_2 = MessageModel.save_uploaded_file(MockFile(), "static/uploads")
        self.assertEqual(file_path, file_path_2)

    def test_edit_private_message_not_owner(self):
        """Проверка запрета редактирования чужого приватного сообщения."""
        msg_id = MessageModel.create_message(
            "private", 
            self.sender_id, 
            "Private", 
            None, 
            self.receiver_id
        )
        # Пытаемся изменить сообщение получателем (должно быть запрещено)
        success = MessageModel.edit_message("private", msg_id, self.receiver_id, "Edited")
        self.assertFalse(success)

    def test_search_messages_empty_query(self):
        """Проверка поиска с пустым запросом."""
        result = MessageModel.search_messages(
            "", 
            "general", 
            None, 
            self.sender_id,
            page=1,
            per_page=10,
            sort="date"
        )
        self.assertEqual(result["total"], 0)

    def test_edit_private_message_fail(self):
        """Проверка невозможности редактирования личного сообщения другим пользователем."""
        message_id = MessageModel.create_message("private", self.sender_id, "Original private", None, self.receiver_id)
        
        success = MessageModel.edit_message("private", message_id, self.receiver_id, "Hacked private")
        self.assertFalse(success, "Чужие личные сообщения не должны редактироваться!")

    def test_edit_group_message_fail(self):
        """Проверка невозможности редактирования чужого сообщения обычным участником"""
        # Создаем группу с владельцем и участником
        owner_id = self.create_test_user("owner")
        member_id = self.create_test_user("member")
        group = GroupModel.create_group("Edit Test Group", owner_id)
        group_id = group['group_id']
        GroupModel.add_member(group_id, member_id)

        # Создаем сообщение от владельца
        original_text = "Original message from owner"
        msg_id = MessageModel.create_message(
            "group",
            owner_id,
            original_text,
            group_id=group_id
        )

        # Пытаемся редактировать сообщение от имени участника
        new_text = "Edited by member"
        success = MessageModel.edit_message(
            "group",
            msg_id,
            member_id,
            new_text
        )
        
        self.assertFalse(success, "Обычный участник не должен редактировать чужие сообщения")

        # Проверяем, что текст не изменился (без использования контекстного менеджера)
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT message_text FROM group_messages WHERE message_id = ?",
                (msg_id,)
            )
            result = cursor.fetchone()
            self.assertEqual(result[0], original_text)
        finally:
            cursor.close()

    def test_edit_group_message_by_member_fail(self):
        """Проверка невозможности редактирования чужого сообщения обычным участником."""
        group_result = GroupModel.create_group("Member Edit Group", self.sender_id)
        group_id = group_result.get("group_id")

        UserModel.create_user("member_user", "pass")
        member_id = UserModel.get_user_id("member_user")
        GroupModel.add_member(group_id, member_id)

        message_id = MessageModel.create_message("group", self.sender_id, "Original text", group_id)
        
        success = MessageModel.edit_message("group", message_id, member_id, "Hacked text")
        self.assertFalse(success, "Обычный участник не должен редактировать чужие сообщения!")

    def test_process_messages_with_attachments(self):
        """Проверка обработки сообщений с вложениями."""
        # Создаем тестовые данные, имитирующие результат SQL-запроса
        test_data = [
            (1, "user1", "text1", 100, "/path1", "image/png", "file1.png", "general", 1),
            (1, "user1", "text1", 100, "/path2", "image/jpeg", "file2.jpg", "general", 1),
            (2, "user2", "text2", 200, None, None, None, "general", 2)
        ]
        
        # Создаем mock курсор
        class MockCursor:
            def fetchall(self):
                return test_data
        
        # Вызываем тестируемый метод
        messages = MessageModel._process_messages(MockCursor())
        
        # Проверяем результаты
        self.assertEqual(len(messages), 2)
        
        # Проверяем сообщение с вложениями
        msg_with_attachments = next(m for m in messages if m['id'] == 1)
        self.assertEqual(len(msg_with_attachments['attachments']), 2)
        self.assertEqual(msg_with_attachments['attachments'][0]['filename'], "file1.png")
        
        # Проверяем сообщение без вложений
        msg_no_attachments = next(m for m in messages if m['id'] == 2)
        self.assertEqual(len(msg_no_attachments['attachments']), 0)

    def test_system_messages_in_groups(self):
        """Проверка системных сообщений в групповых чатах."""
        # Создаем группу
        group_result = GroupModel.create_group("System Msg Group", self.sender_id)
        group_id = group_result.get("group_id")
        
        # Добавляем системное сообщение (user_id = 0)
        msg_id = MessageModel.create_message(
            "group", 
            0,  # System
            "System message", 
            group_id
        )
        
        # Получаем сообщения группы
        messages = MessageModel.get_group_messages(group_id, 0)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['sender'], "System")
        self.assertEqual(messages[0]['user_id'], 0)

    def test_get_general_messages(self):
        """Проверка получения сообщений общего чата с учетом timestamp."""
        # Создаем тестовые данные вручную, так как моки времени не работают с SQLite
        with get_db_cursor() as cursor:
            # Первое сообщение (timestamp = 1000)
            cursor.execute('''
                INSERT INTO group_messages 
                (group_id, user_id, message_text, timestamp)
                VALUES (0, ?, ?, ?)
            ''', (self.sender_id, "First message", 1000))
            
            # Второе сообщение (timestamp = 2000)
            cursor.execute('''
                INSERT INTO group_messages 
                (group_id, user_id, message_text, timestamp)
                VALUES (0, ?, ?, ?)
            ''', (self.sender_id, "Second message", 2000))
            
            cursor.connection.commit()
        
        # Проверяем получение всех сообщений
        all_messages = MessageModel.get_general_messages(0)
        self.assertEqual(len(all_messages), 2, "Должны получить все сообщения")
        
        # Проверяем фильтрацию по timestamp (должны получить только второе сообщение)
        filtered_messages = MessageModel.get_general_messages(1500)
        self.assertEqual(len(filtered_messages), 1, "Должны получить только второе сообщение")
        self.assertEqual(filtered_messages[0]['message_text'], "Second message")
        
        # Проверяем пустой результат для будущего timestamp
        no_messages = MessageModel.get_general_messages(3000)
        self.assertEqual(len(no_messages), 0, "Не должно быть сообщений с будущим timestamp")

    def test_get_private_chats(self):
        """Проверка получения списка приватных чатов пользователя."""
        # Чистим таблицы перед тестом
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM private_messages")
            cursor.execute("DELETE FROM users")
            cursor.connection.commit()

        # Создаём тестовых пользователей с проверкой
        test_users = [
            ("user1", "pass12"),
            ("user2", "pass23"),
            ("user3", "pass34")
        ]
        for username, password in test_users:
            success, error = UserModel.create_user(username, password)
            self.assertTrue(success, f"Не удалось создать пользователя {username}: {error}")

        # Получаем ID пользователей с проверкой
        user1_id = UserModel.get_user_id("user1")
        user2_id = UserModel.get_user_id("user2") 
        user3_id = UserModel.get_user_id("user3")
        
        self.assertIsNotNone(user1_id, "Не найден ID для user1")
        self.assertIsNotNone(user2_id, "Не найден ID для user2")
        self.assertIsNotNone(user3_id, "Не найден ID для user3")

        # Создаём приватные сообщения
        with get_db_cursor() as cursor:
            # Первое сообщение
            cursor.execute('''
                INSERT INTO private_messages 
                (sender_id, receiver_id, message_text, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (user1_id, user2_id, "Hello user2", 1000))
            
            # Ответное сообщение
            cursor.execute('''
                INSERT INTO private_messages 
                (sender_id, receiver_id, message_text, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (user2_id, user1_id, "Hi user1", 2000))
            
            # Сообщение другому пользователю
            cursor.execute('''
                INSERT INTO private_messages 
                (sender_id, receiver_id, message_text, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (user1_id, user3_id, "Hello user3", 1500))
            
            cursor.connection.commit()

        # Проверяем чаты для user1
        chats = MessageModel.get_private_chats(user1_id)
        self.assertEqual(len(chats), 2, f"Должны быть чаты с user2 и user3, получено: {chats}")
        
        # Проверяем сортировку по времени (последнее сообщение первое)
        usernames = [chat['username'] for chat in chats]
        self.assertEqual(usernames, ["user2", "user3"])
        
        # Проверяем last_activity
        self.assertEqual(chats[0]['last_activity'], 2000)  # Последнее сообщение от user2
        self.assertEqual(chats[1]['last_activity'], 1500)  # Последнее сообщение user1→user3

    def test_get_private_messages_by_username(self):
        """Проверка получения приватных сообщений по username собеседника."""
        # 1. Подготовка - очищаем таблицы
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM private_messages")
            cursor.execute("DELETE FROM users")
            cursor.connection.commit()

        # 2. Создаем тестовых пользователей (более надежный способ)
        users = [
            ("alice", "pass123"),
            ("bob", "pass456")
        ]
        for username, password in users:
            success, error = UserModel.create_user(username, password)
            self.assertTrue(success, f"Failed to create user {username}: {error}")

        # 3. Получаем ID пользователей
        alice_id = UserModel.get_user_id("alice")
        bob_id = UserModel.get_user_id("bob")
        self.assertIsNotNone(alice_id, "Alice ID not found")
        self.assertIsNotNone(bob_id, "Bob ID not found")

        # 4. Создаем тестовые сообщения с явными timestamp
        test_messages = [
            (alice_id, bob_id, "Привет, Боб!", 1000),
            (bob_id, alice_id, "Привет, Алиса!", 2000),
            (alice_id, bob_id, "Как дела?", 3000)
        ]

        with get_db_cursor() as cursor:
            for sender, receiver, text, ts in test_messages:
                cursor.execute('''
                    INSERT INTO private_messages
                    (sender_id, receiver_id, message_text, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (sender, receiver, text, ts))
            cursor.connection.commit()

        # 5. Тестируем получение сообщений по username
        # 5.1. Алиса запрашивает переписку с Бобом
        messages = MessageModel.get_private_messages(
            user_id=alice_id,
            other_user_id="bob",  # Используем username
            timestamp=0  # Получить все сообщения
        )
        
        self.assertEqual(len(messages), 3, f"Должны получить все 3 сообщения, получено: {len(messages)}")
        
        # 5.2. Проверяем правильность порядка (по возрастанию timestamp)
        self.assertEqual(messages[0]['message_text'], "Привет, Боб!")
        self.assertEqual(messages[1]['message_text'], "Привет, Алиса!")
        self.assertEqual(messages[2]['message_text'], "Как дела?")

        # 5.3. Проверяем фильтрацию по времени (только сообщения после ts=1500)
        filtered = MessageModel.get_private_messages(
            user_id=alice_id,
            other_user_id="bob",
            timestamp=1500
        )
        self.assertEqual(len(filtered), 2, "Должны получить 2 сообщения после ts=1500")
        self.assertEqual(filtered[0]['message_text'], "Привет, Алиса!")

    def test_delete_general_message_by_owner(self):
        """Пользователь может удалить свое сообщение в общем чате"""
        user_id = self.create_test_user("user1")
        msg_id = self.create_general_message(user_id, "Test message")
        
        result = MessageModel.delete_message("general", msg_id, user_id)
        self.assertTrue(result, "Должно разрешать удаление своего сообщения")

    def test_delete_general_message_by_other_user(self):
        """Чужой пользователь не может удалить сообщение в общем чате"""
        user1_id = self.create_test_user("user1")
        user2_id = self.create_test_user("user2")
        msg_id = self.create_general_message(user1_id, "Test message")
        
        result = MessageModel.delete_message("general", msg_id, user2_id)
        self.assertFalse(result, "Не должно разрешать удаление чужого сообщения")

    def test_delete_nonexistent_general_message(self):
        """Попытка удалить несуществующее сообщение в общем чате"""
        user_id = self.create_test_user("user1")
        
        result = MessageModel.delete_message("general", 99999, user_id)
        self.assertFalse(result, "Не должно разрешать удаление несуществующего сообщения")
    
    def test_delete_private_message_by_owner(self):
        """Проверка, что пользователь может удалить свое приватное сообщение."""
        # Создаем тестовых пользователей
        sender_id = self.create_test_user("sender")
        receiver_id = self.create_test_user("receiver")
        
        # Создаем приватное сообщение
        msg_id = MessageModel.create_message(
            "private", 
            sender_id, 
            "Private message", 
            receiver_id=receiver_id
        )
        
        # Пытаемся удалить сообщение отправителем
        result = MessageModel.delete_message("private", msg_id, sender_id)
        self.assertTrue(result, "Отправитель должен иметь возможность удалить свое сообщение")
        
        # Проверяем, что сообщение действительно удалено
        with get_db_cursor() as cursor:
            cursor.execute("SELECT 1 FROM private_messages WHERE id = ?", (msg_id,))
            self.assertIsNone(cursor.fetchone(), "Сообщение должно быть удалено из БД")

    def test_delete_private_message_by_non_owner(self):
        """Проверка, что нельзя удалить чужое приватное сообщение."""
        # Создаем тестовых пользователей
        sender_id = self.create_test_user("sender")
        receiver_id = self.create_test_user("receiver")
        other_user_id = self.create_test_user("other")
        
        # Создаем приватное сообщение
        msg_id = MessageModel.create_message(
            "private", 
            sender_id, 
            "Private message", 
            receiver_id=receiver_id
        )
        
        # Пытаемся удалить сообщение третьим пользователем
        result = MessageModel.delete_message("private", msg_id, other_user_id)
        self.assertFalse(result, "Чужой пользователь не должен иметь возможность удалить приватное сообщение")

    def test_delete_group_message_by_admin(self):
        """Проверка, что админ группы может удалить любое сообщение в группе."""
        # Создаем группу и пользователей
        owner_id = self.create_test_user("owner")
        admin_id = self.create_test_user("admin")
        member_id = self.create_test_user("member")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Делаем второго пользователя админом
        GroupModel.add_member(group_id, admin_id, "admin")
        # Добавляем обычного участника
        GroupModel.add_member(group_id, member_id)
        
        # Создаем сообщение от обычного участника
        msg_id = MessageModel.create_message(
            "group", 
            member_id, 
            "Member message", 
            group_id=group_id
        )
        
        # Пытаемся удалить сообщение админом
        result = MessageModel.delete_message("group", msg_id, admin_id)
        self.assertTrue(result, "Админ должен иметь возможность удалить любое сообщение в группе")

    def test_delete_group_message_by_regular_member(self):
        """Проверка, что обычный участник может удалить только свои сообщения."""
        # Создаем группу и пользователей
        owner_id = self.create_test_user("owner")
        member1_id = self.create_test_user("member1")
        member2_id = self.create_test_user("member2")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Добавляем участников
        GroupModel.add_member(group_id, member1_id)
        GroupModel.add_member(group_id, member2_id)
        
        # Создаем сообщение от первого участника
        msg_id = MessageModel.create_message(
            "group", 
            member1_id, 
            "Member1 message", 
            group_id=group_id
        )
        
        # Пытаемся удалить сообщение вторым участником
        result = MessageModel.delete_message("group", msg_id, member2_id)
        self.assertFalse(result, "Обычный участник не должен иметь возможность удалить чужое сообщение")
        
        # Пытаемся удалить свое сообщение
        msg2_id = MessageModel.create_message(
            "group", 
            member2_id, 
            "Member2 message", 
            group_id=group_id
        )
        result = MessageModel.delete_message("group", msg2_id, member2_id)
        self.assertTrue(result, "Обычный участник должен иметь возможность удалить свое сообщение")

    def test_delete_group_message_by_non_member(self):
        """Проверка, что пользователь не в группе не может удалять сообщения."""
        # Создаем группу и пользователей
        owner_id = self.create_test_user("owner")
        member_id = self.create_test_user("member")
        outsider_id = self.create_test_user("outsider")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Добавляем участника
        GroupModel.add_member(group_id, member_id)
        
        # Создаем сообщение от участника
        msg_id = MessageModel.create_message(
            "group", 
            member_id, 
            "Member message", 
            group_id=group_id
        )
        
        # Пытаемся удалить сообщение пользователем не из группы
        result = MessageModel.delete_message("group", msg_id, outsider_id)
        self.assertFalse(result, "Пользователь не из группы не должен иметь возможность удалять сообщения")

    def test_delete_nonexistent_private_message(self):
        """Проверка попытки удалить несуществующее приватное сообщение."""
        user_id = self.create_test_user("user")
        result = MessageModel.delete_message("private", 99999, user_id)
        self.assertFalse(result, "Не должно быть возможности удалить несуществующее сообщение")

    def test_delete_nonexistent_group_message(self):
        """Проверка попытки удалить несуществующее групповое сообщение."""
        user_id = self.create_test_user("user")
        result = MessageModel.delete_message("group", 99999, user_id)
        self.assertFalse(result, "Не должно быть возможности удалить несуществующее сообщение")

    def test_edit_group_message_by_owner(self):
        """Владелец группы может редактировать любое сообщение в группе."""
        # Создаем тестовых пользователей
        owner_id = self.create_test_user("owner")
        member_id = self.create_test_user("member")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Добавляем участника
        GroupModel.add_member(group_id, member_id)
        
        # Создаем сообщение от участника
        msg_id = MessageModel.create_message(
            "group", 
            member_id, 
            "Original message", 
            group_id=group_id
        )
        
        # Пытаемся редактировать сообщение владельцем группы
        new_text = "Edited by owner"
        result = MessageModel.edit_message(
            "group", 
            msg_id, 
            owner_id, 
            new_text
        )
        
        self.assertTrue(result, "Владелец должен иметь возможность редактировать любое сообщение")
        
        # Проверяем, что текст изменился
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT message_text FROM group_messages WHERE message_id = ?",
                (msg_id,)
            )
            updated_text = cursor.fetchone()[0]
            self.assertEqual(updated_text, new_text)

    def test_edit_group_message_by_admin(self):
        """Админ группы может редактировать любое сообщение в группе."""
        # Создаем тестовых пользователей
        owner_id = self.create_test_user("owner")
        admin_id = self.create_test_user("admin")
        member_id = self.create_test_user("member")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Добавляем админа и участника
        GroupModel.add_member(group_id, admin_id, "admin")
        GroupModel.add_member(group_id, member_id)
        
        # Создаем сообщение от участника
        msg_id = MessageModel.create_message(
            "group", 
            member_id, 
            "Original message", 
            group_id=group_id
        )
        
        # Пытаемся редактировать сообщение админом
        new_text = "Edited by admin"
        result = MessageModel.edit_message(
            "group", 
            msg_id, 
            admin_id, 
            new_text
        )
        
        self.assertTrue(result, "Админ должен иметь возможность редактировать любое сообщение")
        
        # Проверяем, что текст изменился
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT message_text FROM group_messages WHERE message_id = ?",
                (msg_id,)
            )
            updated_text = cursor.fetchone()[0]
            self.assertEqual(updated_text, new_text)

    def test_edit_group_message_by_regular_member_own_message(self):
        """Обычный участник может редактировать только свои сообщения."""
        # Создаем тестовых пользователей
        owner_id = self.create_test_user("owner")
        member1_id = self.create_test_user("member1")
        member2_id = self.create_test_user("member2")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Добавляем участников
        GroupModel.add_member(group_id, member1_id)
        GroupModel.add_member(group_id, member2_id)
        
        # Создаем сообщение от первого участника
        msg_id = MessageModel.create_message(
            "group", 
            member1_id, 
            "Original message", 
            group_id=group_id
        )
        
        # Пытаемся редактировать свое сообщение
        new_text = "Edited by myself"
        result = MessageModel.edit_message(
            "group", 
            msg_id, 
            member1_id, 
            new_text
        )
        
        self.assertTrue(result, "Участник должен иметь возможность редактировать свое сообщение")
        
        # Проверяем, что текст изменился
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT message_text FROM group_messages WHERE message_id = ?",
                (msg_id,)
            )
            updated_text = cursor.fetchone()[0]
            self.assertEqual(updated_text, new_text)

    def test_edit_group_message_by_regular_member_other_message(self):
        """Обычный участник не может редактировать чужие сообщения."""
        # Создаем тестовых пользователей
        owner_id = self.create_test_user("owner")
        member1_id = self.create_test_user("member1")
        member2_id = self.create_test_user("member2")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Добавляем участников
        GroupModel.add_member(group_id, member1_id)
        GroupModel.add_member(group_id, member2_id)
        
        # Создаем сообщение от первого участника
        msg_id = MessageModel.create_message(
            "group", 
            member1_id, 
            "Original message", 
            group_id=group_id
        )
        
        # Пытаемся редактировать чужое сообщение
        new_text = "Edited by other member"
        result = MessageModel.edit_message(
            "group", 
            msg_id, 
            member2_id, 
            new_text
        )
        
        self.assertFalse(result, "Участник не должен иметь возможность редактировать чужие сообщения")
        
        # Проверяем, что текст не изменился
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT message_text FROM group_messages WHERE message_id = ?",
                (msg_id,)
            )
            original_text = cursor.fetchone()[0]
            self.assertEqual(original_text, "Original message")

    def test_edit_group_message_by_non_member(self):
        """Пользователь не из группы не может редактировать сообщения."""
        # Создаем тестовых пользователей
        owner_id = self.create_test_user("owner")
        member_id = self.create_test_user("member")
        outsider_id = self.create_test_user("outsider")
        
        # Создаем группу
        group = GroupModel.create_group("Test Group", owner_id)
        group_id = group['group_id']
        
        # Добавляем участника
        GroupModel.add_member(group_id, member_id)
        
        # Создаем сообщение от участника
        msg_id = MessageModel.create_message(
            "group", 
            member_id, 
            "Original message", 
            group_id=group_id
        )
        
        # Пытаемся редактировать сообщение пользователем не из группы
        new_text = "Edited by outsider"
        result = MessageModel.edit_message(
            "group", 
            msg_id, 
            outsider_id, 
            new_text
        )
        
        self.assertFalse(result, "Пользователь не из группы не должен иметь возможность редактировать сообщения")

    def test_edit_nonexistent_group_message(self):
        """Попытка редактирования несуществующего группового сообщения."""
        user_id = self.create_test_user("user")
        result = MessageModel.edit_message(
            "group", 
            99999, 
            user_id, 
            "New text"
        )
        self.assertFalse(result, "Не должно быть возможности редактировать несуществующее сообщение")

    def test_search_group_messages(self):
        """Проверка поиска сообщений в групповом чате"""
        # Создаем тестовых пользователей
        owner_id = self.create_test_user("owner")
        member_id = self.create_test_user("member")
        
        # Создаем группу
        group = GroupModel.create_group("Search Group", owner_id)
        group_id = group['group_id']
        GroupModel.add_member(group_id, member_id)
        
        # Создаем тестовые сообщения
        MessageModel.create_message("group", owner_id, "Важное сообщение о проекте", group_id)
        MessageModel.create_message("group", member_id, "Вопрос по проекту", group_id)
        MessageModel.create_message("group", owner_id, "Ответ на вопрос", group_id)
        MessageModel.create_message("group", member_id, "Другое сообщение", group_id)
        
        # Ищем сообщения с ключевым словом "проект"
        result = MessageModel.search_messages(
            search_query="проект",
            message_type="group",
            chat_id=group_id,
            user_id=owner_id
        )
        
        self.assertEqual(result['total'], 2, "Должно найти 2 сообщения с 'проект'")
        self.assertEqual(len(result['messages']), 2)
        self.assertTrue(all("проект" in msg['text'].lower() for msg in result['messages']))

    def test_search_group_messages_pagination(self):
        """Проверка пагинации при поиске в групповом чате"""
        # Создаем тестовых пользователей
        owner_id = self.create_test_user("owner")
        
        # Создаем группу
        group = GroupModel.create_group("Pagination Group", owner_id)
        group_id = group['group_id']
        
        # Создаем 5 тестовых сообщений
        for i in range(1, 6):
            MessageModel.create_message("group", owner_id, f"Тестовое сообщение {i}", group_id)
        
        # Первая страница (2 сообщения)
        result_page1 = MessageModel.search_messages(
            search_query="Тестовое",
            message_type="group",
            chat_id=group_id,
            user_id=owner_id,
            page=1,
            per_page=2
        )
        
        self.assertEqual(result_page1['total'], 5)
        self.assertEqual(len(result_page1['messages']), 2)
        self.assertEqual(result_page1['page'], 1)
        
        # Вторая страница (2 сообщения)
        result_page2 = MessageModel.search_messages(
            search_query="Тестовое",
            message_type="group",
            chat_id=group_id,
            user_id=owner_id,
            page=2,
            per_page=2
        )
        
        self.assertEqual(len(result_page2['messages']), 2)
        self.assertEqual(result_page2['page'], 2)
        
        # Третья страница (1 сообщение)
        result_page3 = MessageModel.search_messages(
            search_query="Тестовое",
            message_type="group",
            chat_id=group_id,
            user_id=owner_id,
            page=3,
            per_page=2
        )
        
        self.assertEqual(len(result_page3['messages']), 1)
        self.assertEqual(result_page3['page'], 3)

    def test_search_private_messages(self):
        """Проверка поиска в приватных сообщениях"""
        # Создаем тестовых пользователей
        user1_id = self.create_test_user("user1")
        user2_id = self.create_test_user("user2")
        
        # Создаем тестовые сообщения
        MessageModel.create_message("private", user1_id, "Привет, как дела?", receiver_id=user2_id)
        MessageModel.create_message("private", user2_id, "Привет, все хорошо!", receiver_id=user1_id)
        MessageModel.create_message("private", user1_id, "Что делаешь?", receiver_id=user2_id)
        MessageModel.create_message("private", user2_id, "Работаю над проектом", receiver_id=user1_id)
        
        # Ищем сообщения с ключевым словом "проект"
        result = MessageModel.search_messages(
            search_query="проект",
            message_type="private",
            chat_id="user2",  # username собеседника
            user_id=user1_id
        )
        
        self.assertEqual(result['total'], 1, "Должно найти 1 сообщение с 'проект'")
        self.assertEqual(len(result['messages']), 1)
        self.assertIn("проект", result['messages'][0]['text'].lower())

    def test_search_private_messages_nonexistent_user(self):
        """Проверка поиска с несуществующим собеседником"""
        user1_id = self.create_test_user("user1")
        
        result = MessageModel.search_messages(
            search_query="тест",
            message_type="private",
            chat_id="nonexistent_user",
            user_id=user1_id
        )
        
        self.assertEqual(result['total'], 0)
        self.assertEqual(len(result['messages']), 0)

    def test_search_group_messages_empty_query(self):
        """Проверка поиска с пустым запросом"""
        owner_id = self.create_test_user("owner")
        group = GroupModel.create_group("Empty Query Group", owner_id)
        group_id = group['group_id']
        
        result = MessageModel.search_messages(
            search_query="",
            message_type="group",
            chat_id=group_id,
            user_id=owner_id
        )
        
        self.assertEqual(result['total'], 0)
        self.assertEqual(len(result['messages']), 0)

    def test_search_error_handling(self):
        """Проверка обработки ошибок при поиске"""
        # Создаем ситуацию, которая вызовет ошибку (неправильный тип сообщения)
        result = MessageModel.search_messages(
            search_query="test",
            message_type="invalid_type",
            chat_id="1",
            user_id=1
        )
        
        # Должен вернуться корректный объект с нулевыми результатами
        self.assertEqual(result['total'], 0)
        self.assertEqual(len(result['messages']), 0)
        self.assertEqual(result['page'], 1)

if __name__ == '__main__':
    unittest.main()
