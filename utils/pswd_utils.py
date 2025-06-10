import os
import bcrypt
from contextlib import contextmanager
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

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

# Генерация RSA ключей (выполняется один раз)
def generate_rsa_keys():
    # Генерируем приватный ключ
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Получаем публичный ключ
    public_key = private_key.public_key()
    
    # Сериализуем ключи
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Сохраняем ключи в файлы (выполняется один раз)
    with open('private_key.pem', 'wb') as f:
        f.write(private_pem)
    
    with open('public_key.pem', 'wb') as f:
        f.write(public_pem)
    
    return private_pem, public_pem

# Загрузка ключей
def load_rsa_keys():
    if not os.path.exists('private_key.pem') or not os.path.exists('public_key.pem'):
        generate_rsa_keys()
    
    with open('private_key.pem', 'rb') as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    
    with open('public_key.pem', 'rb') as f:
        public_key = serialization.load_pem_public_key(
            f.read(),
            backend=default_backend()
        )
    
    return private_key, public_key