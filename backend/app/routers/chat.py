"""Chatbot de agendamento para o cliente (IA quando há ANTHROPIC_API_KEY; senão, modo guiado no front)."""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import chat, models
from app.config import settings
from app.database import get_db
from app.deps import exigir_tipos, usuario_atual

router = APIRouter(prefix="/chat", tags=["Chatbot"])
log = logging.getLogger("barberiq.chat")
somente_cliente = exigir_tipos(models.TipoUsuario.cliente)


class MensagemIn(BaseModel):
    papel: Literal["user", "assistant"]
    texto: str = Field(min_length=1, max_length=1000)


class ChatIn(BaseModel):
    mensagens: list[MensagemIn] = Field(min_length=1, max_length=30)


class ChatOut(BaseModel):
    resposta: str
    atualizou: bool = False  # True se o assistente criou ou cancelou um agendamento


@router.get("/status", summary="Informa se o assistente com IA está ativo")
def status(_: models.Usuario = Depends(usuario_atual)):
    return {"ia": bool(settings.ANTHROPIC_API_KEY)}


@router.post("", response_model=ChatOut, summary="Conversar com o assistente de agendamento (cliente)")
def conversar(dados: ChatIn, db: Session = Depends(get_db), cliente: models.Usuario = Depends(somente_cliente)):
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="Assistente com IA não configurado.")
    if dados.mensagens[-1].papel != "user":
        raise HTTPException(status_code=422, detail="A última mensagem deve ser do cliente.")
    # a API exige que a conversa comece pelo usuário
    historico = [m.model_dump() for m in dados.mensagens]
    while historico and historico[0]["papel"] != "user":
        historico.pop(0)
    try:
        return chat.responder(db, cliente, historico)
    except Exception:
        log.exception("Falha no assistente")
        raise HTTPException(status_code=503, detail="O assistente está indisponível agora. Tente de novo em instantes.")
