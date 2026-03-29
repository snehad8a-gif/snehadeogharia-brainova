import bcrypt

def hash_password(plain_password: str) -> bytes:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode(), salt)
    return hashed

def verify_password(plain_password: str, hashed_password: bytes) -> bool:
    return bcrypt.checkpw(
        plain_password.encode(),
        hashed_password
    )

password = "mySecret123"

hashed = hash_password(password)
print("Hashed:", hashed)

is_valid = verify_password("mySecret123", hashed)
print("Password valid?", is_valid)
