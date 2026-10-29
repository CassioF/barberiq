"""
Camada CRUD: funções que conversam diretamente com o banco via SQLAlchemy.
Separadas dos endpoints para poderem ser testadas sem depender do FastAPI.

Usuários (cliente / barbeiro / admin) compartilham a tabela `usuarios`; todas as
funções recebem o `tipo` e só enxergam registros daquele tipo.
"""
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.security import hash_senha

T = models.TipoUsuario


# ================================================================ USUÁRIOS ==
def criar_usuario(db: Session, dados: schemas.UsuarioCreate, tipo: T) -> models.Usuario:
    novo = models.Usuario(
        nome=dados.nome,
        email=dados.email.lower(),
        telefone=dados.telefone,
        senha_hash=hash_senha(dados.senha),
        tipo=tipo,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


def obter_usuario(db: Session, usuario_id: int, tipo: Optional[T] = None) -> Optional[models.Usuario]:
    q = db.query(models.Usuario).filter(models.Usuario.id == usuario_id)
    if tipo:
        q = q.filter(models.Usuario.tipo == tipo)
    return q.first()


def obter_usuario_por_email(db: Session, email: str) -> Optional[models.Usuario]:
    """E-mail é único na tabela inteira (independente do tipo)."""
    return db.query(models.Usuario).filter(func.lower(models.Usuario.email) == email.lower()).first()


def listar_usuarios(
    db: Session, tipo: T, skip: int = 0, limit: int = 20, busca: Optional[str] = None,
    somente_ativos: bool = False,
) -> tuple[list[models.Usuario], int]:
    """Retorna (página, total). `busca` filtra por nome/e-mail (parcial, sem caixa)."""
    q = db.query(models.Usuario).filter(models.Usuario.tipo == tipo)
    if somente_ativos:
        q = q.filter(models.Usuario.ativo.is_(True))
    if busca:
        termo = f"%{busca.lower()}%"
        q = q.filter(func.lower(models.Usuario.nome).like(termo) | func.lower(models.Usuario.email).like(termo))
    total = q.count()
    return q.order_by(models.Usuario.nome).offset(skip).limit(limit).all(), total


def atualizar_usuario(db: Session, usuario: models.Usuario, dados: schemas.UsuarioUpdate) -> models.Usuario:
    campos = dados.model_dump(exclude_unset=True)
    if "senha" in campos:
        usuario.senha_hash = hash_senha(campos.pop("senha"))
    if "email" in campos and campos["email"]:
        campos["email"] = campos["email"].lower()
    for campo, valor in campos.items():
        setattr(usuario, campo, valor)
    db.commit()
    db.refresh(usuario)
    return usuario


def usuario_possui_agendamentos(db: Session, usuario_id: int) -> bool:
    return (
        db.query(models.Agendamento)
        .filter((models.Agendamento.cliente_id == usuario_id) | (models.Agendamento.barbeiro_id == usuario_id))
        .first()
        is not None
    )


def excluir_usuario(db: Session, usuario: models.Usuario) -> None:
    db.delete(usuario)
    db.commit()


# ================================================================ SERVIÇOS ==
def criar_servico(db: Session, dados: schemas.ServicoCreate) -> models.Servico:
    s = models.Servico(**dados.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def listar_servicos(db: Session, somente_ativos: bool = True) -> list[models.Servico]:
    q = db.query(models.Servico)
    if somente_ativos:
        q = q.filter(models.Servico.ativo.is_(True))
    return q.order_by(models.Servico.nome).all()


def obter_servico(db: Session, servico_id: int) -> Optional[models.Servico]:
    return db.get(models.Servico, servico_id)


def obter_servico_por_nome(db: Session, nome: str) -> Optional[models.Servico]:
    return db.query(models.Servico).filter(func.lower(models.Servico.nome) == nome.lower()).first()


def atualizar_servico(db: Session, servico: models.Servico, dados: schemas.ServicoUpdate) -> models.Servico:
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(servico, campo, valor)
    db.commit()
    db.refresh(servico)
    return servico


def servico_possui_agendamentos(db: Session, servico_id: int) -> bool:
    return db.query(models.Agendamento).filter(models.Agendamento.servico_id == servico_id).first() is not None


def excluir_servico(db: Session, servico: models.Servico) -> None:
    db.delete(servico)
    db.commit()


# ========================================================== DISPONIBILIDADE ==
def listar_disponibilidade(db: Session, barbeiro_id: int) -> list[models.DisponibilidadeBarbeiro]:
    return (
        db.query(models.DisponibilidadeBarbeiro)
        .filter(models.DisponibilidadeBarbeiro.barbeiro_id == barbeiro_id)
        .order_by(models.DisponibilidadeBarbeiro.dia_semana, models.DisponibilidadeBarbeiro.hora_inicio)
        .all()
    )


def substituir_disponibilidade(
    db: Session, barbeiro_id: int, janelas: list[schemas.DisponibilidadeIn]
) -> list[models.DisponibilidadeBarbeiro]:
    db.query(models.DisponibilidadeBarbeiro).filter(
        models.DisponibilidadeBarbeiro.barbeiro_id == barbeiro_id
    ).delete()
    for j in janelas:
        db.add(models.DisponibilidadeBarbeiro(barbeiro_id=barbeiro_id, **j.model_dump()))
    db.commit()
    return listar_disponibilidade(db, barbeiro_id)
