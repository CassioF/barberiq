"""Fábrica do CRUD de usuários por tipo — reaproveitada por /clientes e /barbeiros."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.deps import somente_admin, usuario_atual


def criar_router(prefixo: str, tag: str, tipo: models.TipoUsuario, rotulo: str,
                 leitura=None) -> APIRouter:
    """`leitura`: dependency que autoriza GET (padrão: somente admin)."""
    router = APIRouter(prefix=prefixo, tags=[tag])
    ler = leitura or somente_admin
    nao_achou = lambda: HTTPException(status_code=404, detail=f"{rotulo} não encontrado.")
    dup = lambda: HTTPException(status_code=409, detail=f"Já existe um usuário cadastrado com este e-mail.")

    @router.post("", response_model=schemas.UsuarioOut, status_code=201, summary=f"Cadastrar {rotulo.lower()}",
                 dependencies=[Depends(somente_admin)])
    def criar(dados: schemas.UsuarioCreate, db: Session = Depends(get_db)):
        if crud.obter_usuario_por_email(db, dados.email):
            raise dup()
        try:
            return crud.criar_usuario(db, dados, tipo)
        except IntegrityError:
            db.rollback()
            raise dup()

    @router.get("", response_model=list[schemas.UsuarioOut], summary=f"Listar {tag.lower()} (paginação + busca)",
                dependencies=[Depends(ler)])
    def listar(
        response: Response,
        skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
        busca: Optional[str] = Query(None, description="Filtra por nome ou e-mail"),
        somente_ativos: bool = Query(False),
        db: Session = Depends(get_db),
    ):
        registros, total = crud.listar_usuarios(db, tipo, skip, limit, busca, somente_ativos)
        response.headers["X-Total-Count"] = str(total)
        return registros

    @router.get("/{usuario_id}", response_model=schemas.UsuarioOut, summary=f"Obter {rotulo.lower()} pelo ID",
                dependencies=[Depends(ler)])
    def obter(usuario_id: int, db: Session = Depends(get_db)):
        u = crud.obter_usuario(db, usuario_id, tipo)
        if not u:
            raise nao_achou()
        return u

    @router.put("/{usuario_id}", response_model=schemas.UsuarioOut, summary=f"Atualizar {rotulo.lower()} (parcial)",
                dependencies=[Depends(somente_admin)])
    def atualizar(usuario_id: int, dados: schemas.UsuarioUpdate, db: Session = Depends(get_db)):
        u = crud.obter_usuario(db, usuario_id, tipo)
        if not u:
            raise nao_achou()
        if dados.email and dados.email.lower() != u.email.lower() and crud.obter_usuario_por_email(db, dados.email):
            raise dup()
        try:
            return crud.atualizar_usuario(db, u, dados)
        except IntegrityError:
            db.rollback()
            raise dup()

    @router.delete("/{usuario_id}", status_code=204, summary=f"Excluir {rotulo.lower()}",
                   dependencies=[Depends(somente_admin)])
    def excluir(usuario_id: int, db: Session = Depends(get_db)):
        u = crud.obter_usuario(db, usuario_id, tipo)
        if not u:
            raise nao_achou()
        if crud.usuario_possui_agendamentos(db, usuario_id):
            raise HTTPException(
                status_code=409,
                detail=f"Este {rotulo.lower()} possui agendamentos vinculados e não pode ser excluído. "
                       "Desative-o (ativo = false) ou remova os agendamentos primeiro.",
            )
        crud.excluir_usuario(db, u)
        return Response(status_code=204)

    return router
