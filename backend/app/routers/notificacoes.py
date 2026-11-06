"""Histórico de notificações, disparo de lembretes e WhatsApp do usuário."""
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import mensageiros, models, notificacoes
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


# ---------------------------------------------------------------- WhatsApp ---
@router.get("/canais", response_model=schemas.CanaisOut, summary="Canal de mensagens do usuário logado")
def canais(usuario: models.Usuario = Depends(usuario_atual)):
    return schemas.CanaisOut(
        canal_atual=notificacoes.canal_padrao(usuario),
        whatsapp_ativo=mensageiros.whatsapp_ativo(),
        telefone=usuario.telefone,
    )


@router.put("/whatsapp", response_model=schemas.CanaisOut, summary="Define o número de WhatsApp do usuário logado")
def definir_whatsapp(dados: schemas.TelefoneIn, db: Session = Depends(get_db),
                     usuario: models.Usuario = Depends(usuario_atual)):
    tel = (dados.telefone or "").strip() or None
    if tel and not 10 <= len(re.sub(r"\D", "", tel)) <= 13:
        raise HTTPException(422, "Informe o número com DDD, ex.: 34999990002.")
    usuario.telefone = tel
    db.commit()
    return canais(usuario)


@router.post("/teste", response_model=schemas.NotificacaoOut,
             summary="Envia uma mensagem de teste para o usuário logado")
def teste(db: Session = Depends(get_db), usuario: models.Usuario = Depends(usuario_atual)):
    return notificacoes.notificar(
        db, usuario, models.TipoNotificacao.confirmacao,
        f"Olá, {usuario.nome}! 💈 Mensagem de teste do AI Barbershop: suas confirmações chegarão por aqui.",
    )
