"""Histórico de notificações e disparo de lembretes."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models, notificacoes
from app.database import get_db
from app.deps import somente_admin, usuario_atual
from app import schemas

router = APIRouter(prefix="/notificacoes", tags=["Notificações"])


@router.get("/minhas", response_model=list[schemas.NotificacaoOut], summary="Notificações do usuário logado")
def minhas(limit: int = Query(30, ge=1, le=200), db: Session = Depends(get_db),
           usuario: models.Usuario = Depends(usuario_atual)):
    return (db.query(models.Notificacao).filter(models.Notificacao.usuario_id == usuario.id)
            .order_by(models.Notificacao.id.desc()).limit(limit).all())


@router.get("", response_model=list[schemas.NotificacaoOut], dependencies=[Depends(somente_admin)],
            summary="Todas as notificações (admin)")
def todas(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(models.Notificacao).order_by(models.Notificacao.id.desc()).limit(limit).all()


@router.post("/disparar-lembretes", dependencies=[Depends(somente_admin)],
             summary="Envia agora os lembretes pendentes (24h normal / 48h reforçado p/ alto risco)")
def disparar(db: Session = Depends(get_db)):
    return {"enviados": notificacoes.disparar_lembretes(db)}
