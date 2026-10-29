"""Autenticação: cadastro de cliente, login (JWT) e dados do usuário logado."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import crud, models, schemas, security
from app.database import get_db
from app.deps import usuario_atual

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/registrar", response_model=schemas.UsuarioOut, status_code=status.HTTP_201_CREATED,
             summary="Cadastro público de cliente")
def registrar(dados: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    if crud.obter_usuario_por_email(db, dados.email):
        raise HTTPException(status_code=409, detail="Já existe um usuário cadastrado com este e-mail.")
    return crud.criar_usuario(db, dados, models.TipoUsuario.cliente)


@router.post("/login", response_model=schemas.Token,
             summary="Login (form: username = e-mail, password = senha)")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = crud.obter_usuario_por_email(db, form.username)
    if not usuario or not usuario.ativo or not security.verificar_senha(form.password, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    return schemas.Token(
        access_token=security.criar_token(usuario.id, usuario.tipo.value),
        usuario=schemas.UsuarioOut.model_validate(usuario),
    )


@router.get("/me", response_model=schemas.UsuarioOut, summary="Dados do usuário logado")
def me(usuario: models.Usuario = Depends(usuario_atual)):
    return usuario
