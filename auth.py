from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

import os

JWT_SECRET = os.getenv("JWT_SECRET") or "dev-change-me"  # em produção, defina JWT_SECRET no ambiente

JWT_ALG = "HS256"
JWT_EXPIRE_DAYS = 30

def hash_pw(pw: str):
    return pwd.hash(pw)

def verify_pw(pw, hashed):
    return pwd.verify(pw, hashed)

def make_token(uid: int):
    exp = datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS)
    return jwt.encode({"sub": str(uid), "exp": exp}, JWT_SECRET, algorithm=JWT_ALG)

def read_token(token: str):
    try:
        return int(jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])["sub"])
    except:
        return None
