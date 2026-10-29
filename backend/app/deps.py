"""Dependências de autenticação/autorização para as rotas."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import models, security
from app.database import get_db

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def usuario_atual(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> models.Usuario:
    erro = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou sessão expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        dados = security.decodificar_token(token)
        usuario = db.get(models.Usuario, int(dados["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise erro
    if not usuario or not usuario.ativo:
        raise erro
    return usuario


def exigir_tipos(*tipos: models.TipoUsuario):
    """Gera uma dependency que só deixa passar usuários dos tipos informados."""

    def verificador(usuario: models.Usuario = Depends(usuario_atual)) -> models.Usuario:
        if usuario.tipo not in tipos:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissão para esta ação.")
        return usuario

    return verificador


somente_admin = exigir_tipos(models.TipoUsuario.admin)
admin_ou_barbeiro = exigir_tipos(models.TipoUsuario.admin, models.TipoUsuario.barbeiro)
