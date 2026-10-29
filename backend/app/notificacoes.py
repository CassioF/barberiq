"""
Notificações (e-mail / WhatsApp).

O envio real depende de um provedor externo (SMTP, API do WhatsApp...). Aqui o
envio é SIMULADO em `_enviar`: registra no log e marca como 'enviado'. Para
integrar de verdade, basta trocar o corpo de `_enviar`.
"""
import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app import models, tempo
from app.config import settings
from app.ia.noshow import nivel

log = logging.getLogger("barberiq.notificacoes")
TN = models.TipoNotificacao


def _enviar(canal: models.CanalNotificacao, usuario: models.Usuario, mensagem: str) -> bool:
    destino = usuario.email if canal == models.CanalNotificacao.email else (usuario.telefone or "-")
    log.info("[%s] -> %s: %s", canal.value, destino, mensagem)
    return True


def notificar(
    db: Session, usuario: models.Usuario, tipo: TN, mensagem: str,
    agendamento: models.Agendamento | None = None,
    canal: models.CanalNotificacao | None = None,
) -> models.Notificacao:
    if canal is None:  # WhatsApp quando há telefone, senão e-mail
        canal = models.CanalNotificacao.whatsapp if usuario.telefone else models.CanalNotificacao.email
    n = models.Notificacao(
        usuario_id=usuario.id, agendamento_id=agendamento.id if agendamento else None,
        canal=canal, tipo=tipo, mensagem=mensagem[:500],
    )
    db.add(n)
    try:
        ok = _enviar(canal, usuario, mensagem)
    except Exception:  # falha do provedor não pode derrubar o agendamento
        log.exception("Falha ao enviar notificação")
        ok = False
    n.status = models.StatusNotificacao.enviado if ok else models.StatusNotificacao.falha
    n.enviado_em = tempo.agora() if ok else None
    db.commit()
    return n


def _fmt(ag: models.Agendamento) -> str:
    return f"{ag.servico.nome} com {ag.barbeiro.nome} em {ag.data_hora:%d/%m/%Y às %H:%M}"


def notificar_confirmacao(db: Session, ag: models.Agendamento) -> None:
    notificar(db, ag.cliente, TN.confirmacao, f"Agendamento confirmado: {_fmt(ag)}.", ag)


def notificar_cancelamento(db: Session, ag: models.Agendamento) -> None:
    notificar(db, ag.cliente, TN.cancelamento, f"Agendamento cancelado: {_fmt(ag)}.", ag)


def disparar_lembretes(db: Session) -> int:
    """
    Envia lembretes dos agendamentos confirmados que estão chegando.
    - risco normal: lembrete 24h antes
    - risco alto  : lembrete reforçado (pede confirmação) 48h antes
    Cada tipo é enviado uma única vez por agendamento. Retorna quantos foram enviados.
    """
    agora = tempo.agora()
    candidatos = (
        db.query(models.Agendamento)
        .filter(
            models.Agendamento.status == models.StatusAgendamento.confirmado,
            models.Agendamento.data_hora > agora,
            models.Agendamento.data_hora <= agora + timedelta(hours=48),
        )
        .all()
    )
    enviados = 0
    for ag in candidatos:
        risco = float(ag.previsao.risco) if ag.previsao else 0.0
        alto = nivel(risco, settings.LIMITE_ALTO_RISCO) == "alto"
        tipo = TN.lembrete_reforcado if alto else TN.lembrete
        janela = timedelta(hours=48 if alto else 24)
        if ag.data_hora - agora > janela:
            continue
        ja_enviado = (
            db.query(models.Notificacao)
            .filter(models.Notificacao.agendamento_id == ag.id, models.Notificacao.tipo == tipo)
            .first()
        )
        if ja_enviado:
            continue
        if alto:
            msg = (f"Olá, {ag.cliente.nome}! Seu horário é {_fmt(ag)}. "
                   "Por favor, CONFIRME sua presença respondendo esta mensagem.")
        else:
            msg = f"Lembrete: você tem {_fmt(ag)}."
        notificar(db, ag.cliente, tipo, msg, ag)
        enviados += 1
    return enviados
