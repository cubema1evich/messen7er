from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# Генератор клча    
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)
#приытный ключ 
with open("server_private.pem", "wb") as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))

# публичный ключ
public_key = private_key.public_key()
with open("server_public.pem", "wb") as f:
    f.write(public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ))

print("Ключи успешно созданы: server_private.pem и server_public.pem")