"""Hash de senha (bcrypt) e tokens JWT."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

ALGORITMO = "HS256"


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode()[:72], bcrypt.gensalt()).decode()


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode()[:72], senha_hash.encode())
    except ValueError:
        return False


def criar_token(usuario_id: int, tipo: str) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    return jwt.encode(
        {"sub": str(usuario_id), "tipo": tipo, "exp": expira}, settings.SECRET_KEY, algorithm=ALGORITMO
    )


def decodificar_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITMO])
