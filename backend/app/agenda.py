"""
Regras de negócio da agenda: horários livres, bloqueio de conflitos,
criação de agendamento e cálculo do risco de no-show.
"""
from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app import models, notificacoes, tempo
from app.config import settings
from app.ia import noshow

SA = models.StatusAgendamento
# Agendamentos que ocupam o horário do barbeiro
OCUPAM = (SA.confirmado, SA.concluido, SA.faltou)


def _conflito(msg: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)


def _invalido(msg: str) -> HTTPException:
    return HTTPException(status_code=422, detail=msg)


def fim_do_atendimento(ag: models.Agendamento) -> datetime:
    return ag.data_hora + timedelta(minutes=ag.servico.duracao_min)


def _agendamentos_do_dia(db: Session, campo, valor: int, dia: date) -> list[models.Agendamento]:
    ini = datetime.combine(dia, datetime.min.time())
    return (
        db.query(models.Agendamento)
        .options(joinedload(models.Agendamento.servico))
        .filter(
            campo == valor,
            models.Agendamento.data_hora >= ini,
            models.Agendamento.data_hora < ini + timedelta(days=1),
            models.Agendamento.status.in_(OCUPAM),
        )
        .all()
    )


def _sobrepoe(ini: datetime, fim: datetime, existentes: list[models.Agendamento]) -> bool:
    return any(ini < fim_do_atendimento(e) and e.data_hora < fim for e in existentes)


def horarios_livres(db: Session, barbeiro_id: int, servico: models.Servico, dia: date) -> list[datetime]:
    """Horários em que o barbeiro pode começar este serviço no dia informado."""
    janelas = (
        db.query(models.DisponibilidadeBarbeiro)
        .filter_by(barbeiro_id=barbeiro_id, dia_semana=dia.weekday())
        .all()
    )
    ocupados = _agendamentos_do_dia(db, models.Agendamento.barbeiro_id, barbeiro_id, dia)
    agora = tempo.agora()
    dur = timedelta(minutes=servico.duracao_min)
    passo = timedelta(minutes=settings.PASSO_AGENDA_MIN)

    livres = []
    for j in sorted(janelas, key=lambda x: x.hora_inicio):
        t = datetime.combine(dia, j.hora_inicio)
        limite = datetime.combine(dia, j.hora_fim)
        while t + dur <= limite:
            if t > agora and not _sobrepoe(t, t + dur, ocupados):
                livres.append(t)
            t += passo
    return livres


def calcular_risco(db: Session, cliente_id: int, data_hora: datetime, criado_em: datetime) -> float:
    """Monta as variáveis do modelo a partir do histórico do cliente e consulta a IA."""
    passados = (
        db.query(models.Agendamento.status)
        .filter(
            models.Agendamento.cliente_id == cliente_id,
            models.Agendamento.status.in_((SA.concluido, SA.faltou)),
        )
        .all()
    )
    if passados:
        taxa = sum(1 for (s,) in passados if s == SA.faltou) / len(passados)
    else:
        taxa = noshow.TAXA_CLIENTE_NOVO
    antecedencia = max((data_hora - criado_em).total_seconds() / 3600, 0.0)
    return noshow.prever(taxa, data_hora.weekday(), antecedencia)


def criar_agendamento(
    db: Session, cliente: models.Usuario, barbeiro_id: int, servico_id: int, data_hora: datetime
) -> models.Agendamento:
    data_hora = data_hora.replace(tzinfo=None, second=0, microsecond=0)

    servico = db.get(models.Servico, servico_id)
    if not servico or not servico.ativo:
        raise HTTPException(status_code=404, detail="Serviço não encontrado.")
    barbeiro = db.get(models.Usuario, barbeiro_id)
    if not barbeiro or barbeiro.tipo != models.TipoUsuario.barbeiro or not barbeiro.ativo:
        raise HTTPException(status_code=404, detail="Barbeiro não encontrado.")

    agora = tempo.agora()
    if data_hora <= agora:
        raise _invalido("Escolha um horário no futuro.")
    if data_hora not in horarios_livres(db, barbeiro_id, servico, data_hora.date()):
        raise _conflito("Horário indisponível para este barbeiro. Escolha outro horário.")

    # o cliente também não pode estar em dois lugares ao mesmo tempo
    do_cliente = _agendamentos_do_dia(db, models.Agendamento.cliente_id, cliente.id, data_hora.date())
    if _sobrepoe(data_hora, data_hora + timedelta(minutes=servico.duracao_min), do_cliente):
        raise _conflito("Você já tem um agendamento neste horário.")

    ag = models.Agendamento(
        cliente_id=cliente.id, barbeiro_id=barbeiro_id, servico_id=servico_id,
        data_hora=data_hora, status=SA.confirmado,
    )
    db.add(ag)
    try:
        db.flush()  # a UNIQUE (barbeiro_id, data_hora) é a última barreira contra corrida
    except IntegrityError:
        db.rollback()
        raise _conflito("Este horário acabou de ser reservado. Escolha outro.")

    risco = calcular_risco(db, cliente.id, data_hora, agora)
    db.add(models.PrevisaoNoShow(agendamento_id=ag.id, risco=round(risco, 4), modelo_versao=noshow.VERSAO))
    db.commit()
    db.refresh(ag)
    notificacoes.notificar_confirmacao(db, ag)
    return ag


def para_saida(ag: models.Agendamento, mostrar_risco: bool) -> dict:
    """Converte para o schema de saída; o risco só vai para barbeiro/admin."""
    from app import schemas
    out = schemas.AgendamentoOut.model_validate(ag)
    if mostrar_risco and ag.previsao:
        r = float(ag.previsao.risco)
        out.risco_noshow = r
        out.nivel_risco = noshow.nivel(r, settings.LIMITE_ALTO_RISCO)
    return out
