"""
Notificações (WhatsApp / e-mail).

O WhatsApp é enviado de verdade quando a Cloud API está configurada (ver
`mensageiros.py`); sem configuração — e para e-mail, que não tem provedor —
o envio é SIMULADO: registra no log e marca como 'enviado'.
"""
import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app import mensageiros, models, tempo
from app.config import settings
from app.ia.noshow import nivel

log = logging.getLogger("barberiq.notificacoes")
TN = models.TipoNotificacao
CN = models.CanalNotificacao


def _enviar(canal: CN, usuario: models.Usuario, mensagem: str) -> bool:
    if canal == CN.whatsapp and mensageiros.whatsapp_ativo() and usuario.telefone:
        mensageiros.enviar_whatsapp(usuario.telefone, mensagem)
        return True
    destino = usuario.email if canal == CN.email else usuario.telefone
    log.info("[%s simulado] -> %s: %s", canal.value, destino or "-", mensagem)
    return True


def canal_padrao(usuario: models.Usuario) -> CN:
    """WhatsApp quando o usuário tem telefone; senão e-mail."""
    return CN.whatsapp if usuario.telefone else CN.email


def notificar(
    db: Session, usuario: models.Usuario, tipo: TN, mensagem: str,
    agendamento: models.Agendamento | None = None,
    canal: CN | None = None,
) -> models.Notificacao:
    if canal is None:
        canal = canal_padrao(usuario)
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
    notificar(db, ag.cliente, TN.confirmacao,
              f"Olá, {ag.cliente.nome}! ✅ Agendamento confirmado: {_fmt(ag)}. Até lá!", ag)


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
